from app.services.media import PlayerctlMediaService
from app.services.simulated import controller as simulated_controller
from app.services.volume import WpctlVolumeService


class RemoteController:
    def __init__(self) -> None:
        self._simulated = simulated_controller
        self._volume = WpctlVolumeService()
        self._media = PlayerctlMediaService()

    def _compose_state(
        self,
        *,
        volume: dict | None = None,
        media: dict | None = None,
    ) -> dict:
        state = self._simulated.get_state()
        state.update(volume if volume is not None else self._volume.get_state())
        state.update(media if media is not None else self._media.get_state())
        return state

    def get_state(self) -> dict:
        return self._compose_state()

    def change_volume(self, action: str) -> dict:
        volume = self._volume.change(action)
        return self._compose_state(volume=volume)

    def control_media(self, action: str) -> dict:
        media = self._media.control(action)
        return self._compose_state(media=media)

    def change_brightness(self, action: str) -> dict:
        self._simulated.change_brightness(action)
        return self._compose_state()


controller = RemoteController()