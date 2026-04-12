# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2026 Archisman Panigrahi <apandada1@gmail.com>

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

import datetime
import logging
import os
import typing

import gi
from safeeyes import utility
from safeeyes.context import Context
from safeeyes.model import BreakType
from safeeyes.plugins.trayicon.menu import build_info_message, build_menu_items
from safeeyes.translations import translate as _

gi.require_version("Gtk", "4.0")
gi.require_version("Notify", "0.7")
from gi.repository import GLib, Gtk, Notify

APP_ID = "safeeyes"

context: typing.Optional[Context] = None
notification: typing.Optional[Notify.Notification] = None
options_window: typing.Optional["ResidentOptionsWindow"] = None
notify_initialized = False
is_active = False
next_break_time: typing.Optional[datetime.datetime] = None
next_break_type: typing.Optional[BreakType] = None
server_caps: typing.Optional[set[str]] = None
fallback_mode = False
tray_menu_config: dict = {
    "show_time_in_tray": False,
    "show_long_time_in_tray": False,
    "allow_disabling": True,
    "disable_options": [],
}
wakeup_time: typing.Optional[datetime.datetime] = None
menu_locked = False
resume_timeout_id: typing.Optional[int] = None
strict_break_enabled = False
refresh_timeout_id: typing.Optional[int] = None
last_notification_payload: typing.Optional[tuple[str, str, str, bool]] = None
suppress_reopen = False
reopen_timeout_id: typing.Optional[int] = None

REFRESH_DEBOUNCE_MS = 300
RATE_LIMIT_RETRY_MS = 2000
REOPEN_DELAY_MS = 1000
MOBILE_NOTIFICATION_TIMEOUT_MS = 500


class ResidentOptionsWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="Safe Eyes " + _("Options"))

        self.set_default_size(320, 420)
        self.set_resizable(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scrolled)

        self.box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        scrolled.set_child(self.box)

        self.connect("close-request", self._on_close_request)
        self.refresh()

    def refresh(self) -> None:
        while (child := self.box.get_first_child()) is not None:
            self.box.remove(child)

        for item in _get_menu_items():
            widget = self._build_item_widget(item)
            if widget is not None:
                self.box.append(widget)

    def _build_item_widget(self, item: dict) -> typing.Optional[Gtk.Widget]:
        if item.get("hidden", False):
            return None

        if item.get("type") == "separator":
            return Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        if "children" in item:
            expander = Gtk.Expander(label=item.get("label", ""))
            expander.set_sensitive(item.get("enabled", True))
            expander.set_expanded(True)

            child_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            for child_item in item["children"]:
                child_widget = self._build_item_widget(child_item)
                if child_widget is not None:
                    child_box.append(child_widget)

            expander.set_child(child_box)
            return expander

        callback = item.get("callback")
        label = item.get("label", "")
        enabled = item.get("enabled", True)

        if callback is not None:
            button = Gtk.Button(label=label)
            button.set_sensitive(enabled)
            button.set_hexpand(True)
            button.connect("clicked", lambda *_args: self._activate(callback))
            return button

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_label = Gtk.Label(label=label, xalign=0)
        info_label.set_wrap(True)
        info_label.set_sensitive(enabled)
        box.append(info_label)
        return box

    def _activate(self, callback: typing.Callable[[], None]) -> None:
        callback()
        self.refresh()

    def _on_close_request(self, *_args) -> bool:
        self.hide()
        return True


def init(ctx, safeeyes_config, plugin_config):
    """Initialize the resident notification plugin."""
    del plugin_config

    global context
    global strict_break_enabled
    global tray_menu_config

    logging.debug("Initialize Resident Notification plugin")
    context = ctx
    strict_break_enabled = bool(safeeyes_config.get("strict_break"))
    tray_menu_config = _load_tray_menu_config(safeeyes_config)
    _ensure_notify()


def on_start():
    global is_active
    global wakeup_time
    is_active = True
    wakeup_time = None
    _refresh_all()


def on_activate() -> None:
    if _uses_temporary_mobile_notification():
        _refresh_all()


def on_stop():
    global is_active
    is_active = False
    _refresh_all()


def update_next_break(break_obj, break_time):
    global next_break_time
    global next_break_type

    next_break_time = break_time
    next_break_type = break_obj.type
    _refresh_all()


def on_exit():
    logging.debug("Stop Resident Notification plugin")
    _shutdown_notification()


def disable():
    _shutdown_notification()


def on_pre_break(break_obj):
    del break_obj

    global menu_locked

    if strict_break_enabled:
        menu_locked = True
        _refresh_all()


def on_start_break(break_obj):
    del break_obj


def on_stop_break():
    global menu_locked

    menu_locked = False
    _refresh_all()


def _load_tray_menu_config(safeeyes_config) -> dict:
    for plugin in safeeyes_config.get("plugins"):
        if plugin["id"] == "trayicon":
            return dict(plugin.get("settings", {}))

    config_path = os.path.join(utility.SYSTEM_PLUGINS_DIR, "trayicon", "config.json")
    config = utility.load_json(config_path) or {}
    settings = {}
    for setting in config.get("settings", []):
        settings[setting["id"]] = setting["default"]
    return settings


def _ensure_notify() -> None:
    global notify_initialized
    if notify_initialized:
        return

    Notify.init(APP_ID)
    notify_initialized = True


def _shutdown_notification() -> None:
    global notification
    global notify_initialized
    global server_caps
    global fallback_mode
    global options_window
    global resume_timeout_id
    global refresh_timeout_id
    global last_notification_payload
    global reopen_timeout_id

    _close_notification()
    if notify_initialized:
        Notify.uninit()
        notify_initialized = False
    if options_window is not None:
        options_window.destroy()
        options_window = None
    if resume_timeout_id is not None:
        GLib.source_remove(resume_timeout_id)
        resume_timeout_id = None
    if refresh_timeout_id is not None:
        GLib.source_remove(refresh_timeout_id)
        refresh_timeout_id = None
    if reopen_timeout_id is not None:
        GLib.source_remove(reopen_timeout_id)
        reopen_timeout_id = None
    notification = None
    server_caps = None
    fallback_mode = False
    last_notification_payload = None


def _close_notification() -> None:
    global notification
    global suppress_reopen

    if notification is None:
        return

    try:
        suppress_reopen = True
        notification.close()
    except BaseException:
        pass
    finally:
        suppress_reopen = False


def _get_server_caps() -> set[str]:
    global server_caps

    if server_caps is not None:
        return server_caps

    try:
        caps = Notify.get_server_caps() or []
    except BaseException:
        caps = []

    server_caps = {str(cap) for cap in caps}
    return server_caps


def _create_notification() -> Notify.Notification:
    resident_notification = Notify.Notification.new(
        "Safe Eyes", "", icon="io.github.slgobinath.SafeEyes-enabled"
    )
    resident_notification.connect("closed", _on_notification_closed)
    caps = _get_server_caps()
    resident_notification.set_hint(
        "desktop-entry", GLib.Variant("s", "io.github.slgobinath.SafeEyes")
    )

    if _uses_temporary_mobile_notification():
        resident_notification.set_timeout(MOBILE_NOTIFICATION_TIMEOUT_MS)
        resident_notification.set_hint("resident", GLib.Variant("b", True))
        if _uses_temporary_phosh_notification():
            resident_notification.set_hint(
                "x-phosh-fb-profile", GLib.Variant("s", "quiet")
            )
    elif not fallback_mode:
        resident_notification.set_timeout(Notify.EXPIRES_NEVER)
        resident_notification.set_hint("resident", GLib.Variant("b", True))

    if "actions" in caps:
        resident_notification.add_action(
            "options", _("Options"), _on_options, None, None
        )
        resident_notification.add_action("quit", _("Quit"), _on_quit, None, None)

    return resident_notification


def _uses_temporary_phosh_notification() -> bool:
    return context is not None and context.desktop == "phosh"


def _uses_temporary_mobile_notification() -> bool:
    return context is not None and context.desktop in {
        "phosh",
        "plasma-mobile",
        "sxmo",
    }


def _refresh_all() -> None:
    utility.execute_main_thread(_schedule_refresh_ui)


def _schedule_refresh_ui(delay_ms: int = REFRESH_DEBOUNCE_MS) -> None:
    global refresh_timeout_id

    if refresh_timeout_id is not None:
        GLib.source_remove(refresh_timeout_id)

    refresh_timeout_id = GLib.timeout_add(delay_ms, _run_scheduled_refresh)


def _run_scheduled_refresh() -> bool:
    global refresh_timeout_id

    refresh_timeout_id = None
    _refresh_ui()
    return GLib.SOURCE_REMOVE


def _schedule_reopen_notification(delay_ms: int = REOPEN_DELAY_MS) -> None:
    global reopen_timeout_id

    if reopen_timeout_id is not None:
        GLib.source_remove(reopen_timeout_id)

    reopen_timeout_id = GLib.timeout_add(delay_ms, _run_reopen_notification)


def _run_reopen_notification() -> bool:
    global reopen_timeout_id
    global notification
    global last_notification_payload

    reopen_timeout_id = None
    notification = None
    last_notification_payload = None
    _refresh_all()
    return GLib.SOURCE_REMOVE


def _refresh_ui() -> None:
    _refresh_notification()
    if options_window is not None and options_window.get_visible():
        options_window.refresh()


def _refresh_notification() -> None:
    global notification
    global fallback_mode
    global last_notification_payload

    if context is None:
        return

    _ensure_notify()

    if notification is None:
        notification = _create_notification()

    body = _build_body()
    payload = (
        "Safe Eyes",
        body,
        "io.github.slgobinath.SafeEyes-enabled",
        fallback_mode,
    )
    if notification is not None and payload == last_notification_payload:
        return

    notification.update(payload[0], payload[1], payload[2])

    try:
        notification.show()
        last_notification_payload = payload
    except BaseException as error:
        error_text = str(error)
        if "ExcessNotificationGeneration" in error_text:
            logging.warning(
                "Resident notification rate-limited, retrying later: %s", error
            )
            _schedule_refresh_ui(RATE_LIMIT_RETRY_MS)
            return

        if not fallback_mode:
            logging.warning(
                "Resident notification failed, retrying with basic notification: %s",
                error,
            )
            fallback_mode = True
            _close_notification()
            notification = _create_notification()
            notification.update(payload[0], payload[1], payload[2])
            try:
                notification.show()
                last_notification_payload = (payload[0], payload[1], payload[2], True)
                return
            except BaseException as fallback_error:
                fallback_error_text = str(fallback_error)
                if "ExcessNotificationGeneration" in fallback_error_text:
                    logging.warning(
                        "Resident notification rate-limited after fallback, "
                        "retrying later: %s",
                        fallback_error,
                    )
                    _schedule_refresh_ui(RATE_LIMIT_RETRY_MS)
                    return
                logging.error(
                    "Failed to show the resident notification: %s", fallback_error
                )
                return

        logging.error("Failed to show the resident notification: %s", error)


def _on_notification_closed(closed_notification) -> None:
    global notification
    global last_notification_payload

    if notification is not closed_notification:
        return

    reason = closed_notification.get_closed_reason()
    notification = None
    last_notification_payload = None

    if suppress_reopen:
        return

    if _uses_temporary_mobile_notification():
        if reason == Notify.ClosedReason.DISMISSED:
            _schedule_reopen_notification()
        return

    if reason != Notify.ClosedReason.API_REQUEST:
        _schedule_reopen_notification()


def _build_body() -> str:
    if context is None:
        return "Safe Eyes"

    return build_info_message(
        context,
        active=is_active,
        wakeup_time=wakeup_time,
        next_break=_get_next_break_tuple(),
    )


def _get_next_break_tuple() -> typing.Optional[tuple[str, typing.Optional[str], bool]]:
    if context is None or not (
        context.api.has_breaks() and is_active and next_break_time
    ):
        return None

    formatted_time: str = utility.format_time(context.api.get_break_time())
    long_break_time = context.api.get_break_time(BreakType.LONG_BREAK)

    if long_break_time:
        formatted_long_time: str = utility.format_time(long_break_time)
        if formatted_long_time == formatted_time:
            return (formatted_long_time, formatted_long_time, True)
        return (formatted_time, formatted_long_time, False)

    return (formatted_time, None, False)


def _get_menu_items() -> list[dict]:
    if context is None:
        return []

    items = build_menu_items(
        context,
        tray_menu_config,
        _ResidentMenuCallbacks(),
        active=is_active,
        wakeup_time=wakeup_time,
        menu_locked=menu_locked,
        next_break=_get_next_break_tuple(),
    )
    return [item for item in items if item.get("id") != 8]


class _ResidentMenuCallbacks:
    def on_enable_clicked(self) -> None:
        global wakeup_time
        global resume_timeout_id

        if not is_active or wakeup_time is not None:
            wakeup_time = None
            if resume_timeout_id is not None:
                GLib.source_remove(resume_timeout_id)
                resume_timeout_id = None
            if context is not None:
                context.api.enable_safeeyes()
            _refresh_all()

    def on_disable_clicked(self, time_to_wait: int) -> None:
        global wakeup_time
        global resume_timeout_id

        if resume_timeout_id is not None:
            GLib.source_remove(resume_timeout_id)
            resume_timeout_id = None

        if time_to_wait <= 0:
            wakeup_time = None
            if context is not None:
                context.api.disable_safeeyes(_("Disabled until restart"))
        else:
            wakeup_time = datetime.datetime.now() + datetime.timedelta(
                minutes=time_to_wait
            )
            if context is not None:
                context.api.disable_safeeyes(
                    _("Disabled until %s") % utility.format_time(wakeup_time)
                )
            resume_timeout_id = GLib.timeout_add_seconds(
                time_to_wait * 60, _resume_safeeyes
            )
        _refresh_all()

    def on_manual_break_clicked(self, break_type: typing.Optional[BreakType]) -> None:
        if context is not None:
            context.api.take_break(break_type)

    def show_settings(self) -> None:
        if context is not None:
            context.api.show_settings()

    def show_about(self) -> None:
        if context is not None:
            context.api.show_about()

    def quit_safe_eyes(self) -> None:
        if context is not None:
            context.api.quit()


def _show_options_window() -> None:
    global options_window

    if options_window is None:
        options_window = ResidentOptionsWindow()
    else:
        options_window.refresh()

    options_window.present()


def _resume_safeeyes() -> bool:
    global wakeup_time
    global resume_timeout_id

    wakeup_time = None
    resume_timeout_id = None

    if context is not None:
        context.api.enable_safeeyes()

    _refresh_all()
    return GLib.SOURCE_REMOVE


def _on_options(notification_obj, action, user_data=None, *extra_args) -> None:
    del notification_obj, action, user_data, extra_args
    utility.execute_main_thread(_show_options_window)


def _on_quit(notification_obj, action, user_data=None, *extra_args) -> None:
    del notification_obj, action, user_data, extra_args

    if context is not None:
        context.api.quit()
