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


class HyprlandRuleTests(unittest.TestCase):
    def test_remote_c_opens_floating_and_remembers_its_size(self):
        rule = (
            ROOT / "deploy" / "hypr" / "remote-c-client.conf"
        ).read_text(encoding="utf-8")
        match = r"match:class ^(io\.github\.ab2348\.RemoteC)$"

        self.assertIn(f"windowrule = float on, {match}", rule)
        self.assertIn(f"windowrule = persistent_size on, {match}", rule)

    def test_install_and_uninstall_manage_the_hyprland_rule(self):
        install_script = (
            ROOT / "deploy" / "install-desktop-client.sh"
        ).read_text(encoding="utf-8")
        uninstall_script = (
            ROOT / "deploy" / "uninstall-desktop-client.sh"
        ).read_text(encoding="utf-8")
        target = "remote-c-client-persistent-size.conf"

        self.assertIn(target, install_script)
        self.assertIn('install -Dm644 "$hypr_source" "$hypr_target"', install_script)
        self.assertIn(target, uninstall_script)
        self.assertIn('"$hypr_target"', uninstall_script)


if __name__ == "__main__":
    unittest.main()
