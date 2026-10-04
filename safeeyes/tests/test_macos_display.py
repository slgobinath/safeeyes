"""Tests for display-server detection helpers in utility.py."""
import importlib
import sys
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_utility(platform: str, env: dict):
    """Re-import utility with a patched sys.platform and os.environ."""
    import os

    with patch.dict(os.environ, env, clear=False), \
         patch.object(sys, "platform", platform):
        import safeeyes.utility as utility
        importlib.reload(utility)
        return utility


# ---------------------------------------------------------------------------
# is_macos()
# ---------------------------------------------------------------------------

class TestIsMacos:
    def test_returns_true_on_darwin(self):
        with patch.object(sys, "platform", "darwin"):
            import safeeyes.utility as u
            importlib.reload(u)
            assert u.is_macos() is True

    def test_returns_false_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            import safeeyes.utility as u
            importlib.reload(u)
            assert u.is_macos() is False


# ---------------------------------------------------------------------------
# is_x11() — depends on IS_MACOS and IS_WAYLAND module-level state
# ---------------------------------------------------------------------------

class TestIsX11:
    def test_x11_when_linux_no_wayland(self, monkeypatch):
        import safeeyes.utility as u
        monkeypatch.setattr(u, "IS_MACOS", False)
        monkeypatch.setattr(u, "IS_WAYLAND", False)
        assert u.is_x11() is True

    def test_not_x11_on_wayland(self, monkeypatch):
        import safeeyes.utility as u
        monkeypatch.setattr(u, "IS_MACOS", False)
        monkeypatch.setattr(u, "IS_WAYLAND", True)
        assert u.is_x11() is False

    def test_not_x11_on_macos(self, monkeypatch):
        import safeeyes.utility as u
        monkeypatch.setattr(u, "IS_MACOS", True)
        monkeypatch.setattr(u, "IS_WAYLAND", False)
        assert u.is_x11() is False

    def test_not_x11_on_macos_even_if_wayland_false(self, monkeypatch):
        """MacOS always returns False from is_x11()."""
        import safeeyes.utility as u
        monkeypatch.setattr(u, "IS_MACOS", True)
        monkeypatch.setattr(u, "IS_WAYLAND", False)
        assert u.is_x11() is False


# ---------------------------------------------------------------------------
# is_wayland() — existing behaviour, macOS branch
# ---------------------------------------------------------------------------

class TestIsWayland:
    def test_returns_false_on_macos(self):
        with patch.object(sys, "platform", "darwin"):
            import safeeyes.utility as u
            importlib.reload(u)
            result = u.is_wayland()
            assert result is False

    def test_detects_wayland_display_env(self, monkeypatch):
        import safeeyes.utility as u
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(u, "IS_MACOS", False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        result = u.is_wayland()
        assert result is True


# ---------------------------------------------------------------------------
# GI_TYPELIB_PATH bootstrap in __init__.py
# ---------------------------------------------------------------------------

class TestInitBootstrap:
    def test_sets_gi_typelib_path_when_frozen_and_dir_exists(
        self, tmp_path, monkeypatch
    ):
        """__init__.py should set GI_TYPELIB_PATH when frozen and dir exists."""
        import os
        # Create fake typelib dir
        typelib_dir = tmp_path / "Resources" / "girepository-1.0"
        typelib_dir.mkdir(parents=True)
        # Fake executable inside <bundle>/Contents/MacOS/
        macos_dir = tmp_path / "MacOS"
        macos_dir.mkdir()
        fake_exe = str(macos_dir / "SafeEyes")

        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", fake_exe)
        monkeypatch.delenv("GI_TYPELIB_PATH", raising=False)

        # Re-import __init__
        import safeeyes
        importlib.reload(safeeyes)

        assert "GI_TYPELIB_PATH" in os.environ
        assert os.environ["GI_TYPELIB_PATH"] == str(typelib_dir)

    def test_does_not_set_gi_typelib_path_when_dir_missing(self, tmp_path, monkeypatch):
        import os
        macos_dir = tmp_path / "MacOS"
        macos_dir.mkdir()
        fake_exe = str(macos_dir / "SafeEyes")

        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", fake_exe)
        monkeypatch.delenv("GI_TYPELIB_PATH", raising=False)

        import safeeyes
        importlib.reload(safeeyes)

        assert "GI_TYPELIB_PATH" not in os.environ

    def test_no_op_on_linux(self, monkeypatch):
        import os
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("GI_TYPELIB_PATH", raising=False)

        import safeeyes
        importlib.reload(safeeyes)

        assert "GI_TYPELIB_PATH" not in os.environ
