import os
import sys

# On macOS, dyld reads DYLD_FALLBACK_LIBRARY_PATH at process start.
# If running tests on macOS without Homebrew library path in environment,
# re-exec the pytest process with DYLD_FALLBACK_LIBRARY_PATH set.
if sys.platform == "darwin" and "_SAFEEYES_REEXECED" not in os.environ:
    _brew_lib = (
        "/opt/homebrew/lib"
        if os.path.isdir("/opt/homebrew")
        else "/usr/local/lib"
    )
    existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    if _brew_lib not in existing:
        new_dyld = (_brew_lib + ":" + existing) if existing else _brew_lib
        new_env = dict(
            os.environ,
            DYLD_FALLBACK_LIBRARY_PATH=new_dyld,
            _SAFEEYES_REEXECED="1",
        )
        os.execve(sys.executable, [sys.executable] + sys.argv, new_env)
