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

import signal
import sys
import typing

from safeeyes import translations
from safeeyes.model import Config
from safeeyes.safeeyes import SafeEyes

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

safe_eyes: typing.Optional[SafeEyes] = None


def main() -> None:
    """Start the Safe Eyes."""
    global safe_eyes

    # Handle Ctrl + C
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, sigint_caught)

    system_locale = translations.setup()

    config = Config.load()

    safe_eyes = SafeEyes(system_locale, config)
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
