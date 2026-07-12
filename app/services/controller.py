from app.services.media import PlayerctlMediaService
from app.services.volume import WpctlVolumeService
from app.services.brightness import DdcutilBrightnessService


class RemoteController:
    def __init__(self) -> None:
        self._volume = WpctlVolumeService()
        self._media = PlayerctlMediaService()
        self._brightness = DdcutilBrightnessService()

    def get_state(self) -> dict:
        state = {}
        state.update(self.get_volume_state())
        state.update(self.get_media_state())
        state.update(self.get_brightness_state())
        return state

    def get_volume_state(self) -> dict:
        return self._volume.get_state()

    def get_media_state(self) -> dict:
        return self._media.get_state()

    def get_brightness_state(self) -> dict:
        return self._brightness.get_state()

    def change_volume(self, action: str) -> dict:
        return self._volume.change(action)

    def set_volume(self, value: int) -> dict:
        return self._volume.set_volume(value)

    def control_media(self, action: str) -> dict:
        return self._media.control(action)

    def change_brightness(self, action: str) -> dict:
        return self._brightness.change(action)

    def get_media_sessions(self) -> dict:
        return self._media.get_sessions()

    def control_media_session(
        self,
        player_name: str,
        action: str,
    ) -> dict:
        return self._media.control_session(player_name, action)


controller = RemoteController()
