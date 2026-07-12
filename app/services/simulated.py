from dataclasses import asdict, dataclass, field
from threading import Lock


@dataclass
class RemoteState:
    volume: int = 20
    muted: bool = False
    playing: bool = False
    current_track: str = "Sin reproducción"
    brightness: dict[str, int] = field(
        default_factory=lambda: {
            "display_1": 50,
            "display_2": 50,
        }
    )


class SimulatedController:
    def __init__(self) -> None:
        self._state = RemoteState()
        self._lock = Lock()

    def get_state(self) -> dict:
        with self._lock:
            return asdict(self._state)

    def change_volume(self, action: str) -> dict:
        with self._lock:
            if action == "up":
                self._state.volume = min(100, self._state.volume + 5)
            elif action == "down":
                self._state.volume = max(0, self._state.volume - 5)
            elif action == "mute":
                self._state.muted = not self._state.muted

            return asdict(self._state)

    def control_media(self, action: str) -> dict:
        with self._lock:
            if action == "play_pause":
                self._state.playing = not self._state.playing
            elif action == "next":
                self._state.current_track = "Pista siguiente (simulada)"
            elif action == "previous":
                self._state.current_track = "Pista anterior (simulada)"

            return asdict(self._state)

    def change_brightness(self, action: str) -> dict:
        with self._lock:
            change = 10 if action == "up" else -10

            for display in self._state.brightness:
                current = self._state.brightness[display]
                self._state.brightness[display] = max(
                    0, min(100, current + change)
                )

            return asdict(self._state)


controller = SimulatedController()