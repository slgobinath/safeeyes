import unittest
from unittest.mock import MagicMock, patch
import sys

from safeeyes.plugins.smartpause.macos import IdleMonitorMacOS
from safeeyes.plugins.smartpause import dependency_checker


class TestMacOSIdleMonitor(unittest.TestCase):
    def test_init_with_quartz(self):
        monitor = IdleMonitorMacOS()
        mock_quartz = MagicMock()
        mock_quartz.CGEventSourceSecondsSinceLastEventType.return_value = 42.5
        mock_quartz.kCGEventSourceStateCombinedSessionState = 0
        mock_quartz.kCGAnyInputEventType = 0xFFFFFFFF

        with patch.dict(sys.modules, {"Quartz": mock_quartz}):
            monitor.init()
            self.assertEqual(monitor._get_idle_time(), 42.5)

    def test_init_with_ctypes_fallback(self):
        monitor = IdleMonitorMacOS()
        mock_core_graphics = MagicMock()
        mock_core_graphics.CGEventSourceSecondsSinceLastEventType.return_value = 15.0

        with patch.dict(sys.modules, {"Quartz": None}):
            with patch("ctypes.cdll.LoadLibrary", return_value=mock_core_graphics):
                with patch("ctypes.util.find_library", return_value="CoreGraphics"):
                    monitor.init()
                    self.assertEqual(monitor._get_idle_time(), 15.0)

    def test_dependency_checker_on_macos(self):
        with patch("sys.platform", "darwin"):
            result = dependency_checker.validate({}, {})
            self.assertIsNone(result)

    def test_lifecycle(self):
        monitor = IdleMonitorMacOS()
        self.assertFalse(monitor.is_monitor_running())
        with patch.object(monitor, "_start_idle_monitor"):
            with patch("safeeyes.utility.start_thread"):
                monitor.start_monitor(lambda: None, lambda: None, 10.0)
                self.assertTrue(monitor.is_monitor_running())
                monitor.stop_monitor()
                self.assertFalse(monitor.is_monitor_running())


if __name__ == "__main__":
    unittest.main()
