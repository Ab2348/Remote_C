from app.services.media import PlayerctlMediaService
from app.services.simulated import controller as simulated_controller
from app.services.volume import WpctlVolumeService
from app.services.brightness import DdcutilBrightnessService


class RemoteController:
    def __init__(self) -> None:
        self._simulated = simulated_controller
        self._volume = WpctlVolumeService()
        self._media = PlayerctlMediaService()
        self._brightness = DdcutilBrightnessService()

    def _compose_state(
        self,
        *,
        volume: dict | None = None,
        media: dict | None = None,
        brightness: dict | None = None,
    ) -> dict:
        state = self._simulated.get_state()
        state.update(volume if volume is not None else self.get_volume_state())
        state.update(media if media is not None else self.get_media_state())
        state.update(
            brightness
            if brightness is not None
            else self.get_brightness_state()
        )
        return state

    def get_state(self) -> dict:
        return self._compose_state()

    def get_volume_state(self) -> dict:
        return self._volume.get_state()

    def get_media_state(self) -> dict:
        return self._media.get_state()

    def get_brightness_state(self) -> dict:
        return self._brightness.get_state()

    def change_volume(self, action: str) -> dict:
        volume = self._volume.change(action)
        return self._compose_state(volume=volume)

    def set_volume(self, value: int) -> dict:
        volume = self._volume.set_volume(value)
        return self._compose_state(volume=volume)

    def control_media(self, action: str) -> dict:
        media = self._media.control(action)
        return self._compose_state(media=media)

    def change_brightness(self, action: str) -> dict:
        brightness = self._brightness.change(action)
        return self._compose_state(brightness=brightness)

    def get_media_sessions(self) -> dict:
        return self._media.get_sessions()

    def control_media_session(
        self,
        player_name: str,
        action: str,
    ) -> dict:
        return self._media.control_session(player_name, action)


controller = RemoteController()
