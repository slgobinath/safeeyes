import unittest
from unittest.mock import MagicMock, patch
import sys

from safeeyes.plugins.trayicon.macos import MacOSTrayService
from safeeyes.plugins.trayicon import dependency_checker


class TestMacOSTray(unittest.TestCase):
    def test_dependency_checker_on_macos(self):
        with patch("sys.platform", "darwin"):
            result = dependency_checker.validate({}, {})
            self.assertIsNone(result)

    def test_tray_service_headless(self):
        sample_items = [
            {"id": 1, "label": "Next break at 12:00", "enabled": True},
            {"id": 2, "type": "separator"},
            {
                "id": 4,
                "label": "Disable Safe Eyes",
                "children": [
                    {"id": 12, "label": "Until restart", "callback": MagicMock()}
                ],
            },
            {"id": 8, "label": "Quit", "callback": MagicMock()},
        ]

        service = MacOSTrayService(menu_items=sample_items)
        service.register()

        service.set_tooltip("Safe Eyes", "Next break in 5 minutes")
        self.assertEqual(service.current_tooltip, "Next break in 5 minutes")

        service.set_xayatanalabel("05:00")
        self.assertEqual(service.current_label, "05:00")

        service.set_icon("io.github.slgobinath.SafeEyes-disabled")
        self.assertEqual(service.current_icon, "io.github.slgobinath.SafeEyes-disabled")

        service.set_items(sample_items)
        self.assertEqual(len(service.menu_items), 4)

        service.unregister()
        self.assertIsNone(service.status_item)

    def test_pystray_menu_builder(self):
        callback_mock = MagicMock()
        items = [
            {"id": 1, "label": "Timer", "enabled": True},
            {"id": 2, "type": "separator"},
            {
                "id": 5,
                "label": "Take break",
                "children": [{"id": 9, "label": "Any", "callback": callback_mock}],
            },
        ]
        service = MacOSTrayService(menu_items=items)
        mock_pystray = MagicMock()
        mock_pystray.Menu.SEPARATOR = "SEPARATOR"
        mock_pystray.MenuItem.side_effect = (
            lambda label, action=None, enabled=True: MagicMock(
                label=label, action=action, enabled=enabled
            )
        )
        mock_pystray.Menu.side_effect = lambda *args: list(args)

        with patch.dict(sys.modules, {"pystray": mock_pystray}):
            with patch("safeeyes.utility.execute_main_thread") as mock_exec:
                pystray_menu = service._build_pystray_menu(items)
                self.assertEqual(len(pystray_menu), 3)

                # Check that clicking item with callback dispatches to
                # execute_main_thread
                take_break_item = pystray_menu[2]
                submenu = take_break_item.action
                any_break_item = submenu[0]
                any_break_item.action()
                mock_exec.assert_called_once_with(callback_mock)


if __name__ == "__main__":
    unittest.main()
