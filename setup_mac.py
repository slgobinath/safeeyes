#!/usr/bin/env python3
"""py2app build configuration for SafeEyes macOS bundle.

Run via build_mac.sh which handles the venv, dependency installation,
and post-build steps (dylib bundling, codesign, DMG creation).

Do NOT run this directly for development installs — use pip install -e .
"""
import os
import tomllib
from setuptools import setup

# ---------------------------------------------------------------------------
# Read version from pyproject.toml without importing the package
# ---------------------------------------------------------------------------
with open("pyproject.toml", "rb") as _f:
    _meta = tomllib.load(_f)

_version = _meta["project"]["version"]

# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------
APP = ["safeeyes/__main__.py"]

# ---------------------------------------------------------------------------
# Data files: all non-.pyc files under the listed directories
# ---------------------------------------------------------------------------

def _collect_data(directory: str):
    """Walk *directory* and return (dest_dir, [src_files]) pairs for data_files."""
    result = []
    for root, _dirs, files in os.walk(directory):
        valid = [
            os.path.join(root, f)
            for f in files
            if not f.endswith(".pyc") and "__pycache__" not in root
        ]
        if valid:
            result.append((root, valid))
    return result


DATA_FILES: list = []
for _d in (
    "safeeyes/glade",
    "safeeyes/platform",
    "safeeyes/config",
    "safeeyes/resource",
    "safeeyes/plugins",
):
    DATA_FILES.extend(_collect_data(_d))

# ---------------------------------------------------------------------------
# py2app options
# ---------------------------------------------------------------------------
OPTIONS = {
    "argv_emulation": False,  # Never: blocks Cocoa run loop
    "plist": {
        # Run as a menu-bar–only app — no Dock icon
        "LSUIElement": True,
        "CFBundleIdentifier": "io.github.Mohamed-elgypaly.SafeEyes",
        "CFBundleName": "SafeEyes",
        "CFBundleDisplayName": "SafeEyes",
        "CFBundleVersion": _version,
        "CFBundleShortVersionString": _version,
        # Notification permission usage string (required for UNUserNotificationCenter)
        "NSUserNotificationAlertStyle": "alert",
        "NSHumanReadableCopyright": "© 2016 Gobinath Loganathan — GPL-3.0-or-later",
        # Minimum macOS version (Apple Silicon baseline)
        "LSMinimumSystemVersion": "12.0",
    },
    "packages": ["safeeyes"],
    # Only genuine Python-level modules that py2app can't auto-discover.
    # DO NOT list PyGTK 2 names (gtk, pango, atk, gobject, gio, pangocairo).
    "includes": [
        "gi",           # PyGObject – typelib loader
        "cairo",        # pycairo
        "babel",        # localisation
        "croniter",     # healthstats plugin
        "packaging",    # version comparisons
        "pystray",      # fallback tray backend
        "logging.handlers",   # RotatingFileHandler
        # PyObjC frameworks used by the tray / notification / idle modules
        "objc",
        "Foundation",
        "AppKit",
        "Quartz",
        "UserNotifications",
    ],
    # Exclude heavy packages not needed in the bundle
    "excludes": [
        "tkinter",
        "test",
        "distutils",
    ],
}

setup(
    name="SafeEyes",
    version=_version,
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
