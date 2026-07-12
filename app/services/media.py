import hashlib
import subprocess
from dataclasses import dataclass


class MediaControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlayerState:
    name: str
    label: str
    status: str
    title: str
    artist: str
    art_url: str
    duration_us: int
    can_play: bool
    can_pause: bool
    can_previous: bool
    can_next: bool
    can_seek: bool

    @property
    def current_track(self) -> str:
        if self.title and self.artist:
            return f"{self.title} — {self.artist}"

        return self.title or self.artist or "Sin reproducción"


class PlayerctlMediaService:
    SEPARATOR = "\x1f"
    METADATA_FORMAT = SEPARATOR.join(
        (
            "{{status}}",
            "{{xesam:title}}",
            "{{xesam:artist}}",
            "{{mpris:length}}",
            "{{mpris:artUrl}}",
            "remote-c-end",
        )
    )

    SESSION_COMMANDS = {
        "play_pause": ("play-pause",),
        "previous": ("previous",),
        "next": ("next",),
        "seek_backward": ("position", "10-"),
        "seek_forward": ("position", "10+"),
    }

    def __init__(self) -> None:
        self._preferred_player_name: str | None = None

    def get_state(self) -> dict:
        players = self._get_players()
        player = self._select_active_player(players)

        if player is None:
            return {
                "playing": False,
                "playback_status": "stopped",
                "current_track": "Sin reproducción",
                "media_sessions": [],
            }

        return {
            "playing": player.status.casefold() == "playing",
            "playback_status": player.status.casefold(),
            "current_track": player.current_track,
            "media_sessions": self._serialize_players(players),
        }

    def get_sessions(self) -> dict:
        return {
            "players": self._serialize_players(self._get_players()),
        }

    @staticmethod
    def _serialize_players(
        players: list[PlayerState],
    ) -> list[dict]:
        return [
            {
                "name": player.name,
                "label": player.label,
                "status": player.status.casefold(),
                "playing": player.status.casefold() == "playing",
                "title": player.title,
                "artist": player.artist,
                "current_track": player.current_track,
                "artwork_id": (
                    hashlib.sha256(player.art_url.encode()).hexdigest()[:12]
                    if player.art_url
                    else None
                ),
                "duration_seconds": round(player.duration_us / 1_000_000),
                "can_play_pause": (
                    player.can_pause
                    if player.status.casefold() == "playing"
                    else player.can_play
                ),
                "can_previous": player.can_previous,
                "can_next": player.can_next,
                "can_seek": player.can_seek,
            }
            for player in players
        ]

    def control(self, action: str) -> dict:
        player = self._get_active_player()

        if player is None:
            raise MediaControlError("No hay ningún reproductor disponible")

        commands = {
            "play_pause": ("play-pause",),
            "previous": ("previous",),
            "next": ("next",),
        }

        command = commands.get(str(action))

        if command is None:
            raise MediaControlError("Acción multimedia no permitida")

        self._preferred_player_name = player.name
        self._run("--player", player.name, *command)
        return self.get_state()

    def control_session(self, player_name: str, action: str) -> dict:
        available_players = self._list_player_names()

        if player_name not in available_players:
            raise MediaControlError("El reproductor seleccionado ya no está disponible")

        command = self.SESSION_COMMANDS.get(str(action))

        if command is None:
            raise MediaControlError("Acción multimedia no permitida")

        self._preferred_player_name = player_name
        self._run("--player", player_name, *command)
        return self.get_sessions()

    def get_artwork_url(self, player_name: str) -> str:
        if player_name not in self._list_player_names():
            raise MediaControlError("El reproductor seleccionado ya no está disponible")

        artwork_url = self._run(
            "--player",
            player_name,
            "metadata",
            "mpris:artUrl",
            allow_empty=True,
        )

        if not artwork_url:
            raise MediaControlError("El reproductor no ofrece una carátula")

        return artwork_url

    def _get_active_player(self) -> PlayerState | None:
        return self._select_active_player(self._get_players())

    def _select_active_player(
        self,
        players: list[PlayerState],
    ) -> PlayerState | None:
        if not players:
            self._preferred_player_name = None
            return None

        selected = next(
            (player for player in players if player.status.casefold() == "playing"),
            None,
        )

        if selected is None and self._preferred_player_name:
            selected = next(
                (
                    player
                    for player in players
                    if player.name == self._preferred_player_name
                ),
                None,
            )

        if selected is None:
            selected = next(
                (player for player in players if player.title or player.artist),
                players[0],
            )

        self._preferred_player_name = selected.name
        return selected

    def _get_players(self) -> list[PlayerState]:
        players: list[PlayerState] = []

        for name in self._list_player_names():
            player = self._read_player(name)

            if player is not None:
                players.append(player)

        return players

    def _list_player_names(self) -> list[str]:
        output = self._run("--list-all", allow_empty=True)
        return list(
            dict.fromkeys(name.strip() for name in output.splitlines() if name.strip())
        )

    def _read_player(self, name: str) -> PlayerState | None:
        output = self._run(
            "--player",
            name,
            "metadata",
            "--format",
            self.METADATA_FORMAT,
            allow_empty=True,
        )

        fields = output.split(self.SEPARATOR, maxsplit=5)

        if len(fields) != 6:
            status = self._run(
                "--player",
                name,
                "status",
                allow_empty=True,
            )

            if not status:
                return None

            fields = [status, "", "", "0", "", "remote-c-end"]

        try:
            duration_us = int(float(fields[3] or 0))
        except ValueError:
            duration_us = 0

        capabilities = self._read_capabilities(name)
        base_name = name.split(".instance", maxsplit=1)[0]
        label = base_name.replace("-", " ").replace("_", " ").title()

        return PlayerState(
            name=name,
            label=label,
            status=fields[0] or "Stopped",
            title=fields[1],
            artist=fields[2],
            art_url=fields[4],
            duration_us=max(0, duration_us),
            can_play=capabilities["CanPlay"],
            can_pause=capabilities["CanPause"],
            can_previous=capabilities["CanGoPrevious"],
            can_next=capabilities["CanGoNext"],
            can_seek=capabilities["CanSeek"],
        )

    @staticmethod
    def _read_capabilities(name: str) -> dict[str, bool]:
        properties = (
            "CanControl",
            "CanPlay",
            "CanPause",
            "CanGoPrevious",
            "CanGoNext",
            "CanSeek",
        )
        fallback = {property_name: False for property_name in properties}

        try:
            result = subprocess.run(
                [
                    "busctl",
                    "--user",
                    "get-property",
                    f"org.mpris.MediaPlayer2.{name}",
                    "/org/mpris/MediaPlayer2",
                    "org.mpris.MediaPlayer2.Player",
                    *properties,
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return fallback

        if result.returncode != 0:
            return fallback

        values = [
            line.split(maxsplit=1)[1].casefold() == "true"
            for line in result.stdout.splitlines()
            if line.startswith("b ")
        ]

        if len(values) != len(properties):
            return fallback

        capabilities = dict(zip(properties, values, strict=True))

        if not capabilities["CanControl"]:
            return fallback

        return capabilities

    @staticmethod
    def _run(*arguments: str, allow_empty: bool = False) -> str:
        try:
            result = subprocess.run(
                ["playerctl", *arguments],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except FileNotFoundError as error:
            raise MediaControlError("playerctl no está disponible") from error
        except subprocess.TimeoutExpired as error:
            raise MediaControlError("playerctl tardó demasiado en responder") from error

        if result.returncode != 0:
            if allow_empty:
                return ""

            message = result.stderr.strip() or "playerctl devolvió un error"
            raise MediaControlError(message)

        return result.stdout.strip()
