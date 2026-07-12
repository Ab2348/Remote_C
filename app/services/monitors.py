import asyncio
import logging
import os
from contextlib import suppress

from app.services.audio_routing import AudioRoutingError, audio_routing
from app.services.brightness import BrightnessControlError
from app.services.controller import controller
from app.services.events import event_hub
from app.services.media import MediaControlError
from app.services.volume import VolumeControlError


logger = logging.getLogger(__name__)


class SystemEventMonitors:
    BRIGHTNESS_INTERVAL_SECONDS = 30
    DEBOUNCE_SECONDS = 0.2
    RESTART_DELAY_SECONDS = 2

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._pending_refreshes: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        if self._tasks:
            return

        self._tasks = [
            asyncio.create_task(
                self._supervise("pactl", self._watch_pipewire),
                name="remote-c-pactl-monitor",
            ),
            asyncio.create_task(
                self._supervise("playerctl", self._watch_media),
                name="remote-c-playerctl-monitor",
            ),
            asyncio.create_task(
                self._watch_brightness(),
                name="remote-c-brightness-monitor",
            ),
        ]

    async def stop(self) -> None:
        for task in (*self._tasks, *self._pending_refreshes.values()):
            task.cancel()

        await asyncio.gather(
            *self._tasks,
            *self._pending_refreshes.values(),
            return_exceptions=True,
        )
        self._tasks.clear()
        self._pending_refreshes.clear()

    async def _supervise(self, name: str, watcher) -> None:
        while True:
            try:
                await watcher()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("El observador %s terminó inesperadamente", name)

            await asyncio.sleep(self.RESTART_DELAY_SECONDS)

    async def _watch_pipewire(self) -> None:
        environment = os.environ.copy()
        environment["LC_ALL"] = "C"
        process = await asyncio.create_subprocess_exec(
            "pactl",
            "subscribe",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=environment,
        )

        try:
            assert process.stdout is not None
            async for raw_line in process.stdout:
                if not event_hub.has_subscribers:
                    continue

                line = raw_line.decode(errors="replace").lower()
                if any(
                    subject in line
                    for subject in ("sink", "server", "card", "client")
                ):
                    self._schedule_refresh("pipewire")

            await process.wait()
        finally:
            await self._terminate(process)

    async def _watch_media(self) -> None:
        process = await asyncio.create_subprocess_exec(
            "playerctl",
            "--all-players",
            "--follow",
            "metadata",
            "--format",
            "{{playerName}}|{{status}}|{{xesam:title}}|{{xesam:artist}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        try:
            assert process.stdout is not None
            async for _ in process.stdout:
                if event_hub.has_subscribers:
                    self._schedule_refresh("media")

            await process.wait()
        finally:
            await self._terminate(process)

    async def _watch_brightness(self) -> None:
        while True:
            await asyncio.sleep(self.BRIGHTNESS_INTERVAL_SECONDS)

            if not event_hub.has_subscribers:
                continue

            try:
                state = await asyncio.to_thread(controller.get_brightness_state)
                await event_hub.publish("brightness", state)
            except BrightnessControlError:
                logger.exception("No se pudo actualizar el brillo")

    def _schedule_refresh(self, kind: str) -> None:
        current = self._pending_refreshes.get(kind)
        if current is not None:
            current.cancel()

        task = asyncio.create_task(self._publish_after_delay(kind))
        self._pending_refreshes[kind] = task

        def clear(completed: asyncio.Task) -> None:
            if self._pending_refreshes.get(kind) is completed:
                self._pending_refreshes.pop(kind, None)

        task.add_done_callback(clear)

    async def _publish_after_delay(self, kind: str) -> None:
        await asyncio.sleep(self.DEBOUNCE_SECONDS)

        if not event_hub.has_subscribers:
            return

        try:
            if kind == "media":
                state = await asyncio.to_thread(controller.get_media_state)
                await event_hub.publish("media", state)
                return

            volume_state, routing_state = await asyncio.gather(
                asyncio.to_thread(controller.get_volume_state),
                asyncio.to_thread(audio_routing.get_state),
            )
            await event_hub.publish("volume", volume_state)
            await event_hub.publish("audio-routing", routing_state)
        except (
            AudioRoutingError,
            MediaControlError,
            VolumeControlError,
        ):
            logger.exception("No se pudo publicar el cambio de %s", kind)

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return

        process.terminate()
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=1)
            return

        process.kill()
        await process.wait()


system_event_monitors = SystemEventMonitors()
