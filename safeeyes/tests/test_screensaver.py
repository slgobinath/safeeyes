# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2025  Mel Dafert <m@dafert.at>

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

import gettext
import importlib
import logging
import sys
import threading
import time
import types
import typing
from unittest import mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

# CI has Gtk but not the X11 typelib. BreakScreen imports GdkX11 at module
# scope; provide a stub so collection does not require that typelib.
try:
    importlib.import_module("gi.repository.GdkX11")
except ImportError:
    _gdk_x11 = types.ModuleType("gi.repository.GdkX11")
    setattr(_gdk_x11, "X11Surface", type("X11Surface", (), {}))
    sys.modules["gi.repository.GdkX11"] = _gdk_x11

from safeeyes.context import API
from safeeyes.context import Context
from safeeyes.plugins.screensaver import plugin as screensaver_plugin
from safeeyes.ui.break_screen import BreakScreen

# Attribute access is name-mangled inside the test class, so bind these here.
lock_screen_now = screensaver_plugin.__lock_screen_now
lock_screen_command = screensaver_plugin.__lock_screen_command


class TestScreensaverKeyboardGrab:
    def _x11_display(self) -> tuple[list[str], mock.Mock, threading.Event]:
        calls: list[str] = []
        ready = threading.Event()
        display = mock.Mock()
        display.pending_events.return_value = 0

        def flush() -> None:
            calls.append("flush")
            ready.set()

        def record(name: str) -> typing.Callable[..., None]:
            def side_effect(*_args: object, **_kwargs: object) -> None:
                calls.append(name)

            return side_effect

        display.flush.side_effect = flush
        display.ungrab_keyboard.side_effect = record("ungrab")
        display.sync.side_effect = record("sync")
        display.screen.return_value.root.grab_keyboard.side_effect = record("grab")
        return calls, display, ready

    def _make_screen(
        self,
        display: mock.Mock,
        *,
        is_wayland: bool = False,
    ) -> BreakScreen:
        ctx = Context(
            api=mock.Mock(spec=API),
            locale=gettext.NullTranslations(),
            version="0.0.0",
            session={},
        )
        ctx.is_wayland = is_wayland
        application = typing.cast(Gtk.Application, mock.Mock())

        def build() -> BreakScreen:
            return BreakScreen(application, ctx, lambda: None, lambda: None)

        if is_wayland:
            return build()
        with mock.patch("Xlib.display.Display", return_value=display):
            return build()

    def _start(self, screen: BreakScreen, ready: threading.Event) -> None:
        getattr(screen, "_BreakScreen__start_keyboard_lock_x11")()
        assert ready.wait(2)

    def _grabbed_screen(self) -> tuple[BreakScreen, list[str]]:
        calls, display, ready = self._x11_display()
        screen = self._make_screen(display)
        self._start(screen, ready)
        return screen, calls

    def _bind_plugin(
        self,
        monkeypatch: pytest.MonkeyPatch,
        screen: BreakScreen,
        command: typing.Union[list[str], typing.Callable[[], None], None],
    ) -> None:
        application = mock.Mock()
        application.break_screen = screen
        screen.context.api = API(application)
        monkeypatch.setattr(screensaver_plugin, "context", screen.context)
        monkeypatch.setattr(screensaver_plugin, "lock_screen_command", command)

    def test_skip_break_releases_keyboard_before_on_skipped(self) -> None:
        screen, calls = self._grabbed_screen()
        seen: list[list[str]] = []
        screen.on_skipped = lambda: seen.append(calls.copy())
        try:
            started = time.monotonic()
            screen.skip_break()
            assert time.monotonic() - started < 0.5
            assert seen == [["grab", "flush", "ungrab", "sync"]]
            # close() releases again and must not grab or ungrab a second time
            assert calls == ["grab", "flush", "ungrab", "sync"]
        finally:
            screen.release_keyboard()

    def test_postpone_break_releases_keyboard_before_on_postponed(self) -> None:
        screen, calls = self._grabbed_screen()
        seen: list[list[str]] = []
        screen.on_postponed = lambda: seen.append(calls.copy())
        try:
            started = time.monotonic()
            screen.postpone_break()
            assert time.monotonic() - started < 0.5
            assert seen == [["grab", "flush", "ungrab", "sync"]]
            assert calls == ["grab", "flush", "ungrab", "sync"]
        finally:
            screen.release_keyboard()

    def test_close_ungrabs_before_returning(self) -> None:
        screen, calls = self._grabbed_screen()
        try:
            started = time.monotonic()
            screen.close()
            assert time.monotonic() - started < 0.5
            assert calls == ["grab", "flush", "ungrab", "sync"]
        finally:
            screen.release_keyboard()

    def test_release_keyboard_wakes_immediately(self) -> None:
        screen, calls = self._grabbed_screen()
        try:
            started = time.monotonic()
            screen.release_keyboard()
            assert time.monotonic() - started < 0.5
            assert calls == ["grab", "flush", "ungrab", "sync"]
            assert screen._keyboard_lock_thread is None
        finally:
            screen.release_keyboard()

    def test_lock_screen_now_releases_before_callable_and_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen, calls = self._grabbed_screen()
        seen: list[list[str]] = []

        def dbus_lock() -> None:
            seen.append(calls.copy())

        self._bind_plugin(monkeypatch, screen, dbus_lock)
        try:
            lock_screen_now()
            assert seen == [["grab", "flush", "ungrab", "sync"]]
        finally:
            screen.release_keyboard()

        calls, display, ready = self._x11_display()
        screen = self._make_screen(display)
        self._start(screen, ready)
        executed: list[list[str]] = []

        def execute_command(command: list[str], *_args: object) -> None:
            executed.append(calls.copy())
            assert command == ["loginctl", "lock-session"]

        monkeypatch.setattr(
            screensaver_plugin.utility, "execute_command", execute_command
        )
        self._bind_plugin(monkeypatch, screen, ["loginctl", "lock-session"])
        try:
            lock_screen_now()
            assert executed == [["grab", "flush", "ungrab", "sync"]]
        finally:
            screen.release_keyboard()

    def test_release_keyboard_is_noop_on_wayland_and_idempotent(self) -> None:
        wayland = self._make_screen(mock.Mock(), is_wayland=True)
        skipped: list[str] = []
        wayland.on_skipped = lambda: skipped.append("skipped")
        wayland.release_keyboard()
        wayland.release_keyboard()
        assert wayland._keyboard_lock_thread is None
        assert not wayland._keyboard_release_event.is_set()
        wayland.skip_break()
        assert skipped == ["skipped"]

        calls, display, ready = self._x11_display()
        screen = self._make_screen(display)
        # Releasing before a break must not block a later grab.
        screen.release_keyboard()
        screen.release_keyboard()
        self._start(screen, ready)
        thread = screen._keyboard_lock_thread
        assert thread is not None
        thread.join(timeout=0.2)
        assert thread.is_alive()
        assert calls == ["grab", "flush"]

        seen: list[list[str]] = []
        screen.on_skipped = lambda: seen.append(calls.copy())
        try:
            screen.skip_break()
            assert seen == [["grab", "flush", "ungrab", "sync"]]
            assert calls.count("ungrab") == 1
            assert calls.count("sync") == 1
            screen.release_keyboard()
            assert calls.count("ungrab") == 1
        finally:
            screen.release_keyboard()

    def test_lock_screen_now_without_command_does_not_release(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen, calls = self._grabbed_screen()
        self._bind_plugin(monkeypatch, screen, None)
        try:
            lock_screen_now()
            assert calls == ["grab", "flush"]
            thread = screen._keyboard_lock_thread
            assert thread is not None
            assert thread.is_alive()
        finally:
            screen.release_keyboard()

    def test_event_read_failure_still_ungrabs(self) -> None:
        calls, display, ready = self._x11_display()
        display.pending_events.return_value = 1
        display.next_event.side_effect = RuntimeError("x11 event read failed")
        screen = self._make_screen(display)
        errors: list[BaseException] = []
        previous_hook = threading.excepthook

        def hook(args: threading.ExceptHookArgs) -> None:
            if args.exc_value is not None:
                errors.append(args.exc_value)

        threading.excepthook = hook
        try:
            self._start(screen, ready)
            thread = screen._keyboard_lock_thread
            assert thread is not None
            thread.join(timeout=2)
            assert not thread.is_alive()
            assert calls == ["grab", "flush", "ungrab", "sync"]
            assert len(errors) == 1
            assert isinstance(errors[0], RuntimeError)
        finally:
            threading.excepthook = previous_hook
            screen.release_keyboard()

    def test_flush_failure_after_grab_still_ungrabs(self) -> None:
        calls, display, _ready = self._x11_display()

        def flush() -> None:
            calls.append("flush")
            raise RuntimeError("flush failed")

        display.flush.side_effect = flush
        screen = self._make_screen(display)
        errors: list[BaseException] = []
        previous_hook = threading.excepthook

        def hook(args: threading.ExceptHookArgs) -> None:
            if args.exc_value is not None:
                errors.append(args.exc_value)

        threading.excepthook = hook
        try:
            getattr(screen, "_BreakScreen__start_keyboard_lock_x11")()
            thread = screen._keyboard_lock_thread
            assert thread is not None
            thread.join(timeout=2)
            assert not thread.is_alive()
            assert calls == ["grab", "flush", "ungrab", "sync"]
            assert len(errors) == 1
            assert isinstance(errors[0], RuntimeError)
            # The finally block confirmed the unlock, so release can drop it.
            screen.release_keyboard()
            assert screen._keyboard_lock_thread is None
            assert screen._keyboard_grab_held is False
        finally:
            threading.excepthook = previous_hook
            screen.release_keyboard()

    def test_grab_failure_still_ungrabs(self) -> None:
        calls, display, _ready = self._x11_display()

        def grab(*_args: object, **_kwargs: object) -> None:
            calls.append("grab")
            raise RuntimeError("grab failed after the server accepted it")

        display.screen.return_value.root.grab_keyboard.side_effect = grab
        screen = self._make_screen(display)
        errors: list[BaseException] = []
        previous_hook = threading.excepthook

        def hook(args: threading.ExceptHookArgs) -> None:
            if args.exc_value is not None:
                errors.append(args.exc_value)

        threading.excepthook = hook
        try:
            getattr(screen, "_BreakScreen__start_keyboard_lock_x11")()
            thread = screen._keyboard_lock_thread
            assert thread is not None
            thread.join(timeout=2)
            assert not thread.is_alive()
            assert calls == ["grab", "ungrab", "sync"]
            assert len(errors) == 1
            assert isinstance(errors[0], RuntimeError)
        finally:
            threading.excepthook = previous_hook
            screen.release_keyboard()

    @pytest.mark.parametrize("failing", ["ungrab", "sync"])
    def test_release_keyboard_retries_failed_unlock(
        self, failing: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        calls, display, ready = self._x11_display()
        attempts = {"ungrab": 0, "sync": 0}

        def ungrab(*_args: object, **_kwargs: object) -> None:
            calls.append("ungrab")
            attempts["ungrab"] += 1
            if failing == "ungrab" and attempts["ungrab"] == 1:
                raise RuntimeError("ungrab failed")

        def sync(*_args: object, **_kwargs: object) -> None:
            calls.append("sync")
            attempts["sync"] += 1
            if failing == "sync" and attempts["sync"] == 1:
                raise RuntimeError("sync failed")

        display.ungrab_keyboard.side_effect = ungrab
        display.sync.side_effect = sync
        screen = self._make_screen(display)
        self._start(screen, ready)
        try:
            with caplog.at_level(logging.ERROR):
                screen.release_keyboard()
            assert screen._keyboard_lock_thread is None
            assert screen._keyboard_grab_held is False
            assert screen._keyboard_release_error is None
            # The worker's failed attempt is retried by release_keyboard.
            assert attempts[failing] == 2
            assert calls.count("ungrab") == 2
            assert calls.count("sync") == 2
            assert "retrying unlock" in caplog.text
        finally:
            screen.release_keyboard()

    def test_release_keyboard_keeps_grab_when_unlock_keeps_failing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        calls, display, ready = self._x11_display()

        def ungrab(*_args: object, **_kwargs: object) -> None:
            calls.append("ungrab")
            raise RuntimeError("ungrab failed")

        display.ungrab_keyboard.side_effect = ungrab
        screen = self._make_screen(display)
        self._start(screen, ready)
        try:
            with caplog.at_level(logging.ERROR):
                screen.release_keyboard()
            kept = screen._keyboard_lock_thread
            assert kept is not None
            assert not kept.is_alive()
            assert screen._keyboard_grab_held is True
            assert isinstance(screen._keyboard_release_error, RuntimeError)
            assert "Failed to ungrab the X11 keyboard" in caplog.text
            assert "keeping lock thread" in caplog.text

            # A later release retries and still does not drop the owner.
            screen.release_keyboard()
            assert screen._keyboard_lock_thread is kept
            assert screen._keyboard_grab_held is True
            assert calls.count("ungrab") == 3

            # A new break must not replace the thread that still owns the grab.
            getattr(screen, "_BreakScreen__start_keyboard_lock_x11")()
            assert screen._keyboard_lock_thread is kept
            assert calls.count("grab") == 1
            assert "keeping the existing lock thread" in caplog.text
        finally:
            screen.release_keyboard()

    @pytest.mark.parametrize(
        "env",
        [
            {"DESKTOP_SESSION": "plasmax11"},
            {"KDE_FULL_SESSION": "true"},
            {"XDG_CURRENT_DESKTOP": "KDE"},
        ],
    )
    def test_lock_screen_command_detects_kde(
        self, monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
    ) -> None:
        for name in (
            "DESKTOP_SESSION",
            "XDG_CURRENT_DESKTOP",
            "KDE_FULL_SESSION",
            "GNOME_DESKTOP_SESSION_ID",
        ):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)

        dbus_calls: list[tuple[str, str, str]] = []

        def fake_dbus(destination: str, path: str, method: str) -> None:
            dbus_calls.append((destination, path, method))

        monkeypatch.setattr(screensaver_plugin, "__lock_screen_dbus", fake_dbus)
        command = lock_screen_command()
        assert command is not None
        assert not isinstance(command, list)
        command()
        assert dbus_calls == [("org.freedesktop.ScreenSaver", "/ScreenSaver", "Lock")]

    def test_restore_keyboard_retries_until_grab_succeeds(self) -> None:
        from Xlib import X

        calls, display, ready = self._x11_display()
        statuses = iter([X.AlreadyGrabbed, X.AlreadyGrabbed, X.GrabSuccess])

        def grab(*_args: object, **_kwargs: object) -> int:
            calls.append("grab")
            return next(statuses)

        display.screen.return_value.root.grab_keyboard.side_effect = grab
        screen = self._make_screen(display)
        screen.windows.append(mock.Mock())
        screen.keyboard_regrab_delay = 0.0
        screen.keyboard_regrab_interval = 0.0
        try:
            screen.restore_keyboard()
            assert ready.wait(2)
            assert calls == ["grab", "grab", "grab", "flush"]
            assert screen._keyboard_grab_held is True
            thread = screen._keyboard_lock_thread
            assert thread is not None
            assert thread.is_alive()

            # Calling restore again while the worker is alive does not spawn another.
            screen.restore_keyboard()
            assert screen._keyboard_lock_thread is thread

            screen.close()
            assert calls == ["grab", "grab", "grab", "flush", "ungrab", "sync"]
            assert screen._keyboard_grab_held is False
            assert screen._keyboard_lock_thread is None
        finally:
            screen.release_keyboard()

    def test_restore_keyboard_is_noop_on_wayland_and_without_windows(self) -> None:
        wayland = self._make_screen(mock.Mock(), is_wayland=True)
        wayland.windows.append(mock.Mock())
        wayland.restore_keyboard()
        assert wayland._keyboard_lock_thread is None

        calls, display, _ready = self._x11_display()
        screen = self._make_screen(display)
        screen.keyboard_regrab_delay = 0.0
        screen.keyboard_regrab_interval = 0.0
        screen.restore_keyboard()
        assert screen._keyboard_lock_thread is None
        assert calls == []

    def test_release_keyboard_during_regrab_wait_stops_without_grabbing(self) -> None:
        from Xlib import X

        calls, display, _ready = self._x11_display()
        screen = self._make_screen(display)
        screen.windows.append(mock.Mock())
        screen.keyboard_regrab_delay = 5.0
        try:
            screen.restore_keyboard()
            thread = screen._keyboard_lock_thread
            assert thread is not None
            started = time.monotonic()
            screen.release_keyboard()
            assert time.monotonic() - started < 0.5
            assert not thread.is_alive()
            assert screen._keyboard_lock_thread is None
            assert screen._keyboard_grab_held is False
            assert calls == []
        finally:
            screen.release_keyboard()

        # Releasing while waiting between AlreadyGrabbed retries does not ungrab.
        calls, display, _ready = self._x11_display()
        attempted = threading.Event()

        def grab(*_args: object, **_kwargs: object) -> int:
            calls.append("grab")
            attempted.set()
            return X.AlreadyGrabbed

        display.screen.return_value.root.grab_keyboard.side_effect = grab
        screen = self._make_screen(display)
        screen.windows.append(mock.Mock())
        screen.keyboard_regrab_delay = 0.0
        screen.keyboard_regrab_interval = 5.0
        try:
            screen.restore_keyboard()
            assert attempted.wait(2)
            started = time.monotonic()
            screen.release_keyboard()
            assert time.monotonic() - started < 0.5
            assert screen._keyboard_lock_thread is None
            assert screen._keyboard_grab_held is False
            assert calls == ["grab"]
        finally:
            screen.release_keyboard()

    def test_lock_screen_now_restores_keyboard_after_lock_and_on_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from Xlib import X

        calls, display, ready = self._x11_display()
        statuses = iter([X.GrabSuccess, X.AlreadyGrabbed, X.GrabSuccess])

        def grab(*_args: object, **_kwargs: object) -> int:
            calls.append("grab")
            return next(statuses)

        display.screen.return_value.root.grab_keyboard.side_effect = grab
        screen = self._make_screen(display)
        screen.windows.append(mock.Mock())
        screen.keyboard_regrab_delay = 0.0
        screen.keyboard_regrab_interval = 0.0
        self._start(screen, ready)
        ready.clear()

        seen: list[list[str]] = []

        def execute_command(command: list[str], *_args: object) -> None:
            seen.append(calls.copy())
            assert command == ["loginctl", "lock-session"]

        monkeypatch.setattr(
            screensaver_plugin.utility, "execute_command", execute_command
        )
        self._bind_plugin(monkeypatch, screen, ["loginctl", "lock-session"])
        try:
            lock_screen_now()
            assert seen == [["grab", "flush", "ungrab", "sync"]]
            assert ready.wait(2)
            assert calls == [
                "grab",
                "flush",
                "ungrab",
                "sync",
                "grab",
                "grab",
                "flush",
            ]
            assert screen._keyboard_grab_held is True
            screen.release_keyboard()
            assert calls == [
                "grab",
                "flush",
                "ungrab",
                "sync",
                "grab",
                "grab",
                "flush",
                "ungrab",
                "sync",
            ]
        finally:
            screen.release_keyboard()

        calls, display, ready = self._x11_display()

        def grab_ok(*_args: object, **_kwargs: object) -> int:
            calls.append("grab")
            return X.GrabSuccess

        display.screen.return_value.root.grab_keyboard.side_effect = grab_ok
        screen = self._make_screen(display)
        screen.windows.append(mock.Mock())
        screen.keyboard_regrab_delay = 0.0
        screen.keyboard_regrab_interval = 0.0
        self._start(screen, ready)
        ready.clear()

        def failing_lock() -> None:
            raise RuntimeError("lock failed")

        self._bind_plugin(monkeypatch, screen, failing_lock)
        try:
            with pytest.raises(RuntimeError, match="lock failed"):
                lock_screen_now()
            assert ready.wait(2)
            assert calls == ["grab", "flush", "ungrab", "sync", "grab", "flush"]
            assert screen._keyboard_grab_held is True
            screen.release_keyboard()
            assert calls == [
                "grab",
                "flush",
                "ungrab",
                "sync",
                "grab",
                "flush",
                "ungrab",
                "sync",
            ]
        finally:
            screen.release_keyboard()
