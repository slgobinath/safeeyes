#!/usr/bin/env bash
# ==============================================================================
# build_mac.sh – Build SafeEyes.app for macOS
#
# Usage:
#   ./build_mac.sh [--clean] [--no-autostart] [--sign] [--dmg]
#
#   --clean        : Remove .venv_mac, build/, dist/ before starting
#   --no-autostart : Skip Login Items registration
#   --sign         : Ad-hoc code-sign the .app and all bundled dylibs
#   --dmg          : Create a distributable DMG after the build
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Defaults ──────────────────────────────────────────────────────────────────
OPT_CLEAN=false
OPT_NO_AUTOSTART=false
OPT_SIGN=false
OPT_DMG=false

for arg in "$@"; do
  case "$arg" in
    --clean)        OPT_CLEAN=true ;;
    --no-autostart) OPT_NO_AUTOSTART=true ;;
    --sign)         OPT_SIGN=true ;;
    --dmg)          OPT_DMG=true ;;
    *)
      echo "Unknown option: $arg"
      echo "Usage: $0 [--clean] [--no-autostart] [--sign] [--dmg]"
      exit 1 ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
die() { echo "ERROR: $*" >&2; exit 1; }
require_cmd() { command -v "$1" &>/dev/null || die "'$1' not found. $2"; }
section() { echo; echo "══════════════════════════════════════════════════"; echo "  $*"; echo "══════════════════════════════════════════════════"; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
section "Pre-flight checks"

require_cmd brew  "Install Homebrew from https://brew.sh"
require_cmd python3 "Install Python 3.10+ from https://python.org"

# Python version check (>=3.10)
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER##*.}"
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10) ]]; then
  die "Python 3.10+ required, found $PY_VER"
fi
echo "Python: $PY_VER  ✓"

# Homebrew dependency checks
for pkg in gtk4 gobject-introspection glib libffi gettext; do
  if ! brew list --formula "$pkg" &>/dev/null; then
    die "Homebrew package '$pkg' not installed. Run: brew install gtk4 gobject-introspection glib"
  fi
  echo "brew $pkg  ✓"
done

# Detect Homebrew prefix (Apple Silicon vs Intel)
BREW_PREFIX="$(brew --prefix)"
GI_SRC="$BREW_PREFIX/lib/girepository-1.0"
BREW_LIB="$BREW_PREFIX/lib"
[[ -d "$GI_SRC" ]] || die "girepository-1.0 directory not found at $GI_SRC"

# ── Clean ─────────────────────────────────────────────────────────────────────
if $OPT_CLEAN; then
  section "Cleaning previous build artifacts"
  rm -rf .venv_mac build dist
  echo "Clean done."
fi

# ── Virtual environment ───────────────────────────────────────────────────────
section "Setting up Python virtual environment"
VENV_DIR=".venv_mac"
if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating venv..."
  python3 -m venv "$VENV_DIR"
fi
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

section "Installing Python dependencies"
pip install --upgrade --quiet pip setuptools wheel

# Core runtime deps
pip install --quiet PyGObject babel packaging

# macOS extras (pystray, PyObjC, Pillow, croniter)
pip install --quiet pystray Pillow pyobjc-core pyobjc-framework-Cocoa \
  pyobjc-framework-Quartz pyobjc-framework-UserNotifications croniter

# Build tooling
pip install --quiet py2app

# Install safeeyes itself (no-deps: avoid pulling python-xlib on macOS)
pip install --quiet --no-deps -e .

echo "==> Dependencies installed."

# ── Compile translations ───────────────────────────────────────────────────────
section "Compiling translations"
if command -v msgfmt &>/dev/null; then
  python3 setup.py build_mo 2>/dev/null && echo "Translations compiled." || echo "Warning: build_mo failed (non-fatal)."
else
  echo "msgfmt not found, skipping translation compilation."
fi

# ── Build .app bundle ─────────────────────────────────────────────────────────
section "Building SafeEyes.app via py2app"
rm -rf build dist

# setup_mac.py no longer needs pyproject.toml moved away — the monkey-patch is gone.
python3 setup_mac.py py2app

APP_BUNDLE="$SCRIPT_DIR/dist/SafeEyes.app"
[[ -d "$APP_BUNDLE" ]] || die "py2app finished but $APP_BUNDLE not found"
echo "py2app build succeeded: $APP_BUNDLE"

# ── Bundle typelibs ───────────────────────────────────────────────────────────
section "Bundling GObject-Introspection typelibs"
GI_DEST="$APP_BUNDLE/Contents/Resources/girepository-1.0"
mkdir -p "$GI_DEST"
if ls "$GI_SRC"/*.typelib &>/dev/null; then
  cp "$GI_SRC"/*.typelib "$GI_DEST/"
  echo "Copied $(ls "$GI_DEST"/*.typelib | wc -l | tr -d ' ') typelibs."
else
  echo "Warning: No typelibs found at $GI_SRC — the app may fail to load GTK."
fi

# ── Bundle shared libraries (dylibbundler or manual copy) ─────────────────────
section "Bundling shared libraries into Contents/Frameworks"
FRAMEWORKS="$APP_BUNDLE/Contents/Frameworks"
mkdir -p "$FRAMEWORKS"

if command -v dylibbundler &>/dev/null; then
  echo "==> Using dylibbundler..."
  # Bundle the main executable's deps
  dylibbundler -od -b \
    -x "$APP_BUNDLE/Contents/MacOS/SafeEyes" \
    -d "$FRAMEWORKS" \
    -p "@executable_path/../Frameworks/" \
    -s "$BREW_LIB" \
    --ignore /usr/lib \
    --ignore /System
  echo "dylibbundler done."
else
  echo "==> dylibbundler not found (brew install dylibbundler to enable fully standalone bundle)."
  echo "    Setting DYLD_FALLBACK_LIBRARY_PATH as runtime fallback — Homebrew must be installed on target Mac."
  # At minimum, copy the key GTK/GLib dylibs so the app can launch on another machine
  KEY_LIBS=(
    "libgtk-4" "libgdk-4" "libglib-2.0" "libgobject-2.0" "libgio-2.0"
    "libgmodule-2.0" "libpango-1.0" "libpangocairo-1.0" "libcairo"
    "libcairo-gobject" "libgdk_pixbuf-2.0" "libharfbuzz" "libffi"
    "libintl" "libfontconfig" "libfreetype" "libpixman-1"
    "libgraphene-1.0" "libepoxy"
  )
  for lib_name in "${KEY_LIBS[@]}"; do
    # Find the versioned .dylib
    found="$(ls "$BREW_LIB/${lib_name}".*.dylib 2>/dev/null | head -1 || true)"
    if [[ -n "$found" ]]; then
      cp "$found" "$FRAMEWORKS/"
      echo "  Copied $(basename "$found")"
    fi
  done
fi

# ── Bundle GLib/GTK schemas ───────────────────────────────────────────────────
section "Bundling GLib schemas and icon theme"
SHARE_SRC="$BREW_PREFIX/share"
SHARE_DEST="$APP_BUNDLE/Contents/Resources/share"
mkdir -p "$SHARE_DEST"

# GLib schemas (required by many GTK 4 widgets)
if [[ -d "$SHARE_SRC/glib-2.0/schemas" ]]; then
  mkdir -p "$SHARE_DEST/glib-2.0"
  cp -R "$SHARE_SRC/glib-2.0/schemas" "$SHARE_DEST/glib-2.0/"
  echo "Copied GLib schemas."
fi

# GTK 4 default theme / icons (minimal, avoids blank icons)
for d in "icons/hicolor" "themes/Default" "themes/Adwaita"; do
  src="$SHARE_SRC/$d"
  if [[ -d "$src" ]]; then
    mkdir -p "$SHARE_DEST/$(dirname "$d")"
    cp -Rn "$src" "$SHARE_DEST/$(dirname "$d")/" 2>/dev/null || true
    echo "Copied $d."
  fi
done

# ── Ad-hoc code signing ───────────────────────────────────────────────────────
if $OPT_SIGN; then
  section "Ad-hoc code signing"
  require_cmd codesign "Install Xcode Command Line Tools: xcode-select --install"
  # Sign all dylibs first, then the app
  find "$APP_BUNDLE/Contents/Frameworks" -name "*.dylib" -exec \
    codesign --force --sign - --timestamp=none {} \;
  codesign --force --deep --sign - --timestamp=none "$APP_BUNDLE"
  echo "Ad-hoc signing done."
fi

# ── Self-test ─────────────────────────────────────────────────────────────────
section "Running bundle self-test"
if "$APP_BUNDLE/Contents/MacOS/SafeEyes" --self-test; then
  echo "Self-test PASSED ✓"
else
  echo "WARNING: Self-test failed. The app may not run correctly." >&2
  # Don't die here — let the user decide; build artifacts are still useful
fi

# ── DMG creation ─────────────────────────────────────────────────────────────
if $OPT_DMG; then
  section "Creating DMG"
  require_cmd hdiutil "hdiutil should be built into macOS"
  DMG_PATH="$SCRIPT_DIR/dist/SafeEyes-$(python3 -c "import tomllib; v=tomllib.load(open('pyproject.toml','rb'))['project']['version']; print(v)").dmg"
  rm -f "$DMG_PATH"
  hdiutil create -volname "SafeEyes" -srcfolder "$APP_BUNDLE" \
    -ov -format UDZO "$DMG_PATH"
  echo "DMG created: $DMG_PATH"
fi

# ── Login Items (autostart) ───────────────────────────────────────────────────
if ! $OPT_NO_AUTOSTART; then
  section "Configuring macOS Login Items (autostart on boot)"
  if command -v osascript &>/dev/null; then
    osascript -e "
      on run argv
        set appPath to (item 1 of argv)
        tell application \"System Events\"
          if not (exists login item \"SafeEyes\") then
            make login item at end with properties {path:appPath, hidden:false, name:\"SafeEyes\"}
            log \"SafeEyes added to Login Items.\"
          else
            set the path of login item \"SafeEyes\" to appPath
            log \"SafeEyes Login Item updated.\"
          end if
        end tell
      end run" "$APP_BUNDLE" \
      && echo "Login Items registration done." \
      || echo "Note: Could not register Login Item automatically. Add dist/SafeEyes.app manually in System Settings → General → Login Items."
  else
    echo "Note: osascript not found (not running on macOS?). Skip Login Items registration."
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
section "Build complete"
echo ""
echo "  Bundle : $APP_BUNDLE"
echo "  Log    : ~/Library/Logs/SafeEyes/safeeyes.log (when launched from Finder)"
echo ""
echo "  To launch immediately:"
echo "    open \"$APP_BUNDLE\""
echo ""
echo "  First launch: macOS Gatekeeper will ask you to confirm."
echo "  Right-click → Open if the system blocks the app on first run."
