import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock


class BrightnessControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class Display:
    key: str
    bus: int
    label: str


class DdcutilBrightnessService:
    VCP_CODE = "10"
    CACHE_SECONDS = 2
    VALUE_PATTERN = re.compile(r"VCP 10 C (\d+) (\d+)")

    DISPLAYS = (
        Display(key="display_1", bus=3, label="LG UltraGear"),
        Display(key="display_2", bus=6, label="GA271"),
    )

    def __init__(self) -> None:
        self._lock = RLock()
        self._cache: dict[str, int] = {}
        self._last_refresh = 0.0

    def get_state(self) -> dict:
        with self._lock:
            cache_expired = (
                not self._cache
                or time.monotonic() - self._last_refresh >= self.CACHE_SECONDS
            )

            if cache_expired:
                self._refresh()

            return self._serialize_state()

    def change(self, action: str) -> dict:
        changes = {
            "up": ("+", 10),
            "down": ("-", 10),
        }

        change = changes.get(str(action))

        if change is None:
            raise BrightnessControlError(
                "Acción de brillo no permitida"
            )

        operator, amount = change

        with self._lock:
            try:
                self._run_parallel(
                    lambda display: self._run(
                        "--bus",
                        str(display.bus),
                        "setvcp",
                        self.VCP_CODE,
                        operator,
                        str(amount),
                    )
                )
            except BrightnessControlError:
                self._last_refresh = 0.0
                raise

            # El cambio de DDC/CI es relativo al valor físico del monitor.
            # Releer evita responder con un cálculo basado en una caché antigua
            # cuando el brillo cambió mediante teclas o herramientas externas.
            self._refresh()

            return self._serialize_state()

    def change_display(self, display_key: str, action: str) -> dict:
        changes = {
            "up": ("+", 10),
            "down": ("-", 10),
        }
        change = changes.get(str(action))

        if change is None:
            raise BrightnessControlError("Acción de brillo no permitida")

        display = self._find_display(display_key)
        operator, amount = change

        with self._lock:
            try:
                self._run(
                    "--bus",
                    str(display.bus),
                    "setvcp",
                    self.VCP_CODE,
                    operator,
                    str(amount),
                )
            except BrightnessControlError:
                self._last_refresh = 0.0
                raise

            self._refresh()
            return self._serialize_state()

    def set_display(self, display_key: str, brightness: int) -> dict:
        if not 0 <= brightness <= 100:
            raise BrightnessControlError(
                "El brillo debe estar entre 0 y 100"
            )

        display = self._find_display(display_key)

        with self._lock:
            try:
                self._run(
                    "--bus",
                    str(display.bus),
                    "setvcp",
                    self.VCP_CODE,
                    str(brightness),
                )
            except BrightnessControlError:
                self._last_refresh = 0.0
                raise

            self._refresh()
            return self._serialize_state()

    def _serialize_state(self) -> dict:
        return {
            "brightness": self._cache.copy(),
            "brightness_displays": [
                {
                    "key": display.key,
                    "label": display.label,
                    "brightness": self._cache[display.key],
                }
                for display in self.DISPLAYS
                if display.key in self._cache
            ],
        }

    def _find_display(self, display_key: str) -> Display:
        for display in self.DISPLAYS:
            if display.key == display_key:
                return display

        raise BrightnessControlError(
            "El monitor seleccionado no está disponible"
        )

    def _refresh(self) -> None:
        results = self._run_parallel(self._read_display)
        self._cache = {
            display.key: brightness
            for display, brightness in results
        }
        self._last_refresh = time.monotonic()

    def _read_display(self, display: Display) -> tuple[Display, int]:
        output = self._run(
            "--bus",
            str(display.bus),
            "getvcp",
            self.VCP_CODE,
            "--terse",
        )

        match = self.VALUE_PATTERN.search(output)

        if match is None:
            raise BrightnessControlError(
                f"No se pudo interpretar el brillo del bus {display.bus}"
            )

        current = int(match.group(1))
        maximum = int(match.group(2))

        if maximum <= 0:
            raise BrightnessControlError(
                f"Valor máximo inválido en el bus {display.bus}"
            )

        percentage = round(current / maximum * 100)
        return display, percentage

    def _run_parallel(self, operation):
        with ThreadPoolExecutor(
            max_workers=len(self.DISPLAYS)
        ) as executor:
            futures = [
                executor.submit(operation, display)
                for display in self.DISPLAYS
            ]

            return [future.result() for future in futures]

    @staticmethod
    def _run(*arguments: str) -> str:
        try:
            result = subprocess.run(
                ["ddcutil", *arguments],
                capture_output=True,
                text=True,
                timeout=6,
            )
        except FileNotFoundError as error:
            raise BrightnessControlError(
                "ddcutil no está disponible"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise BrightnessControlError(
                "ddcutil tardó demasiado en responder"
            ) from error

        if result.returncode != 0:
            message = result.stderr.strip() or "ddcutil devolvió un error"
            raise BrightnessControlError(message)

        return result.stdout.strip()
