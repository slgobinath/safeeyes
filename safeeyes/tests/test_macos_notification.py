import unittest
from unittest.mock import MagicMock, patch
import sys

from safeeyes.model import Break, BreakType
from safeeyes.plugins.notification.macos import MacOSNotification
from safeeyes.plugins.notification import plugin as notification_plugin


class TestMacOSNotification(unittest.TestCase):
    def test_osascript_notification(self):
        notif = MacOSNotification("Safe Eyes", "Time for a break")
        with (
            patch.object(notif, "_show_user_notifications", return_value=False),
            patch.object(notif, "_show_ns_user_notifications", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = notif.show()
            self.assertTrue(result)
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            cmd = args[0]
            self.assertEqual(cmd[0], "osascript")
            self.assertIn("Time for a break", cmd)
            self.assertIn("Safe Eyes", cmd)

        # Ensure close does not raise
        notif.close()

    def test_ns_user_notification_center(self):
        mock_center = MagicMock()
        mock_notif_class = MagicMock()
        mock_instance = MagicMock()
        mock_notif_class.alloc.return_value.init.return_value = mock_instance

        with patch.dict(
            sys.modules,
            {
                "Foundation": MagicMock(
                    NSUserNotificationCenter=MagicMock(
                        defaultUserNotificationCenter=MagicMock(
                            return_value=mock_center
                        )
                    ),
                    NSUserNotification=mock_notif_class,
                )
            },
        ):
            notif = MacOSNotification("Safe Eyes", "Pre-break alert")
            result = notif._show_ns_user_notifications()
            self.assertTrue(result)
            mock_center.deliverNotification_.assert_called_once_with(
                mock_instance
            )

            # Test close
            notif._delivered_via_objc = True
            notif.close()
            mock_center.removeDeliveredNotification_.assert_called_once_with(
                mock_instance
            )

    def test_plugin_on_pre_break_and_on_start_break_macos(self):
        break_obj = Break(
            break_type=BreakType.SHORT_BREAK,
            name="Short Break",
            time=15,
            duration=20,
            image=None,
            plugins={},
        )

        with patch("sys.platform", "darwin"):
            with patch(
                "safeeyes.plugins.notification.macos.MacOSNotification.show"
            ) as mock_show:
                with patch(
                    "safeeyes.plugins.notification.macos.MacOSNotification.close"
                ) as mock_close:
                    notification_plugin.init(
                        {}, {"pre_break_warning_time": 10}, {}
                    )
                    notification_plugin.on_pre_break(break_obj)

                    self.assertIsNotNone(notification_plugin.notification)
                    mock_show.assert_called_once()

                    notification_plugin.on_start_break(break_obj)
                    self.assertIsNone(notification_plugin.notification)
                    mock_close.assert_called_once()

                    # on_exit shouldn't raise on macOS
                    notification_plugin.on_exit()


if __name__ == "__main__":
    unittest.main()
