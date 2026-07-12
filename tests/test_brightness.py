import unittest
from unittest.mock import Mock

from app.services.brightness import (
    BrightnessControlError,
    DdcutilBrightnessService,
)


class IndividualBrightnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DdcutilBrightnessService()
        self.service._cache = {
            "display_1": 70,
            "display_2": 60,
        }
        self.service._run = Mock(return_value="")
        self.service._refresh = Mock()

    def test_state_contains_display_metadata(self) -> None:
        state = self.service.get_state()

        self.assertEqual(state["brightness"]["display_1"], 70)
        self.assertEqual(
            state["brightness_displays"],
            [
                {
                    "key": "display_1",
                    "label": "LG UltraGear",
                    "brightness": 70,
                },
                {
                    "key": "display_2",
                    "label": "GA271",
                    "brightness": 60,
                },
            ],
        )

    def test_sets_only_the_selected_display(self) -> None:
        state = self.service.set_display("display_2", 45)

        self.service._run.assert_called_once_with(
            "--bus",
            "6",
            "setvcp",
            "10",
            "45",
        )
        self.service._refresh.assert_called_once_with()
        self.assertIn("brightness_displays", state)

    def test_changes_only_the_selected_display_relatively(self) -> None:
        self.service.change_display("display_1", "up")

        self.service._run.assert_called_once_with(
            "--bus",
            "3",
            "setvcp",
            "10",
            "+",
            "10",
        )

    def test_rejects_an_unknown_display(self) -> None:
        with self.assertRaisesRegex(BrightnessControlError, "no está disponible"):
            self.service.set_display("display_9", 50)

        self.service._run.assert_not_called()

    def test_rejects_an_out_of_range_value(self) -> None:
        with self.assertRaisesRegex(BrightnessControlError, "entre 0 y 100"):
            self.service.set_display("display_1", 101)

        self.service._run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
