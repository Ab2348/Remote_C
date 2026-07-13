import tempfile
import unittest
from pathlib import Path

import importlib.util


MODULE_PATH = Path(__file__).parents[1] / "deploy" / "configure-waybar.py"
SPEC = importlib.util.spec_from_file_location("configure_waybar", MODULE_PATH)
configure_waybar = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(configure_waybar)


LAYOUT = '''{
  "group/rightbox#main": {
    "orientation": "inherit",
    "modules": [
      "custom/updates",
      "pulseaudio"
    ]
  }
}
'''


class WaybarLayoutTests(unittest.TestCase):
    def test_adds_remote_c_before_updates(self):
        updated = configure_waybar.add_layout_module(LAYOUT)
        self.assertLess(
            updated.index('"custom/remote-c"'),
            updated.index('"custom/updates"'),
        )

    def test_adding_module_is_idempotent(self):
        once = configure_waybar.add_layout_module(LAYOUT)
        twice = configure_waybar.add_layout_module(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count('"custom/remote-c"'), 1)

    def test_removes_only_remote_c(self):
        configured = configure_waybar.add_layout_module(LAYOUT)
        restored = configure_waybar.remove_layout_module(configured)
        self.assertEqual(restored, LAYOUT)

    def test_rejects_an_unknown_layout(self):
        with self.assertRaises(configure_waybar.ConfigurationError):
            configure_waybar.add_layout_module('{"modules": []}')


class WaybarStyleTests(unittest.TestCase):
    def test_style_round_trip(self):
        initial = "window#waybar { background: transparent; }\n"
        configured = configure_waybar.add_style(initial)
        self.assertIn("#custom-remote-c", configured)
        self.assertEqual(configure_waybar.add_style(configured), configured)
        restored = configure_waybar.remove_style(configured)
        self.assertEqual(restored, initial)


class WaybarFileUpdateTests(unittest.TestCase):
    def test_update_creates_a_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.jsonc"
            path.write_text(LAYOUT, encoding="utf-8")
            backup = configure_waybar.update_file(
                path,
                configure_waybar.add_layout_module,
            )
            self.assertIsNotNone(backup)
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.read_text(encoding="utf-8"), LAYOUT)


if __name__ == "__main__":
    unittest.main()
