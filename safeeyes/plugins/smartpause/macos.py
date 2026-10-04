# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2017  Gobinath
# Copyright (C) 2026  Mohamed Elgypaly

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import threading
import typing

from safeeyes import utility
from .interface import IdleMonitorInterface


class IdleMonitorMacOS(IdleMonitorInterface):
    """IdleMonitorInterface implementation for macOS.

    Uses CoreGraphics / Quartz framework's CGEventSourceSecondsSinceLastEventType
    to retrieve the elapsed system idle time in seconds.
    """

    active: bool = False
    lock = threading.Lock()
    idle_condition = threading.Condition()

    def __init__(self) -> None:
        self._get_idle_seconds: typing.Optional[typing.Callable[[], float]] = None

    def _is_active(self) -> bool:
        """Thread-safe check to determine if the monitor is active."""
        with self.lock:
            return self.active

    def _set_active(self, is_active: bool) -> None:
        """Thread-safe setter for the monitor's active state."""
        with self.lock:
            self.active = is_active

    def init(self) -> None:
        """Initialize the macOS idle time tracking function.

        Tries PyObjC Quartz first, and falls back to ctypes loading CoreGraphics
        directly if PyObjC is not installed.
        """
        # 1. Attempt to use PyObjC Quartz
        try:
            from Quartz import (  # type: ignore
                CGEventSourceSecondsSinceLastEventType,
                kCGAnyInputEventType,
                kCGEventSourceStateCombinedSessionState,
            )

            self._get_idle_seconds = lambda: float(
                CGEventSourceSecondsSinceLastEventType(
                    kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType
                )
            )
            logging.debug("Initialized macOS idle monitor using PyObjC Quartz")
            return
        except (ImportError, Exception):
            pass

        # 2. Fallback to ctypes calling CoreGraphics directly
        try:
            import ctypes
            import ctypes.util

            cg_path = ctypes.util.find_library("CoreGraphics") or (
                "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
            )
            core_graphics = ctypes.cdll.LoadLibrary(cg_path)

            # CGEventSourceSecondsSinceLastEventType(
            #     CGEventSourceStateID stateID, CGEventType eventType
            # )
            func = core_graphics.CGEventSourceSecondsSinceLastEventType
            func.restype = ctypes.c_double
            func.argtypes = [
                ctypes.c_uint32,
                ctypes.c_uint32,
            ]

            # kCGEventSourceStateCombinedSessionState = 0
            # kCGAnyInputEventType = ~0 (0xFFFFFFFF)
            kCGEventSourceStateCombinedSessionState = 0
            kCGAnyInputEventType = 0xFFFFFFFF

            self._get_idle_seconds = lambda: float(
                func(
                    kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType
                )
            )
            logging.debug("Initialized macOS idle monitor using ctypes CoreGraphics")
            return
        except Exception as e:
            msg = f"Failed to load macOS CoreGraphics / Quartz library: {e}"
            raise RuntimeError(msg) from e

    def _get_idle_time(self) -> float:
        """Retrieve current system idle time in seconds."""
        if self._get_idle_seconds is not None:
            return self._get_idle_seconds()
        return 0.0

    def start_monitor(
        self,
        on_idle: typing.Callable[[], None],
        on_resumed: typing.Callable[[], None],
        idle_time: float,
    ) -> None:
        """Start a thread to continuously check macOS idle time."""
        if not self._is_active():
            self._set_active(True)
            utility.start_thread(
                self._start_idle_monitor,
                on_idle=on_idle,
                on_resumed=on_resumed,
                idle_time=idle_time,
            )

    def is_monitor_running(self) -> bool:
        """Check if the monitor is currently running."""
        return self._is_active()

    def _start_idle_monitor(
        self,
        on_idle: typing.Callable[[], None],
        on_resumed: typing.Callable[[], None],
        idle_time: float,
    ) -> None:
        """Continuously check system idle time and notify Safe Eyes on state changes."""
        waiting_time = min(idle_time, 2)
        was_idle = False

        while self._is_active():
            self.idle_condition.acquire()
            self.idle_condition.wait(waiting_time)
            self.idle_condition.release()

            if self._is_active():
                system_idle_time = self._get_idle_time()
                if system_idle_time >= idle_time and not was_idle:
                    was_idle = True
                    utility.execute_main_thread(on_idle)
                elif system_idle_time < idle_time and was_idle:
                    was_idle = False
                    utility.execute_main_thread(on_resumed)

    def stop_monitor(self) -> None:
        """Stop the background monitor thread."""
        self._set_active(False)
        self.idle_condition.acquire()
        self.idle_condition.notify_all()
        self.idle_condition.release()

    def stop(self) -> None:
        """Deinitialize monitor."""
        self.stop_monitor()
        self._get_idle_seconds = None
