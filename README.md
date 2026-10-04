# SafeEyes for macOS (Native)

SafeEyes is a 100% native macOS menu-bar utility designed to prevent digital eye strain and Repetitive Strain Injury (RSI). Built using pure Swift, SwiftUI, AppKit, and Combine — with zero third-party dependencies, no Python runtime, and no GTK.

---

## Features

- **Menu Bar Resident (`LSUIElement`):** Runs cleanly in the menu bar with dynamic status countdowns and live icon updates.
- **Scientifically Proven Intervals:** Configurable short breaks (e.g. 20-20-20 rule) and periodic long restorative breaks.
- **Pure Functional Reducer Architecture:** Driven by `BreakScheduler.reduce` — 100% unit-tested and deterministic.
- **Hardware-Accelerated Fullscreen Overlays:** Custom `BreakWindow` shields every connected display, floating above the Dock, menu bar, and native fullscreen Spaces.
- **Smart Idle Detection:** Tracks system inactivity via `CGEventSource` without needing Accessibility or Input Monitoring permissions. Naturally credits time away toward your breaks.
- **Strict Mode with Emergency Safety Valve:** Prevents break avoidance and locks app-switching shortcuts. In an emergency, holding `⌥⌘⇧E` (Option + Command + Shift + E) for 5 seconds force-skips the break.
- **Multi-Monitor Awareness:** Automatically reconstructs overlay viewports when displays are hot-plugged or resolution changes.
- **Accessibility & Reduce Motion:** Fully tagged with VoiceOver elements, values, and hints; honors system-wide Reduce Motion preferences.
- **Localization & Right-to-Left (RTL):** Comprehensive English and Arabic support via String Catalogs (`Localizable.xcstrings`), with full bidirectional and RTL dynamic layout adaptation.
- **Launch at Login:** Seamlessly integrates with Apple's modern `SMAppService` with approval status warnings.
- **System Event Awareness:** Automatically pauses and credits breaks on system sleep, display sleep, and screen lock/unlock.

---

## System Requirements

- **Operating System:** macOS 13.0 (Ventura) or newer
- **Architecture:** Apple Silicon (arm64) and Intel (x86_64)
- **Build Tools:** [XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`) and Xcode 15+

---

## Building and Running

### 1. Generate Xcode Project
We use **XcodeGen** so that project files are generated deterministically:
```bash
xcodegen generate
```

### 2. Build via Command Line
```bash
xcodebuild -scheme SafeEyes build
```

### 3. Run Unit Tests
```bash
xcodebuild test -scheme SafeEyes
```

### 4. Open in Xcode
```bash
open SafeEyes.xcodeproj
```

---

## Strict Mode & Emergency Exit

When **Strict Mode** is enabled:
- Break overlays lock down the screen and hide the Dock and Menu Bar.
- System hotkeys (⌘Tab, ⌘Q, ⌘H, Esc) and mouse clicks outside buttons are swallowed.
- Postponing and regular skipping are disabled.

### Emergency Exit Shortcut
If you must urgently return to your desktop during a strict break:
> **Hold `⌥⌘⇧E` (Option + Command + Shift + E) continuously for 5 seconds.**
> SafeEyes will detect the sustained hold, safely dismiss the overlay, and log the emergency override.

---

## Permissions & Privacy

SafeEyes respects your privacy:
- **No Accessibility Permissions Required:** Idle tracking uses `CGEventSource.secondsSinceLastEventType` which requires zero special permissions.
- **No Input Monitoring Required:** Keystrokes are never recorded or logged.
- **Notifications (Optional):** Prompts on first launch to deliver pre-break notifications.

---

## Packaging a Release

To build a notarized DMG for distribution:
```bash
export DEVELOPER_ID_APPLICATION="Developer ID Application: Your Name (TEAMID)"
export NOTARY_APPLE_ID="your-apple-id@example.com"
export NOTARY_PASSWORD="app-specific-password"
export NOTARY_TEAM_ID="TEAMID"

./scripts/release.sh
```

---

## Legacy Python Implementation

The original cross-platform Python implementation has been preserved in [README_PYTHON_LEGACY.md](README_PYTHON_LEGACY.md).

---

## License

SafeEyes is open-source software licensed under the [GNU General Public License v3.0](LICENSE).
