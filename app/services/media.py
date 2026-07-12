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
    duration_us: int

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
        )
    )

    SESSION_COMMANDS = {
        "play_pause": ("play-pause",),
        "previous": ("previous",),
        "next": ("next",),
        "seek_backward": ("position", "10-"),
        "seek_forward": ("position", "10+"),
    }

    def get_state(self) -> dict:
        player = self._get_active_player()

        if player is None:
            return {
                "playing": False,
                "playback_status": "stopped",
                "current_track": "Sin reproducción",
            }

        return {
            "playing": player.status.casefold() == "playing",
            "playback_status": player.status.casefold(),
            "current_track": player.current_track,
        }

    def get_sessions(self) -> dict:
        return {
            "players": [
                {
                    "name": player.name,
                    "label": player.label,
                    "status": player.status.casefold(),
                    "playing": player.status.casefold() == "playing",
                    "title": player.title,
                    "artist": player.artist,
                    "current_track": player.current_track,
                    "duration_seconds": round(player.duration_us / 1_000_000),
                }
                for player in self._get_players()
            ]
        }

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

        self._run("--player", player.name, *command)
        return self.get_state()

    def control_session(self, player_name: str, action: str) -> dict:
        available_players = self._list_player_names()

        if player_name not in available_players:
            raise MediaControlError(
                "El reproductor seleccionado ya no está disponible"
            )

        command = self.SESSION_COMMANDS.get(str(action))

        if command is None:
            raise MediaControlError("Acción multimedia no permitida")

        self._run("--player", player_name, *command)
        return self.get_sessions()

    def _get_active_player(self) -> PlayerState | None:
        players = self._get_players()

        if not players:
            return None

        return next(
            (
                player
                for player in players
                if player.status.casefold() == "playing"
            ),
            players[0],
        )

    def _get_players(self) -> list[PlayerState]:
        players: list[PlayerState] = []

        for name in self._list_player_names():
            player = self._read_player(name)

            if player is not None:
                players.append(player)

        return players

    def _list_player_names(self) -> list[str]:
        output = self._run("--list-all", allow_empty=True)
        return list(dict.fromkeys(
            name.strip()
            for name in output.splitlines()
            if name.strip()
        ))

    def _read_player(self, name: str) -> PlayerState | None:
        output = self._run(
            "--player",
            name,
            "metadata",
            "--format",
            self.METADATA_FORMAT,
            allow_empty=True,
        )

        fields = output.split(self.SEPARATOR, maxsplit=3)

        if len(fields) != 4:
            status = self._run(
                "--player",
                name,
                "status",
                allow_empty=True,
            )

            if not status:
                return None

            fields = [status, "", "", "0"]

        try:
            duration_us = int(float(fields[3] or 0))
        except ValueError:
            duration_us = 0

        base_name = name.split(".instance", maxsplit=1)[0]
        label = base_name.replace("-", " ").replace("_", " ").title()

        return PlayerState(
            name=name,
            label=label,
            status=fields[0] or "Stopped",
            title=fields[1],
            artist=fields[2],
            duration_us=max(0, duration_us),
        )

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
            raise MediaControlError(
                "playerctl tardó demasiado en responder"
            ) from error

        if result.returncode != 0:
            if allow_empty:
                return ""

            message = result.stderr.strip() or "playerctl devolvió un error"
            raise MediaControlError(message)

        return result.stdout.strip()
