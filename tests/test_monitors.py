import asyncio
import unittest
from unittest.mock import patch

from app.services.audio_routing import audio_routing
from app.services.controller import controller
from app.services.monitors import SystemEventMonitors
from app.services.events import event_hub


class PactlEventClassificationTests(unittest.TestCase):
    def test_client_events_are_ignored(self) -> None:
        classify = SystemEventMonitors._classify_pactl_event

        self.assertEqual(classify("Event 'new' on client #2437"), ())
        self.assertEqual(classify("Event 'change' on client #2437"), ())
        self.assertEqual(classify("Event 'remove' on client #2437"), ())

    def test_sink_volume_change_only_refreshes_volume(self) -> None:
        result = SystemEventMonitors._classify_pactl_event(
            "Event 'change' on sink #312"
        )

        self.assertEqual(result, ("volume",))

    def test_sink_input_change_refreshes_routing(self) -> None:
        result = SystemEventMonitors._classify_pactl_event(
            "Event 'change' on sink-input #94"
        )

        self.assertEqual(result, ("routing",))

    def test_new_sink_refreshes_volume_and_routing(self) -> None:
        result = SystemEventMonitors._classify_pactl_event(
            "Event 'new' on sink #312"
        )

        self.assertEqual(result, ("volume", "routing"))

    def test_server_and_card_events_have_scoped_refreshes(self) -> None:
        classify = SystemEventMonitors._classify_pactl_event

        self.assertEqual(
            classify("Event 'change' on server #4294967295"),
            ("volume", "routing"),
        )
        self.assertEqual(
            classify("Event 'change' on card #311"),
            ("routing",),
        )


class RefreshCoalescingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.monitor = SystemEventMonitors()
        self.monitor.DEBOUNCE_SECONDS = 0.01
        self.monitor._refresh_events = {"volume": asyncio.Event()}
        self.worker = asyncio.create_task(
            self.monitor._refresh_worker("volume")
        )

    async def asyncTearDown(self) -> None:
        self.worker.cancel()
        await asyncio.gather(self.worker, return_exceptions=True)

    async def test_burst_is_coalesced_into_one_refresh(self) -> None:
        refreshed = asyncio.Event()
        calls = 0

        async def publish(_kind: str) -> None:
            nonlocal calls
            calls += 1
            refreshed.set()

        self.monitor._publish_refresh = publish

        async with event_hub.subscribe():
            self.monitor._schedule_refresh("volume")
            self.monitor._schedule_refresh("volume")
            self.monitor._schedule_refresh("volume")

            await asyncio.wait_for(refreshed.wait(), timeout=0.2)
        self.assertEqual(calls, 1)

    async def test_event_during_refresh_does_not_cancel_active_work(self) -> None:
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        second_finished = asyncio.Event()
        calls = 0

        async def publish(_kind: str) -> None:
            nonlocal calls
            calls += 1

            if calls == 1:
                first_started.set()
                await release_first.wait()
            else:
                second_finished.set()

        self.monitor._publish_refresh = publish

        async with event_hub.subscribe():
            self.monitor._schedule_refresh("volume")
            await asyncio.wait_for(first_started.wait(), timeout=0.2)

            self.monitor._schedule_refresh("volume")
            await asyncio.sleep(0)
            self.assertFalse(self.worker.done())
            self.assertEqual(calls, 1)

            release_first.set()
            await asyncio.wait_for(second_finished.wait(), timeout=0.2)
        self.assertEqual(calls, 2)


class ScopedRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_volume_refresh_does_not_query_routing(self) -> None:
        monitor = SystemEventMonitors()
        volume_state = {"volume": 47, "muted": False}

        with (
            patch.object(
                controller,
                "get_volume_state",
                return_value=volume_state,
            ) as get_volume,
            patch.object(audio_routing, "get_state") as get_routing,
        ):
            async with event_hub.subscribe() as queue:
                await monitor._publish_refresh("volume")
                event_type, payload = await asyncio.wait_for(
                    queue.get(),
                    timeout=0.2,
                )

        self.assertEqual(event_type, "volume")
        self.assertEqual(payload, volume_state)
        get_volume.assert_called_once_with()
        get_routing.assert_not_called()

    async def test_routing_refresh_does_not_query_volume(self) -> None:
        monitor = SystemEventMonitors()
        routing_state = {"outputs": [], "applications": []}

        with (
            patch.object(controller, "get_volume_state") as get_volume,
            patch.object(
                audio_routing,
                "get_state",
                return_value=routing_state,
            ) as get_routing,
        ):
            async with event_hub.subscribe() as queue:
                await monitor._publish_refresh("routing")
                event_type, payload = await asyncio.wait_for(
                    queue.get(),
                    timeout=0.2,
                )

        self.assertEqual(event_type, "audio-routing")
        self.assertEqual(payload, routing_state)
        get_routing.assert_called_once_with()
        get_volume.assert_not_called()


if __name__ == "__main__":
    unittest.main()
