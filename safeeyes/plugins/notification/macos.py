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
import subprocess
import typing


class MacOSNotification:
    """macOS-native notification dispatcher.

    Dispatches notifications using PyObjC's UNUserNotificationCenter or
    NSUserNotificationCenter when available, with a reliable osascript
    AppleScript fallback.
    """

    def __init__(
        self,
        title: str,
        message: str,
        identifier: str = "safeeyes-break-pre-warning",
    ) -> None:
        self.title = title
        self.message = message
        self.identifier = identifier
        self._ns_notification: typing.Any = None
        self._delivered_via_objc: bool = False

    def show(self) -> bool:
        """Display the notification on macOS."""
        # 1. Try UNUserNotificationCenter (Modern PyObjC)
        if self._show_user_notifications():
            self._delivered_via_objc = True
            logging.debug("Dispatched notification via UNUserNotificationCenter")
            return True

        # 2. Try NSUserNotificationCenter (Legacy PyObjC)
        if self._show_ns_user_notifications():
            self._delivered_via_objc = True
            logging.debug("Dispatched notification via NSUserNotificationCenter")
            return True

        # 3. Fallback to osascript (built-in AppleScript command)
        logging.debug("Dispatching notification via osascript fallback")
        return self._show_osascript()

    def _show_user_notifications(self) -> bool:
        try:
            from UserNotifications import (  # type: ignore
                UNMutableNotificationContent,
                UNNotificationRequest,
                UNNotificationSound,
                UNUserNotificationCenter,
            )

            center = UNUserNotificationCenter.currentNotificationCenter()
            if center is None:
                return False

            content = UNMutableNotificationContent.alloc().init()
            content.setTitle_(self.title)
            content.setBody_(self.message.strip())
            content.setSound_(UNNotificationSound.defaultSound())

            request = UNNotificationRequest.requestWithIdentifier_content_trigger_(
                self.identifier, content, None
            )
            center.addNotificationRequest_withCompletionHandler_(request, None)
            return True
        except Exception:
            return False

    def _show_ns_user_notifications(self) -> bool:
        try:
            from Foundation import (  # type: ignore
                NSUserNotification,
                NSUserNotificationCenter,
            )

            center = NSUserNotificationCenter.defaultUserNotificationCenter()
            if center is None:
                return False

            notification = NSUserNotification.alloc().init()
            notification.setTitle_(self.title)
            notification.setInformativeText_(self.message.strip())
            notification.setSoundName_("NSUserNotificationDefaultSoundName")
            notification.setIdentifier_(self.identifier)

            self._ns_notification = notification
            center.deliverNotification_(notification)
            return True
        except Exception:
            return False

    def _show_osascript(self) -> bool:
        script = (
            "on run argv\n"
            '    display notification (item 1 of argv) with title '
            '(item 2 of argv) sound name "default"\n'
            "end run"
        )
        try:
            subprocess.run(
                ["osascript", "-e", script, self.message.strip(), self.title],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return True
        except Exception as e:
            logging.error("Failed to show notification via osascript: %s", e)
            return False

    def close(self) -> None:
        """Close / dismiss the notification if supported."""
        if self._delivered_via_objc:
            try:
                if self._ns_notification is not None:
                    from Foundation import NSUserNotificationCenter  # type: ignore

                    center = NSUserNotificationCenter.defaultUserNotificationCenter()
                    if center is not None:
                        center.removeDeliveredNotification_(self._ns_notification)
                    self._ns_notification = None
            except Exception:
                pass

            try:
                from UserNotifications import UNUserNotificationCenter  # type: ignore

                center = UNUserNotificationCenter.currentNotificationCenter()
                if center is not None:
                    center.removeDeliveredNotificationsWithIdentifiers_([self.identifier])
            except Exception:
                pass
