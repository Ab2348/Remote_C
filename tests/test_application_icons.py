import tempfile
import unittest
from pathlib import Path

from app.services.application_icons import (
    ApplicationIconError,
    ApplicationIconService,
)


class ApplicationIconServiceTests(unittest.TestCase):
    def test_resolves_a_common_application_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "hicolor"
            icon = root / "128x128/apps/brave-browser.svg"
            icon.parent.mkdir(parents=True)
            icon.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
            service = ApplicationIconService(
                icon_roots=(root,),
                pixmap_roots=(Path(directory) / "pixmaps",),
            )

            path, media_type = service.resolve("brave")

            self.assertEqual(path, icon.resolve())
            self.assertEqual(media_type, "image/svg+xml")

    def test_rejects_names_that_could_escape_the_icon_directories(self) -> None:
        service = ApplicationIconService()

        with self.assertRaisesRegex(ApplicationIconError, "no es válido"):
            service.resolve("../../passwd")

    def test_raises_a_clean_error_when_no_icon_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = ApplicationIconService(
                icon_roots=(root,),
                pixmap_roots=(root,),
            )

            with self.assertRaisesRegex(ApplicationIconError, "No hay un icono"):
                service.resolve("unknown-player")


if __name__ == "__main__":
    unittest.main()
