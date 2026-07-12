import re
import subprocess


class VolumeControlError(RuntimeError):
    pass


class WpctlVolumeService:
    SINK = "@DEFAULT_AUDIO_SINK@"
    VOLUME_PATTERN = re.compile(r"Volume:\s+([0-9]*\.?[0-9]+)")

    def get_state(self) -> dict:
        output = self._run("get-volume", self.SINK)
        match = self.VOLUME_PATTERN.search(output)

        if match is None:
            raise VolumeControlError(
                "No se pudo interpretar el volumen devuelto por wpctl"
            )

        volume = round(float(match.group(1)) * 100)

        return {
            "volume": volume,
            "muted": "[MUTED]" in output,
        }

    def change(self, action: str) -> dict:
        if action == "up":
            self._run(
                "set-volume",
                "--limit",
                "1.0",
                self.SINK,
                "5%+",
            )
        elif action == "down":
            self._run(
                "set-volume",
                self.SINK,
                "5%-",
            )
        elif action == "mute":
            self._run(
                "set-mute",
                self.SINK,
                "toggle",
            )
        else:
            raise VolumeControlError("Acción de volumen no permitida")

        return self.get_state()

    def set_volume(self, volume: int) -> dict:
        if not 0 <= volume <= 100:
            raise VolumeControlError(
                "El volumen debe estar entre 0 y 100"
            )

        self._run(
            "set-volume",
            "--limit",
            "1.0",
            self.SINK,
            f"{volume}%",
        )
        return self.get_state()

    @staticmethod
    def _run(*arguments: str) -> str:
        try:
            result = subprocess.run(
                ["wpctl", *arguments],
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
        except FileNotFoundError as error:
            raise VolumeControlError("wpctl no está disponible") from error
        except subprocess.TimeoutExpired as error:
            raise VolumeControlError(
                "wpctl tardó demasiado en responder"
            ) from error
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip() or "wpctl devolvió un error"
            raise VolumeControlError(message) from error

        return result.stdout.strip()
