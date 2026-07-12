import unittest

from app.actions import AppAction


class AppActionTests(unittest.TestCase):
    def test_from_ui_row_preserves_widget_fields(self):
        handler = lambda: "ok"

        action = AppAction.from_ui_row(
            "global_boost",
            "desc_global_boost",
            "run_action",
            handler,
            category="system",
        )

        self.assertEqual(action.key, "global_boost")
        self.assertEqual(action.title_key, "global_boost")
        self.assertEqual(action.description_key, "desc_global_boost")
        self.assertEqual(action.button_key, "run_action")
        self.assertEqual(action.category, "system")
        self.assertIs(action.handler, handler)


if __name__ == "__main__":
    unittest.main()
