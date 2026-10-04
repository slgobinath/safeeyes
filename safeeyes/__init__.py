# macOS py2app bundle bootstrap.
#
# This file runs first when the safeeyes package is imported, before any
# submodule (translations.py, utility.py, …) can execute their top-level
# 'import gi' / 'gi.require_version(…)' calls.
#
# We set every environment variable that PyGObject and GTK 4 need to find
# their resources inside the .app bundle.  Nothing here runs on Linux.
import os
import sys

if sys.platform == "darwin":
    _fw_dir = ""
    if getattr(sys, "frozen", False) or "SafeEyes.app" in (sys.executable or ""):
        # .app Contents/MacOS/<binary> → Contents/Resources
        _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        _res_dir = os.path.abspath(os.path.join(_exe_dir, "..", "Resources"))
        _fw_dir = os.path.abspath(os.path.join(_exe_dir, "..", "Frameworks"))

        # 1. GObject-introspection typelibs
        _typelib_dir = os.path.join(_res_dir, "girepository-1.0")
        if os.path.isdir(_typelib_dir):
            os.environ["GI_TYPELIB_PATH"] = _typelib_dir

        # 2. GSettings / GLib schemas
        _schema_dir = os.path.join(_res_dir, "share", "glib-2.0", "schemas")
        if os.path.isdir(_schema_dir):
            os.environ["GSETTINGS_SCHEMA_DIR"] = _schema_dir

        # 3. XDG_DATA_DIRS for icon themes, etc.
        _share_dir = os.path.join(_res_dir, "share")
        if os.path.isdir(_share_dir):
            existing_xdg = os.environ.get("XDG_DATA_DIRS", "")
            os.environ["XDG_DATA_DIRS"] = (
                _share_dir + (":" + existing_xdg if existing_xdg else "")
            )

    # 4. Homebrew shared libraries (Frameworks dir first, then Homebrew prefix)
    _brew_lib = (
        "/opt/homebrew/lib"
        if os.path.isdir("/opt/homebrew")
        else "/usr/local/lib"
    )
    _dyld_paths = ":".join(
        filter(None, [_fw_dir if os.path.isdir(_fw_dir) else "", _brew_lib])
    )
    if _dyld_paths:
        existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        if _brew_lib not in existing:
            new_dyld = _dyld_paths + (":" + existing if existing else "")
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = new_dyld
            if (
                "_SAFEEYES_REEXECED" not in os.environ
                and not getattr(sys, "frozen", False)
            ):
                os.environ["_SAFEEYES_REEXECED"] = "1"
                os.execve(sys.executable, [sys.executable] + sys.argv, os.environ)

