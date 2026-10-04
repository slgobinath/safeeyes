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
import os
import threading
import typing

from safeeyes import utility

HAS_APPKIT: bool = False
HAS_PYSTRAY: bool = False

# Try importing AppKit / Cocoa via PyObjC
try:
    import objc  # type: ignore
    from Foundation import NSObject  # type: ignore
    from AppKit import (  # type: ignore
        NSStatusBar,
        NSVariableStatusItemLength,
        NSMenu,
        NSMenuItem,
        NSImage,
    )
    HAS_APPKIT = True
except (ImportError, Exception):
    HAS_APPKIT = False

# Try importing pystray as an alternative backend
try:
    import pystray  # type: ignore # noqa: F401
    from PIL import Image
    HAS_PYSTRAY = True
except (ImportError, Exception):
    HAS_PYSTRAY = False


def _find_icon_path(icon_name: str) -> typing.Optional[str]:
    """Find the path to the specified icon file."""
    sizes = ["24x24", "32x32", "16x16", "48x48"]
    for size in sizes:
        candidate = os.path.join(
            utility.SYSTEM_ICONS, f"hicolor/{size}/status/{icon_name}.png"
        )
        if os.path.isfile(candidate):
            return candidate
    plugin_icon = os.path.join(utility.BIN_DIRECTORY, "plugins", "trayicon", "icon.png")
    if os.path.isfile(plugin_icon):
        return plugin_icon
    return None


def _run_on_main_thread(func: typing.Callable[[], None]) -> None:
    """Ensure the target function is executed on the main UI thread.

    SafeEyes runs GLib/GTK on the main thread. To avoid thread conflicts or
    blocking the GLib main loop, UI operations are dispatched via
    utility.execute_main_thread if not already on the main thread.
    """
    if threading.current_thread() is threading.main_thread():
        func()
    else:
        utility.execute_main_thread(func)


if HAS_APPKIT:
    class MenuActionTarget(NSObject):
        """ObjC target for handling NSMenuItem click actions."""

        def init(self):
            self = objc.super(MenuActionTarget, self).init()
            if self is None:
                return None
            self._callbacks = {}
            return self

        def registerCallback_forTag_(
            self, callback: typing.Callable[[], None], tag: int
        ):
            self._callbacks[tag] = callback

        def clearCallbacks(self):
            self._callbacks.clear()

        @objc.IBAction
        def menuAction_(self, sender):
            tag = sender.tag()
            cb = self._callbacks.get(tag)
            if cb:
                # Dispatch back into GLib main loop to avoid blocking Cocoa menu
                utility.execute_main_thread(cb)


class MacOSTrayService:
    """macOS Top Menu Bar Tray implementation.

    Provides a native macOS menu bar status item replacing Linux DBus
    StatusNotifierItem/DBusMenu.

    Integrates with the GLib main loop by dispatching UI mutations onto the main
    thread and queuing user interaction callbacks via GLib.idle_add.
    """

    last_activation_token: typing.Optional[str] = None

    def __init__(
        self,
        menu_items: typing.List[typing.Dict[str, typing.Any]],
        on_secondary_activate: typing.Optional[typing.Callable[[], None]] = None,
    ) -> None:
        self.menu_items = menu_items
        self.on_secondary_activate = on_secondary_activate
        self.current_icon = "io.github.slgobinath.SafeEyes-enabled"
        self.current_label = ""
        self.current_tooltip = "Safe Eyes"
        self.status_item = None
        self._target = None
        self._backend: str = "headless"
        self._pystray_icon = None

    def register(self) -> None:
        """Register and display the macOS status item."""
        if HAS_APPKIT:
            self._backend = "appkit"
            self._init_appkit()
        elif HAS_PYSTRAY:
            self._backend = "pystray"
            self._init_pystray()
        else:
            self._backend = "headless"
            logging.info(
                "Neither PyObjC (AppKit) nor pystray is available for macOS tray. "
                "Running in headless tray mode."
            )

    def _init_appkit(self) -> None:
        def _setup():
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
                NSVariableStatusItemLength
            )
            self._target = MenuActionTarget.alloc().init()
            self._update_appkit_icon()
            self._update_appkit_menu()
            self._update_appkit_label()
            self._update_appkit_tooltip()

        _run_on_main_thread(_setup)

    def _build_appkit_menu(self, items: typing.List[typing.Dict[str, typing.Any]]):
        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        for item in items:
            if item.get("hidden"):
                continue
            if item.get("type") == "separator":
                menu.addItem_(NSMenuItem.separatorItem())
                continue

            label = item.get("label", "")
            enabled = item.get("enabled", True)
            callback = item.get("callback")
            children = item.get("children")
            item_id = item.get("id", 0)

            menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                label,
                "menuAction:" if callback else None,
                "",
            )
            menu_item.setEnabled_(enabled)
            menu_item.setTag_(item_id)

            if callback and self._target:
                self._target.registerCallback_forTag_(callback, item_id)
                menu_item.setTarget_(self._target)

            if children:
                submenu = self._build_appkit_menu(children)
                menu_item.setSubmenu_(submenu)

            menu.addItem_(menu_item)

        return menu

    def _update_appkit_menu(self) -> None:
        if not self.status_item:
            return

        def _apply():
            if self._target:
                self._target.clearCallbacks()
            menu = self._build_appkit_menu(self.menu_items)
            self.status_item.setMenu_(menu)

        _run_on_main_thread(_apply)

    def _update_appkit_icon(self) -> None:
        if not self.status_item:
            return

        def _apply():
            icon_path = _find_icon_path(self.current_icon)
            button = self.status_item.button()
            if button and icon_path and os.path.exists(icon_path):
                img = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if img:
                    img.setSize_((18.0, 18.0))
                    button.setImage_(img)
                    button.setImagePosition_(2)  # NSImageLeading (left of title)

        _run_on_main_thread(_apply)

    def _update_appkit_label(self) -> None:
        if not self.status_item:
            return

        def _apply():
            button = self.status_item.button()
            if button:
                button.setTitle_(self.current_label or "")

        _run_on_main_thread(_apply)

    def _update_appkit_tooltip(self) -> None:
        if not self.status_item:
            return

        def _apply():
            button = self.status_item.button()
            if button:
                button.setToolTip_(self.current_tooltip or "Safe Eyes")

        _run_on_main_thread(_apply)

    def _init_pystray(self) -> None:
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return

        icon_path = _find_icon_path(self.current_icon)
        image = None
        if icon_path and os.path.exists(icon_path):
            try:
                image = Image.open(icon_path)
            except Exception as e:
                logging.warning("Failed to load icon for pystray: %s", e)

        if image is None:
            image = Image.new("RGBA", (24, 24), color=(0, 0, 0, 0))

        menu = self._build_pystray_menu(self.menu_items)
        self._pystray_icon = pystray.Icon(
            "SafeEyes",
            image,
            title=self.current_tooltip,
            menu=menu,
        )
        self._pystray_icon.run_detached()

    def _build_pystray_menu(self, items: typing.List[typing.Dict[str, typing.Any]]):
        import pystray

        pystray_items = []
        for item in items:
            if item.get("hidden"):
                continue
            if item.get("type") == "separator":
                pystray_items.append(pystray.Menu.SEPARATOR)
                continue
            label = item.get("label", "")
            enabled = item.get("enabled", True)
            callback = item.get("callback")
            children = item.get("children")
            if children:
                submenu = self._build_pystray_menu(children)
                pystray_items.append(pystray.MenuItem(label, submenu, enabled=enabled))
            else:
                action = (
                    (lambda it=item: utility.execute_main_thread(it["callback"]))
                    if callback
                    else None
                )
                pystray_items.append(pystray.MenuItem(label, action, enabled=enabled))
        return pystray.Menu(*pystray_items)

    def set_items(self, items: typing.List[typing.Dict[str, typing.Any]]) -> None:
        """Update tray menu items."""
        self.menu_items = items
        if self._backend == "appkit":
            self._update_appkit_menu()
        elif self._backend == "pystray" and self._pystray_icon:
            self._pystray_icon.menu = self._build_pystray_menu(items)

    def set_tooltip(self, title: str, description: str) -> None:
        """Update status item tooltip."""
        self.current_tooltip = description if description else title
        if self._backend == "appkit":
            self._update_appkit_tooltip()
        elif self._backend == "pystray" and self._pystray_icon:
            self._pystray_icon.title = self.current_tooltip

    def set_xayatanalabel(self, label: str) -> None:
        """Update top bar text label next to status icon."""
        self.current_label = label
        if self._backend == "appkit":
            self._update_appkit_label()

    def set_icon(self, icon_name: str) -> None:
        """Update the menu bar icon."""
        self.current_icon = icon_name
        if self._backend == "appkit":
            self._update_appkit_icon()
        elif self._backend == "pystray" and self._pystray_icon:
            icon_path = _find_icon_path(icon_name)
            if icon_path and os.path.exists(icon_path):
                try:
                    self._pystray_icon.icon = Image.open(icon_path)
                except Exception as e:
                    logging.warning("Failed to update pystray icon image: %s", e)

    def unregister(self) -> None:
        """Remove the status item from the macOS menu bar."""
        if self._backend == "appkit" and self.status_item:
            def _cleanup():
                from AppKit import NSStatusBar
                NSStatusBar.systemStatusBar().removeStatusItem_(self.status_item)
                self.status_item = None
                if self._target:
                    self._target.clearCallbacks()
                    self._target = None

            _run_on_main_thread(_cleanup)
        elif self._backend == "pystray" and self._pystray_icon:
            try:
                self._pystray_icon.stop()
            except Exception:
                pass
            self._pystray_icon = None
