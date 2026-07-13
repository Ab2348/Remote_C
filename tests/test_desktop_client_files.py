import configparser
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class DesktopEntryTests(unittest.TestCase):
    def test_desktop_entry_matches_application_id(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(
            ROOT / "desktop" / "io.github.ab2348.RemoteC.desktop",
            encoding="utf-8",
        )
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Type"], "Application")
        self.assertEqual(entry["Exec"], "remote-c-client")
        self.assertEqual(entry["Icon"], "io.github.ab2348.RemoteC")
        self.assertEqual(entry["StartupWMClass"], "io.github.ab2348.RemoteC")


class WaybarModuleTests(unittest.TestCase):
    def test_waybar_module_launches_the_desktop_entry(self):
        path = ROOT / "deploy" / "waybar" / "custom-remote-c.jsonc"
        module = json.loads(path.read_text(encoding="utf-8"))
        config = module["custom/remote-c"]
        self.assertEqual(
            config["on-click"],
            "gtk-launch io.github.ab2348.RemoteC",
        )


if __name__ == "__main__":
    unittest.main()
