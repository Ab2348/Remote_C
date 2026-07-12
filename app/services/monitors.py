import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Literal

from app.services.audio_routing import AudioRoutingError, audio_routing
from app.services.brightness import BrightnessControlError
from app.services.controller import controller
from app.services.events import event_hub
from app.services.media import MediaControlError
from app.services.volume import VolumeControlError


logger = logging.getLogger(__name__)

RefreshKind = Literal["volume", "routing", "media"]
Watcher = Callable[[], Awaitable[None]]


class SystemEventMonitors:
    BRIGHTNESS_INTERVAL_SECONDS = 30
    DEBOUNCE_SECONDS = 0.2
    RESTART_DELAY_SECONDS = 2

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._refresh_events: dict[RefreshKind, asyncio.Event] = {}
        self._last_brightness_state: dict | None = None

    async def start(self) -> None:
        if self._tasks:
            return

        self._refresh_events = {
            kind: asyncio.Event()
            for kind in ("volume", "routing", "media")
        }
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
            *(
                asyncio.create_task(
                    self._refresh_worker(kind),
                    name=f"remote-c-{kind}-refresh",
                )
                for kind in self._refresh_events
            ),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._refresh_events.clear()
        self._last_brightness_state = None

    def record_brightness_state(self, state: dict) -> None:
        self._last_brightness_state = {
            key: state[key]
            for key in ("brightness", "brightness_displays")
            if key in state
        }

    async def _supervise(self, name: str, watcher: Watcher) -> None:
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

                line = raw_line.decode(errors="replace")
                for kind in self._classify_pactl_event(line):
                    self._schedule_refresh(kind)

            await process.wait()
        finally:
            await self._terminate(process)

    @staticmethod
    def _classify_pactl_event(line: str) -> tuple[RefreshKind, ...]:
        normalized = line.casefold()

        if " on sink-input " in normalized:
            return ("routing",)

        if " on sink " in normalized:
            if "event 'change'" in normalized:
                return ("volume",)

            return ("volume", "routing")

        if " on server " in normalized:
            return ("volume", "routing")

        if " on card " in normalized:
            return ("routing",)

        return ()

    async def _watch_media(self) -> None:
        process = await asyncio.create_subprocess_exec(
            "playerctl",
            "--all-players",
            "--follow",
            "metadata",
            "--format",
            "{{playerName}}|{{status}}|{{xesam:title}}|{{xesam:artist}}|{{mpris:artUrl}}",
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
                await self._publish_brightness_if_changed()
            except BrightnessControlError:
                logger.exception("No se pudo actualizar el brillo")

    async def _publish_brightness_if_changed(self) -> None:
        state = await asyncio.to_thread(controller.get_brightness_state)

        if state == self._last_brightness_state:
            return

        self._last_brightness_state = state
        await event_hub.publish("brightness", state)

    def _schedule_refresh(self, kind: RefreshKind) -> None:
        self._refresh_events[kind].set()

    async def _refresh_worker(self, kind: RefreshKind) -> None:
        event = self._refresh_events[kind]

        while True:
            await event.wait()
            event.clear()
            await asyncio.sleep(self.DEBOUNCE_SECONDS)

            while event.is_set():
                event.clear()
                await asyncio.sleep(self.DEBOUNCE_SECONDS)

            if event_hub.has_subscribers:
                await self._publish_refresh(kind)

    async def _publish_refresh(self, kind: RefreshKind) -> None:
        try:
            if kind == "volume":
                state = await asyncio.to_thread(controller.get_volume_state)
                await event_hub.publish("volume", state)
            elif kind == "routing":
                state = await asyncio.to_thread(audio_routing.get_state)
                await event_hub.publish("audio-routing", state)
            else:
                state = await asyncio.to_thread(controller.get_media_state)
                await event_hub.publish("media", state)
        except VolumeControlError:
            logger.exception("No se pudo publicar el cambio de volumen")
        except AudioRoutingError:
            logger.exception("No se pudo publicar el cambio de ruteo")
        except MediaControlError:
            logger.exception("No se pudo publicar el cambio multimedia")

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
