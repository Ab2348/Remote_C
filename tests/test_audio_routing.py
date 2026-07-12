import unittest
from unittest.mock import Mock

from app.services.audio_routing import (
    AudioRoutingError,
    AudioSink,
    AudioStream,
    PactlAudioRoutingService,
)


def stream(
    index: int,
    *,
    sink: int = 1,
    application: str = "Brave",
    icon_name: str = "brave-browser",
    binary: str = "brave",
    pid: str = "7003",
    media: str = "Playback",
    volume: int = 50,
    muted: bool = False,
    corked: bool = False,
) -> AudioStream:
    return AudioStream(
        index=index,
        sink=sink,
        application=application,
        icon_name=icon_name,
        media=media,
        binary=binary,
        pid=pid,
        volume=volume,
        muted=muted,
        corked=corked,
    )


class AudioApplicationSerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sinks = {
            1: AudioSink(1, "razer", "Razer Barracuda X", "RUNNING", True),
            2: AudioSink(2, "huawei", "HUAWEI Sound Joy", "IDLE", False),
        }

    def test_groups_streams_by_binary_and_reports_mixed_state(self) -> None:
        applications = PactlAudioRoutingService._serialize_applications(
            [
                stream(94, media="YouTube", volume=40),
                stream(294, media="Spotify web", volume=60, muted=True),
            ],
            self.sinks,
        )

        self.assertEqual(len(applications), 1)
        application = applications[0]
        self.assertEqual(application["id"], "brave")
        self.assertEqual(application["icon_name"], "brave-browser")
        self.assertEqual(application["stream_indexes"], [94, 294])
        self.assertEqual(application["stream_count"], 2)
        self.assertEqual(application["volume"], 50)
        self.assertTrue(application["mixed_volume"])
        self.assertFalse(application["muted"])
        self.assertTrue(application["partially_muted"])
        self.assertEqual(application["output_name"], "razer")
        self.assertEqual(application["media"], ["YouTube", "Spotify web"])
        self.assertTrue(application["playing"])
        self.assertEqual(application["playback_status"], "playing")

    def test_marks_a_fully_corked_application_as_paused(self) -> None:
        applications = PactlAudioRoutingService._serialize_applications(
            [stream(1, corked=True), stream(2, corked=True)],
            self.sinks,
        )

        self.assertFalse(applications[0]["playing"])
        self.assertEqual(applications[0]["playback_status"], "paused")

    def test_marks_an_application_routed_to_multiple_outputs(self) -> None:
        applications = PactlAudioRoutingService._serialize_applications(
            [stream(1, sink=1), stream(2, sink=2)],
            self.sinks,
        )

        self.assertIsNone(applications[0]["output_name"])
        self.assertEqual(applications[0]["output_label"], "Varias salidas")

    def test_keeps_distinct_applications_separate(self) -> None:
        applications = PactlAudioRoutingService._serialize_applications(
            [
                stream(1),
                stream(
                    2,
                    application="Spotify",
                    binary="",
                    pid="9000",
                    media="Spotify",
                ),
            ],
            self.sinks,
        )

        self.assertEqual(
            [application["application"] for application in applications],
            ["Brave", "Spotify"],
        )


class AudioApplicationActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PactlAudioRoutingService()
        self.service._get_streams = Mock(return_value=[stream(1), stream(2)])
        self.service.get_state = Mock(return_value={"updated": True})
        self.service._run = Mock(return_value="")

    def test_sets_volume_for_every_current_stream(self) -> None:
        result = self.service.set_streams_volume([1, 2], 35)

        self.assertEqual(result, {"updated": True})
        self.assertEqual(
            self.service._run.call_args_list,
            [
                unittest.mock.call("set-sink-input-volume", "1", "35%"),
                unittest.mock.call("set-sink-input-volume", "2", "35%"),
            ],
        )

    def test_uses_explicit_mute_state_for_the_whole_application(self) -> None:
        self.service.set_streams_mute([1, 2], True)

        self.assertEqual(
            self.service._run.call_args_list,
            [
                unittest.mock.call("set-sink-input-mute", "1", "1"),
                unittest.mock.call("set-sink-input-mute", "2", "1"),
            ],
        )

    def test_tolerates_one_stale_index_if_the_application_still_exists(self) -> None:
        self.service.set_streams_volume([1, 999], 25)

        self.service._run.assert_called_once_with(
            "set-sink-input-volume",
            "1",
            "25%",
        )

    def test_rejects_an_application_with_no_current_streams(self) -> None:
        with self.assertRaisesRegex(AudioRoutingError, "ya no está reproduciendo"):
            self.service.set_streams_volume([999], 25)


if __name__ == "__main__":
    unittest.main()
