#!/usr/bin/env python3
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
"""Safe Eyes is a utility to remind you to take break frequently to protect
your eyes from eye strain.
"""

import logging
import os
import signal
import sys
import typing


def _configure_frozen_logging() -> None:
    """When running as a frozen macOS .app bundle, redirect logs to
    ~/Library/Logs/SafeEyes/safeeyes.log so crash diagnostics are
    accessible even when launched from Finder (no terminal stdout).
    """
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return
    home = os.path.expanduser("~")
    log_dir = os.path.join(home, "Library", "Logs", "SafeEyes")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "safeeyes.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logging.info("SafeEyes starting (frozen bundle), logging to %s", log_file)


_configure_frozen_logging()

from safeeyes import translations  # noqa: E402 — must come after logging setup
from safeeyes.safeeyes import SafeEyes  # noqa: E402

import gi  # noqa: E402

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

safe_eyes: typing.Optional[SafeEyes] = None


def _self_test() -> int:
    """Import gi/Gtk and all plugins, then exit 0.  Used by build_mac.sh."""
    try:
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk  # noqa: F401

        logging.info("--self-test: gi.repository.Gtk 4.0 loaded OK")

        import importlib
        import os as _os

        from safeeyes import utility

        plugins_dir = utility.SYSTEM_PLUGINS_DIR
        errors = []
        for plugin_id in sorted(_os.listdir(plugins_dir)):
            plugin_py = _os.path.join(plugins_dir, plugin_id, "plugin.py")
            if not _os.path.isfile(plugin_py):
                continue
            try:
                importlib.import_module(f"safeeyes.plugins.{plugin_id}.plugin")
                logging.info("--self-test: plugin '%s' imported OK", plugin_id)
            except Exception as exc:
                logging.error("--self-test: plugin '%s' FAILED: %s", plugin_id, exc)
                errors.append(plugin_id)

        if errors:
            logging.error("--self-test FAILED for plugins: %s", errors)
            return 1
        logging.info("--self-test PASSED")
        return 0
    except Exception as exc:
        logging.exception("--self-test FAILED: %s", exc)
        return 1


def main() -> None:
    """Start the Safe Eyes."""
    global safe_eyes

    if "--self-test" in sys.argv:
        sys.exit(_self_test())

    # Handle Ctrl + C
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, sigint_caught)

    # Handle SIGTERM (e.g. from macOS Login Items / launchd)
    if sys.platform == "darwin":
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, sigint_caught)

    system_locale = translations.setup()

    safe_eyes = SafeEyes(system_locale)
    safe_eyes.run(sys.argv)


def sigint_caught() -> bool:
    global safe_eyes

    if safe_eyes is not None:
        # Call quit after the handler has been removed
        # This makes sure that a second Ctrl + C can just force quit
        # in case quitting also hangs
        GLib.idle_add(lambda: safe_eyes.quit())
    else:
        sys.exit(0)

    return GLib.SOURCE_REMOVE


if __name__ == "__main__":
    main()
