from app.services.simulated import controller as simulated_controller
from app.services.volume import WpctlVolumeService


class RemoteController:
    def __init__(self) -> None:
        self._simulated = simulated_controller
        self._volume = WpctlVolumeService()

    def get_state(self) -> dict:
        state = self._simulated.get_state()
        state.update(self._volume.get_state())
        return state

    def change_volume(self, action: str) -> dict:
        state = self._simulated.get_state()
        state.update(self._volume.change(action))
        return state

    def control_media(self, action: str) -> dict:
        self._simulated.control_media(action)
        return self.get_state()

    def change_brightness(self, action: str) -> dict:
        self._simulated.change_brightness(action)
        return self.get_state()


controller = RemoteController()