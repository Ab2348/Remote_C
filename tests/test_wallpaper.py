import os
import tempfile
import unittest
from pathlib import Path

from app.services.wallpaper import HydeWallpaperService, WallpaperError


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"remote-c"


def write_image(path: Path, payload: bytes = PNG_HEADER) -> Path:
    path.write_bytes(payload)
    return path


class HydeWallpaperServiceTests(unittest.TestCase):
    def test_prefers_hyde_thumbnail_over_the_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            original = write_image(cache / "original.png")
            thumbnail = write_image(cache / "cached.thmb")
            (cache / "wall.set").symlink_to(original)
            (cache / "wall.thmb").symlink_to(thumbnail)
            service = HydeWallpaperService(cache)

            asset = service.get_asset()

            self.assertEqual(asset.path, thumbnail)
            self.assertEqual(asset.media_type, "image/png")

    def test_frontend_bootstraps_the_last_wallpaper_without_a_first_fade(self) -> None:
        static = Path(__file__).parents[1] / "app" / "static"
        script = (static / "wallpaper.js").read_text(encoding="utf-8")
        styles = (static / "shell.css").read_text(encoding="utf-8")

        self.assertIn('STORAGE_KEY = "remote-c:last-wallpaper"', script)
        self.assertIn("readCachedWallpaper()", script)
        self.assertIn("rememberWallpaper(state)", script)
        self.assertIn('classList.add("is-initial-paint")', script)
        self.assertIn(".wallpaper-background.is-initial-paint", styles)
        self.assertIn("transition: none", styles)

    def test_uses_the_original_when_thumbnail_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            original = write_image(cache / "original.png")
            (cache / "wall.set").symlink_to(original)
            service = HydeWallpaperService(cache)

            self.assertEqual(service.get_asset().path, original)

    def test_state_exposes_only_a_versioned_server_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            thumbnail = write_image(cache / "private-wallpaper.thmb")
            (cache / "wall.thmb").symlink_to(thumbnail)
            service = HydeWallpaperService(cache)

            state = service.get_state()

            self.assertTrue(state["available"])
            self.assertEqual(len(state["revision"]), 20)
            self.assertEqual(
                state["url"],
                f"/api/wallpaper/current?v={state['revision']}",
            )
            self.assertNotIn(str(cache), str(state))

    def test_revision_changes_when_hyde_replaces_the_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            first = write_image(cache / "first.thmb")
            second = write_image(cache / "second.thmb", PNG_HEADER + b"2")
            link = cache / "wall.thmb"
            link.symlink_to(first)
            service = HydeWallpaperService(cache)
            first_revision = service.get_asset().revision

            link.unlink()
            link.symlink_to(second)
            second_revision = service.get_asset().revision

            self.assertNotEqual(first_revision, second_revision)

    def test_rejects_a_stale_versioned_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            thumbnail = write_image(cache / "cached.thmb")
            (cache / "wall.thmb").symlink_to(thumbnail)
            service = HydeWallpaperService(cache)

            with self.assertRaisesRegex(WallpaperError, "cambió"):
                service.get_asset("0" * 20)

    def test_ignores_unsupported_or_oversized_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            invalid = write_image(cache / "invalid.thmb", b"not-an-image")
            (cache / "wall.thmb").symlink_to(invalid)
            service = HydeWallpaperService(cache)

            self.assertFalse(service.get_state()["available"])

            write_image(invalid)
            os.truncate(invalid, service.MAX_FILE_SIZE + 1)
            self.assertFalse(service.get_state()["available"])


if __name__ == "__main__":
    unittest.main()
