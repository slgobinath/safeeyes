#!/usr/bin/env python
# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2016  Gobinath

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

import gi
from safeeyes import utility
from safeeyes.configuration import Config
from safeeyes.context import Context
from safeeyes.model import Break, TrayAction
from safeeyes.translations import translate as _

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GdkX11
from gi.repository import Gtk

BREAK_SCREEN_GLADE = os.path.join(utility.BIN_DIRECTORY, "glade/break_screen.glade")


class BreakScreen:
    """The fullscreen windows which prevent users from using the computer.

    This class creates and manages the fullscreen windows for every monitor.
    """

    windows: list["BreakScreenWindow"]

    def __init__(
        self,
        application: Gtk.Application,
        context: Context,
        on_skipped: typing.Callable[[], None],
        on_postponed: typing.Callable[[], None],
    ):
        self.application = application
        self.context = context
        self.x11_display = None
        self.enable_postpone = False
        self.enable_shortcut = False
        self.is_pretified = False
        self.keycode_shortcut_postpone = 65  # Space
        self.keycode_shortcut_skip = 9  # Escape
        self.on_postponed = on_postponed
        self.on_skipped = on_skipped
        self.fade_in_break_screen = True
        self.fade_in_break_screen_duration = 1500
        self.shortcut_disable_time = 2
        self.strict_break = False
        self.windows = []
        self.show_skip_button = False
        self.show_postpone_button = False
        # Worker that holds the X11 keyboard grab, and a signal that wakes it.
        # _keyboard_grab_held stays set until ungrab and sync both succeed, so a
        # failed unlock keeps this thread as the owner instead of dropping it.
        self._keyboard_lock_thread: typing.Optional[threading.Thread] = None
        self._keyboard_release_event = threading.Event()
        self._keyboard_grab_held = False
        self._keyboard_release_error: typing.Optional[BaseException] = None
        self.keyboard_regrab_delay = 5.0
        self.keyboard_regrab_interval = 1.0

        if not self.context.is_wayland:
            import Xlib.display

            self.x11_display = Xlib.display.Display()

    def initialize(self, config: Config) -> None:
        """Initialize the internal properties from configuration."""
        logging.info("Initialize the break screen")
        self.enable_postpone = config.get("allow_postpone", False)
        self.keycode_shortcut_postpone = config.get("shortcut_postpone", 65)
        self.keycode_shortcut_skip = config.get("shortcut_skip", 9)

        if self.context.is_wayland and (
            self.keycode_shortcut_postpone != 65 or self.keycode_shortcut_skip != 9
        ):
            logging.warning(
                _(
                    "Customizing the postpone and skip shortcuts does not work on "
                    "Wayland."
                )
            )

        # TODO: shortcut_disable_time should be renamed
        # it used to be just about keyboard shortcuts - now it also controls whether
        # the buttons are locked
        self.shortcut_disable_time = config.get("shortcut_disable_time", 2)
        self.fade_in_break_screen = config.get("fade_in_break_screen", True)
        self.fade_in_break_screen_duration = config.get(
            "fade_in_break_screen_duration", 1500
        )
        self.strict_break = config.get("strict_break", False)

    def skip_break(self) -> None:
        """Skip the break from the break screen.

        Aborts without dismissing the break screen if the X11 keyboard grab
        cannot be released, allowing the user to retry.
        """
        logging.info("User skipped the break")
        # Drop the X11 grab before on_skipped, which may lock the screen, but
        # still lock before close so the break window is up while locking.
        if not self.release_keyboard():
            logging.error(
                "Aborting skip because the X11 keyboard grab could not be released"
            )
            return
        self.on_skipped()
        self.close()

    def postpone_break(self) -> None:
        """Postpone the break from the break screen.

        Aborts without dismissing the break screen if the X11 keyboard grab
        cannot be released, allowing the user to retry.
        """
        logging.info("User postponed the break")
        if not self.release_keyboard():
            logging.error(
                "Aborting postpone because the X11 keyboard grab could not be released"
            )
            return
        self.on_postponed()
        self.close()

    def on_skip_clicked(self, button) -> None:
        """Skip button press event handler."""
        if self.enable_shortcut:
            self.skip_break()

    def on_postpone_clicked(self, button) -> None:
        """Postpone button press event handler."""
        if self.enable_shortcut:
            self.postpone_break()

    def show_count_down(self, countdown: int, seconds: int) -> None:
        """Show/update the count down on all screens."""
        self.enable_shortcut = self.shortcut_disable_time <= seconds
        mins, secs = divmod(countdown, 60)
        timeformat = "{:02d}:{:02d}".format(mins, secs)
        self.__update_count_down(timeformat, self.enable_shortcut)

    def show_message(
        self, break_obj: Break, widget: str, tray_actions: list[TrayAction] = []
    ) -> None:
        """Show the break screen with the given message on all displays."""
        message = break_obj.name
        image_path = break_obj.image
        self.enable_shortcut = self.shortcut_disable_time <= 0
        self.__show_break_screen(message, image_path, widget, tray_actions)

    def close(self) -> None:
        """Hide the break screen from active window and destroy all other
        windows.
        """
        logging.info("Close the break screen(s)")
        if not self.release_keyboard():
            # The core is ending the break, so still destroy the windows.
            logging.error(
                "Closing break screen despite failing to release the X11 keyboard grab"
            )

        # Destroy other windows if exists
        self.__destroy_all_screens()

    def __show_break_screen(
        self,
        message: str,
        image_path: typing.Optional[str],
        widget: str,
        tray_actions: list[TrayAction],
    ) -> None:
        """Show an empty break screen on all screens."""
        # Lock the keyboard
        if not self.context.is_wayland:
            self.__start_keyboard_lock_x11()

        display = Gdk.Display.get_default()

        if display is None:
            raise Exception("display not found")

        monitors = typing.cast(typing.Sequence[Gdk.Monitor], display.get_monitors())
        logging.info("Show break screens in %d display(s)", len(monitors))

        skip_button_disabled = self.context.get("skip_button_disabled", False)
        self.show_skip_button = not self.strict_break and not skip_button_disabled

        postpone_button_disabled = self.context.get("postpone_button_disabled", False)
        self.show_postpone_button = (
            self.enable_postpone and not postpone_button_disabled
        )

        i = 0

        for monitor in monitors:
            monitor_geometry = monitor.get_geometry()
            window = BreakScreenWindow(
                self.application,
                message,
                image_path,
                widget,
                monitor_geometry.width,
                monitor_geometry.height,
                tray_actions,
                lambda: self.close(),
                self.show_postpone_button,
                self.on_postpone_clicked,
                self.show_skip_button,
                self.on_skip_clicked,
                self.enable_shortcut,
                self.fade_in_break_screen_duration,
            )

            if self.context.is_wayland:
                # Note: in theory, this could also be used on X11
                # however, that already has its own implementation below
                controller = Gtk.EventControllerKey()
                controller.connect("key_pressed", self.on_key_pressed_wayland)
                controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                window.add_controller(controller)

            window.set_title("SafeEyes-" + str(i))

            self.windows.append(window)

            target_opacity = 0.9 if self.context.desktop == "kde" else 1.0
            window.configure_opacity(target_opacity, self.fade_in_break_screen)

            window.present()

            # Apparently this needs to run after present() (as of GTK 4.20)
            # On Wayland, either work seems to work fine
            # On X11, calling this before present() always fullscreens only on the
            # focused monitor regardless
            window.fullscreen_on_monitor(monitor)

            # this ensures that none of the buttons is in focus immediately
            # otherwise, pressing space presses that button instead of triggering the
            # shortcut
            window.set_focus(None)

            if not self.context.is_wayland:
                self.__window_set_keep_above_x11(window)

            if self.context.is_wayland:
                # this may or may not be granted by the window system
                surface = window.get_surface()
                if surface is not None:
                    typing.cast(Gdk.Toplevel, surface).inhibit_system_shortcuts(None)

            if self.fade_in_break_screen:
                window.start_fade_in()

            i = i + 1

    def __update_count_down(self, count: str, enable_shortcut: bool) -> None:
        """Update the countdown on all break screens."""
        for window in self.windows:
            window.set_count_down(count, enable_shortcut)

    def __window_set_keep_above_x11(self, window: "BreakScreenWindow") -> None:
        """Use EWMH hints to keep window above and on all desktops."""
        if self.x11_display is None:
            return

        import Xlib

        NET_WM_STATE = self.x11_display.intern_atom("_NET_WM_STATE")
        NET_WM_STATE_ABOVE = self.x11_display.intern_atom("_NET_WM_STATE_ABOVE")
        NET_WM_STATE_STICKY = self.x11_display.intern_atom("_NET_WM_STATE_STICKY")

        # To change the _NET_WM_STATE, we cannot simply set the
        # property - we must send a ClientMessage event
        # See https://specifications.freedesktop.org/wm-spec/1.3/ar01s05.html#id-1.6.8
        root_window = self.x11_display.screen().root

        surface = window.get_surface()

        if surface is None or not isinstance(surface, GdkX11.X11Surface):
            return

        xid = GdkX11.X11Surface.get_xid(surface)

        root_window.send_event(
            Xlib.protocol.event.ClientMessage(
                window=xid,
                client_type=NET_WM_STATE,
                data=(
                    32,
                    [
                        1,  # _NET_WM_STATE_ADD
                        NET_WM_STATE_ABOVE,
                        NET_WM_STATE_STICKY,  # other property
                        1,  # source indication
                        0,  # must be 0
                    ],
                ),
            ),
            event_mask=(
                Xlib.X.SubstructureRedirectMask | Xlib.X.SubstructureNotifyMask
            ),
        )

        self.x11_display.sync()

    def release_keyboard(self) -> bool:
        """Release the X11 keyboard grab and wait until the server has processed it.

        No-op on Wayland. Safe to call more than once. Returns True once no
        grab is held (including after falling back to closing and reopening the
        X11 display connection), or False if the grab could not be confirmed
        released.
        """
        if self.context.is_wayland:
            return True

        self._keyboard_release_event.set()
        thread = self._keyboard_lock_thread
        # Joining the worker from itself would deadlock. Its finally block
        # releases the grab when this invocation returns.
        if thread is threading.current_thread():
            return not self._keyboard_grab_held

        if thread is not None:
            logging.info("Unlock the keyboard")
            thread.join()

        if self._keyboard_grab_held:
            # The worker finished without a confirmed ungrab+sync. Retry here
            # and, if it fails again, close the X11 connection as a last resort.
            logging.error(
                "X11 keyboard grab is still held (%s); retrying unlock",
                self._keyboard_release_error,
            )
            self.__ungrab_keyboard_x11()
        if self._keyboard_grab_held:
            self.__reset_x11_display_for_release()
        if self._keyboard_grab_held:
            logging.error(
                "Failed to release the X11 keyboard grab; keeping lock thread %r: %s",
                self._keyboard_lock_thread,
                self._keyboard_release_error,
            )
            return False

        if self._keyboard_lock_thread is thread:
            self._keyboard_lock_thread = None
        return True

    def __reset_x11_display_for_release(self) -> None:
        """Close the X11 display to drop a stuck grab, then reopen it."""
        x11_display = self.x11_display
        if x11_display is None:
            return

        import Xlib.display
        import Xlib.error

        logging.error(
            "Closing X11 display connection as a last resort to drop the keyboard grab"
        )
        try:
            x11_display.close()
        except Xlib.error.ConnectionClosedError:
            logging.exception(
                "X11 display connection already closed while releasing keyboard grab"
            )
        except Exception as exc:
            self._keyboard_release_error = exc
            logging.exception(
                "Failed to close X11 display connection while releasing keyboard grab"
            )
            return

        self.x11_display = None
        self._keyboard_grab_held = False
        self._keyboard_release_error = None

        try:
            self.x11_display = Xlib.display.Display()
        except Exception:
            logging.exception("Failed to reopen X11 display connection")

    def restore_keyboard(self) -> None:
        """Restore the X11 keyboard grab while a break screen is still shown.

        No-op on Wayland or when no break screen windows are open.
        """
        if self.context.is_wayland or not self.windows:
            return

        self.__start_keyboard_lock_x11(wait_for_grab=True)

    def __start_keyboard_lock_x11(self, wait_for_grab: bool = False) -> None:
        """Grab the keyboard on a worker thread until release_keyboard()."""
        # utility.start_thread does not return the Thread, but release_keyboard
        # has to join this worker before a screen locker takes its own grab.
        if self._keyboard_grab_held:
            # Replacing the thread would drop a grab that ungrab or sync
            # could not release.
            logging.error(
                "X11 keyboard grab is still held; keeping the existing lock thread"
            )
            return
        if (
            self._keyboard_lock_thread is not None
            and self._keyboard_lock_thread.is_alive()
        ):
            return

        self._keyboard_release_event.clear()
        thread = threading.Thread(
            target=self.__lock_keyboard_x11,
            kwargs={"wait_for_grab": wait_for_grab},
            name="WorkThread BreakScreen.__lock_keyboard_x11",
            daemon=False,
        )
        self._keyboard_lock_thread = thread
        thread.start()

    def __lock_keyboard_x11(self, wait_for_grab: bool = False) -> None:
        """Lock the keyboard to prevent the user from using keyboard shortcuts.

        (X11 only)
        """
        x11_display = self.x11_display
        if x11_display is None:
            return

        from Xlib import X

        if wait_for_grab:
            # Let a command-based locker (Popen) acquire its own grab first.
            if self._keyboard_release_event.wait(self.keyboard_regrab_delay):
                return

        logging.info("Lock the keyboard")

        # Grab the keyboard
        root = x11_display.screen().root
        root.change_attributes(event_mask=X.KeyPressMask | X.KeyReleaseMask)
        self._keyboard_release_error = None
        try:
            if wait_for_grab:
                while True:
                    # Own the grab before calling the server so a failure after
                    # acquisition still ungrabs in finally.
                    self._keyboard_grab_held = True
                    status = root.grab_keyboard(
                        True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime
                    )
                    if status == X.GrabSuccess:
                        break
                    self._keyboard_grab_held = False
                    logging.debug(
                        "X11 keyboard grab not available yet (status=%s); retrying",
                        status,
                    )
                    if self._keyboard_release_event.wait(self.keyboard_regrab_interval):
                        return
            else:
                # Own the grab before calling the server. grab_keyboard can raise
                # after the grab is taken, and flush can raise after it returns;
                # either way the finally block still ungrabs and syncs.
                self._keyboard_grab_held = True
                root.grab_keyboard(
                    True, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime
                )
            x11_display.flush()

            # Consume keyboard events until the grab is released.
            while not self._keyboard_release_event.is_set():
                if x11_display.pending_events() > 0:
                    # Avoid waiting for next event by checking pending events
                    event = x11_display.next_event()
                    if self.enable_shortcut and event.type == X.KeyPress:
                        if (
                            event.detail == self.keycode_shortcut_skip
                            and self.show_skip_button
                        ):
                            utility.execute_main_thread(lambda: self.skip_break())
                            break
                        elif (
                            event.detail == self.keycode_shortcut_postpone
                            and self.show_postpone_button
                        ):
                            utility.execute_main_thread(lambda: self.postpone_break())
                            break
                else:
                    # Block for up to a second, waking immediately when released.
                    self._keyboard_release_event.wait(1)
        finally:
            if self._keyboard_grab_held:
                self.__ungrab_keyboard_x11()

    def __ungrab_keyboard_x11(self) -> None:
        """Ungrab and sync. Keep the grab held when either call fails."""
        x11_display = self.x11_display
        if x11_display is None:
            error = RuntimeError(
                "X11 display is missing; keyboard grab may still be held"
            )
            self._keyboard_release_error = error
            logging.error("%s", error)
            return

        from Xlib import X

        failures: list[BaseException] = []
        try:
            x11_display.ungrab_keyboard(X.CurrentTime)
        except Exception as exc:
            failures.append(exc)
            logging.exception("Failed to ungrab the X11 keyboard")
        try:
            # sync() blocks until the X server has processed the ungrab.
            x11_display.sync()
        except Exception as exc:
            failures.append(exc)
            logging.exception("Failed to sync the X11 keyboard ungrab")

        if failures:
            # Ownership stays with _keyboard_lock_thread until a later retry.
            self._keyboard_release_error = failures[0]
            return

        self._keyboard_grab_held = False
        self._keyboard_release_error = None

    def on_key_pressed_wayland(
        self, event_controller_key, keyval, keycode, state
    ) -> bool:
        if self.enable_shortcut:
            if keyval == Gdk.KEY_space and self.show_postpone_button:
                self.postpone_break()
                return True
            elif keyval == Gdk.KEY_Escape and self.show_skip_button:
                self.skip_break()
                return True

        return False

    def __destroy_all_screens(self) -> None:
        """Close all the break screens."""
        for win in self.windows:
            win.stop_fade_in()
            win.destroy()
        del self.windows[:]


@Gtk.Template(filename=BREAK_SCREEN_GLADE)
class BreakScreenWindow(Gtk.Window):
    """This class manages the UI for the break screen window.

    Each instance is a single window, covering a single monitor.
    """

    __gtype_name__ = "BreakScreenWindow"

    grid1: Gtk.Grid = Gtk.Template.Child()
    lbl_message: Gtk.Label = Gtk.Template.Child()
    lbl_count: Gtk.Label = Gtk.Template.Child()
    lbl_widget: Gtk.Label = Gtk.Template.Child()
    img_break: Gtk.Picture = Gtk.Template.Child()
    box_buttons: Gtk.Box = Gtk.Template.Child()
    toolbar: Gtk.Box = Gtk.Template.Child()

    def __init__(
        self,
        application: Gtk.Application,
        message: str,
        image_path: typing.Optional[str],
        widget: str,
        monitor_width: int,
        monitor_height: int,
        tray_actions: list[TrayAction],
        on_close: typing.Callable[[], None],
        show_postpone: bool,
        on_postpone: typing.Callable[[Gtk.Button], None],
        show_skip: bool,
        on_skip: typing.Callable[[Gtk.Button], None],
        enable_shortcut: bool,
        fade_in_duration_ms: int,
    ):
        super().__init__(application=application)

        self.on_close = on_close
        self.img_break.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
        self.grid1.add_css_class("break_screen_root")
        self.button_widgets: list[Gtk.Button] = []
        self.fade_in_target_opacity = 1.0
        self.fade_in_enabled = False
        self.fade_in_css_provider: typing.Optional[Gtk.CssProvider] = None
        self.fade_in_duration_ms = max(fade_in_duration_ms, 1)

        for tray_action in tray_actions:
            # TODO: apparently, this would be better served with an icon theme
            # + Gtk.button.new_from_icon_name
            icon = tray_action.get_icon()
            toolbar_button = Gtk.Button()
            toolbar_button.set_child(icon)
            tray_action.add_toolbar_button(toolbar_button)
            toolbar_button.connect(
                "clicked",
                lambda button, action: self.__tray_action(button, action),
                tray_action,
            )
            toolbar_button.set_tooltip_text(_(tray_action.name))
            self.toolbar.append(toolbar_button)
            toolbar_button.show()

        # Add the buttons
        if show_postpone:
            # Add postpone button
            btn_postpone = Gtk.Button.new_with_label(_("Postpone"))
            btn_postpone.get_style_context().add_class("btn_postpone")
            btn_postpone.connect("clicked", on_postpone)
            btn_postpone.set_visible(True)
            btn_postpone.set_sensitive(enable_shortcut)
            self.box_buttons.append(btn_postpone)
            self.button_widgets.append(btn_postpone)

        if show_skip:
            # Add the skip button
            btn_skip = Gtk.Button.new_with_label(_("Skip"))
            btn_skip.get_style_context().add_class("btn_skip")
            btn_skip.connect("clicked", on_skip)
            btn_skip.set_visible(True)
            btn_skip.set_sensitive(enable_shortcut)
            self.box_buttons.append(btn_skip)
            self.button_widgets.append(btn_skip)

        # Set values
        if image_path:
            self.__set_break_image(image_path, monitor_width, monitor_height)
        self.lbl_message.set_label(message)
        self.lbl_widget.set_markup(widget)

    def configure_opacity(self, target_opacity: float, fade_in_enabled: bool) -> None:
        self.fade_in_target_opacity = target_opacity
        self.fade_in_enabled = fade_in_enabled
        self.set_opacity(target_opacity)
        self.grid1.remove_css_class("break_screen_fade_in")

        if fade_in_enabled:
            self.__set_fade_in_animation_duration(self.fade_in_duration_ms)

    def start_fade_in(self) -> None:
        if self.fade_in_enabled:
            self.grid1.add_css_class("break_screen_fade_in")

    def stop_fade_in(self) -> None:
        self.grid1.remove_css_class("break_screen_fade_in")

    def __set_fade_in_animation_duration(self, fade_in_duration_ms: int) -> None:
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            f".break_screen_fade_in {{ animation-duration: {fade_in_duration_ms}ms; }}"
        )

        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
            )

        self.fade_in_css_provider = css_provider

    def set_count_down(self, count: str, enable_shortcut: bool) -> None:
        self.lbl_count.set_text(count)

        for button in self.button_widgets:
            button.set_sensitive(enable_shortcut)

    def __tray_action(self, button, tray_action: TrayAction) -> None:
        """Tray action handler.

        Hides all toolbar buttons for this action and call the action
        provided by the plugin.
        """
        if tray_action.single_use:
            tray_action.reset()
        tray_action.action()

    def __set_break_image(
        self, image_path: str, monitor_width: int, monitor_height: int
    ) -> None:
        """Load the break image and cap it relative to the current monitor size."""
        max_width = max(1, (monitor_width * 8) // 10 - 1)
        max_height = max(1, (monitor_height * 3) // 10 - 1)

        try:
            loaded = GdkPixbuf.Pixbuf.new_from_file(image_path)
            if loaded is None:
                raise ValueError("Failed to load break image")
        except Exception:
            logging.exception("Failed to load break image: %s", image_path)
            return
        pixbuf: GdkPixbuf.Pixbuf = loaded

        width, height = pixbuf.get_width(), pixbuf.get_height()
        scale = min(1, max_width / width, max_height / height)
        if scale < 1:
            pixbuf = (
                pixbuf.scale_simple(
                    max(1, int(width * scale)),
                    max(1, int(height * scale)),
                    GdkPixbuf.InterpType.BILINEAR,
                )
                or pixbuf
            )

        self.img_break.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))

    @Gtk.Template.Callback()
    def on_window_delete(self, *args) -> None:
        """Window close event handler."""
        logging.info("Closing the break screen")
        self.stop_fade_in()
        self.on_close()
