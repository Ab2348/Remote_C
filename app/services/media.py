import subprocess
from dataclasses import dataclass


class MediaControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlayerState:
    name: str
    status: str
    title: str
    artist: str


class PlayerctlMediaService:
    SEPARATOR = "\x1f"
    METADATA_FORMAT = SEPARATOR.join(
        (
            "{{playerName}}",
            "{{status}}",
            "{{xesam:title}}",
            "{{xesam:artist}}",
        )
    )

    def get_state(self) -> dict:
        player = self._get_active_player()

        if player is None:
            return {
                "playing": False,
                "playback_status": "stopped",
                "current_track": "Sin reproducción",
            }

        if player.title and player.artist:
            current_track = f"{player.title} — {player.artist}"
        else:
            current_track = player.title or player.artist or "Sin reproducción"

        return {
            "playing": player.status.casefold() == "playing",
            "playback_status": player.status.casefold(),
            "current_track": current_track,
        }

    def control(self, action: str) -> dict:
        player = self._get_active_player()

        if player is None:
            raise MediaControlError("No hay ningún reproductor disponible")

        commands = {
            "play_pause": "play-pause",
            "previous": "previous",
            "next": "next",
        }

        command = commands.get(str(action))

        if command is None:
            raise MediaControlError("Acción multimedia no permitida")

        self._run(
            "--player",
            player.name,
            command,
        )

        return self.get_state()

    def _get_active_player(self) -> PlayerState | None:
        output = self._run(
            "--all-players",
            "metadata",
            "--format",
            self.METADATA_FORMAT,
            allow_empty=True,
        )

        players: list[PlayerState] = []

        for line in output.splitlines():
            fields = line.split(self.SEPARATOR, maxsplit=3)

            if len(fields) != 4:
                continue

            players.append(
                PlayerState(
                    name=fields[0],
                    status=fields[1],
                    title=fields[2],
                    artist=fields[3],
                )
            )

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