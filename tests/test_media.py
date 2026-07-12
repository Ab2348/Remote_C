import hashlib
import unittest
from unittest.mock import Mock

from app.services.media import PlayerState, PlayerctlMediaService


def player(
    *,
    name: str = "spotify",
    status: str = "Playing",
    title: str = "Track",
    art_url: str = "https://example.com/cover.jpg",
) -> PlayerState:
    return PlayerState(
        name=name,
        label=name.title(),
        status=status,
        title=title,
        artist="Artist",
        art_url=art_url,
        duration_us=120_000_000,
        can_play=True,
        can_pause=True,
        can_previous=True,
        can_next=True,
        can_seek=True,
    )


class MediaArtworkTests(unittest.TestCase):
    def test_serializes_a_stable_artwork_id(self) -> None:
        state = PlayerctlMediaService._serialize_players([player()])[0]
        expected = hashlib.sha256(b"https://example.com/cover.jpg").hexdigest()[:12]

        self.assertEqual(state["artwork_id"], expected)

    def test_omits_artwork_id_when_the_player_has_no_cover(self) -> None:
        state = PlayerctlMediaService._serialize_players(
            [
                player(art_url=""),
            ]
        )[0]

        self.assertIsNone(state["artwork_id"])

    def test_reads_artwork_from_playerctl_metadata(self) -> None:
        service = PlayerctlMediaService()
        service._run = Mock(
            return_value=service.SEPARATOR.join(
                (
                    "Playing",
                    "Track",
                    "Artist",
                    "120000000",
                    "https://example.com/cover.jpg",
                    "remote-c-end",
                )
            )
        )
        service._read_capabilities = Mock(
            return_value={
                "CanPlay": True,
                "CanPause": True,
                "CanGoPrevious": True,
                "CanGoNext": True,
                "CanSeek": True,
            }
        )

        result = service._read_player("spotify")

        self.assertIsNotNone(result)
        self.assertEqual(result.art_url, "https://example.com/cover.jpg")

    def test_empty_artwork_keeps_the_rest_of_the_metadata(self) -> None:
        service = PlayerctlMediaService()
        service._run = Mock(
            return_value=service.SEPARATOR.join(
                (
                    "Paused",
                    "Track without cover",
                    "Artist",
                    "120000000",
                    "",
                    "remote-c-end",
                )
            )
        )
        service._read_capabilities = Mock(
            return_value={
                "CanPlay": True,
                "CanPause": True,
                "CanGoPrevious": False,
                "CanGoNext": False,
                "CanSeek": True,
            }
        )

        result = service._read_player("spotify")

        self.assertEqual(result.title, "Track without cover")
        self.assertEqual(result.artist, "Artist")
        self.assertEqual(result.art_url, "")

    def test_returns_artwork_only_for_an_available_player(self) -> None:
        service = PlayerctlMediaService()
        service._list_player_names = Mock(return_value=["spotify"])
        service._run = Mock(return_value="https://example.com/cover.jpg")

        self.assertEqual(
            service.get_artwork_url("spotify"),
            "https://example.com/cover.jpg",
        )


class ActivePlayerSelectionTests(unittest.TestCase):
    def test_keeps_the_last_controlled_player_after_it_is_paused(self) -> None:
        service = PlayerctlMediaService()
        service._preferred_player_name = "brave.instance7003"

        selected = service._select_active_player(
            [
                player(name="spotify", status="Paused", title="Otra canción"),
                player(
                    name="brave.instance7003",
                    status="Paused",
                    title="Canción pausada",
                ),
            ]
        )

        self.assertEqual(selected.name, "brave.instance7003")

    def test_a_playing_player_takes_priority_over_the_previous_selection(self) -> None:
        service = PlayerctlMediaService()
        service._preferred_player_name = "brave.instance7003"

        selected = service._select_active_player(
            [
                player(name="brave.instance7003", status="Paused"),
                player(name="spotify", status="Playing"),
            ]
        )

        self.assertEqual(selected.name, "spotify")
        self.assertEqual(service._preferred_player_name, "spotify")

    def test_session_control_updates_the_preferred_player(self) -> None:
        service = PlayerctlMediaService()
        service._list_player_names = Mock(return_value=["brave.instance7003"])
        service._run = Mock(return_value="")
        service.get_sessions = Mock(return_value={"players": []})

        service.control_session("brave.instance7003", "play_pause")

        self.assertEqual(service._preferred_player_name, "brave.instance7003")
        service._run.assert_called_once_with(
            "--player",
            "brave.instance7003",
            "play-pause",
        )


if __name__ == "__main__":
    unittest.main()
