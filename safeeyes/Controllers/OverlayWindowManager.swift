import AppKit
import SwiftUI
import os

@MainActor
public final class OverlayWindowManager: NSObject, OverlayPresenting {
    private var timerManager: TimerManager?
    private let settingsManager: SettingsStoring

    private var windows: [BreakWindow] = []
    private var isBreakActive = false
    private var currentKind: BreakKind = .short
    private var isStrict = false
    private var previousFrontmostApp: NSRunningApplication?

    // Strict mode monitors & observers
    private var keyEventMonitor: Any?
    private var resignActiveObserver: NSObjectProtocol?
    private var screenChangeObserver: NSObjectProtocol?
    private var emergencyExitTimer: Timer?

    public init(settingsManager: SettingsStoring) {
        self.settingsManager = settingsManager
        super.init()
    }

    public func configure(timerManager: TimerManager) {
        self.timerManager = timerManager
    }


    public func show(kind: BreakKind, strict: Bool) {
        guard !isBreakActive else { return } // Idempotent

        isBreakActive = true
        currentKind = kind
        isStrict = strict
        previousFrontmostApp = NSWorkspace.shared.frontmostApplication

        buildWindows()

        if strict {
            enableStrictMode()
        }

        startScreenChangeObservation()
    }

    public func hide() {
        guard isBreakActive else { return }

        isBreakActive = false
        stopScreenChangeObservation()

        if isStrict {
            disableStrictMode()
        }

        let reduceMotion = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        let fadeDuration: TimeInterval = reduceMotion ? 0.0 : 0.3

        if fadeDuration > 0 {
            NSAnimationContext.runAnimationGroup({ context in
                context.duration = fadeDuration
                for window in windows {
                    window.animator().alphaValue = 0.0
                }
            }, completionHandler: { [weak self] in
                Task { @MainActor [weak self] in
                    self?.teardownWindows()
                }
            })
        } else {
            teardownWindows()
        }
    }

    // MARK: - Window Management

    private func buildWindows() {
        guard let timerManager = timerManager else {
            Log.overlay.error("Cannot build windows: timerManager is nil")
            return
        }

        // Find screen under mouse or fallback to main screen
        let mouseLoc = NSEvent.mouseLocation
        let primaryScreen = NSScreen.screens.first { NSMouseInRect(mouseLoc, $0.frame, false) }
            ?? NSScreen.main
            ?? NSScreen.screens.first

        let reduceMotion = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        let fadeDuration: TimeInterval = reduceMotion ? 0.0 : 0.3

        var newWindows: [BreakWindow] = []

        for screen in NSScreen.screens {
            let window = BreakWindow(screen: screen)
            let isPrimary = (screen == primaryScreen)

            let viewModel = BreakViewModel(
                timerManager: timerManager,
                settingsManager: settingsManager,
                kind: currentKind,
                strict: isStrict
            )

            let hostingView: NSView
            if isPrimary {
                hostingView = NSHostingView(rootView: BreakView(viewModel: viewModel))
            } else {
                hostingView = NSHostingView(rootView: SecondaryScreenView(viewModel: viewModel))
            }

            window.contentView = hostingView
            window.alphaValue = fadeDuration > 0 ? 0.0 : 1.0

            if isPrimary {
                window.makeKeyAndOrderFront(nil)
            } else {
                window.orderFrontRegardless()
            }

            newWindows.append(window)
        }

        self.windows = newWindows

        // Activate app
        activateApp()

        if fadeDuration > 0 {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = fadeDuration
                for window in self.windows {
                    window.animator().alphaValue = 1.0
                }
            }
        }
    }

    private func teardownWindows() {
        for window in windows {
            window.teardown()
        }
        windows.removeAll()

        // Restore focus to previous frontmost application
        if let previous = previousFrontmostApp {
            if #available(macOS 14.0, *) {
                previous.activate()
            } else {
                previous.activate(options: .activateIgnoringOtherApps)
            }
            previousFrontmostApp = nil
        }
    }

    private func rebuildWindowsForScreenChange() {
        guard isBreakActive else { return }
        Log.overlay.info("Rebuilding overlay windows for screen parameter change")

        // Destroy previous windows immediately and recreate for new screen set
        for window in windows {
            window.teardown()
        }
        windows.removeAll()

        buildWindows()
    }

    private func activateApp() {
        if #available(macOS 14.0, *) {
            NSApp.activate()
        } else {
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    // MARK: - Strict Mode

    private func enableStrictMode() {
        NSApp.presentationOptions = [
            .hideDock,
            .hideMenuBar,
            .disableProcessSwitching,
            .disableHideApplication,
            .disableAppleMenu
        ]

        // Local monitor swallowing keyboard events, except emergency exit shortcut
        keyEventMonitor = NSEvent.addLocalMonitorForEvents(
            matching: [.keyDown, .keyUp, .flagsChanged]
        ) { [weak self] event in
            guard let self = self else { return event }
            return self.handleStrictKeyEvent(event)
        }

        // Re-activation guard if focus is lost
        resignActiveObserver = NotificationCenter.default.addObserver(
            forName: NSApplication.didResignActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self = self, self.isBreakActive, self.isStrict else { return }
                self.activateApp()
                for window in self.windows {
                    window.orderFrontRegardless()
                }
            }
        }
    }

    private func disableStrictMode() {
        NSApp.presentationOptions = []

        if let monitor = keyEventMonitor {
            NSEvent.removeMonitor(monitor)
            keyEventMonitor = nil
        }

        if let observer = resignActiveObserver {
            NotificationCenter.default.removeObserver(observer)
            resignActiveObserver = nil
        }

        emergencyExitTimer?.invalidate()
        emergencyExitTimer = nil
    }

    private func handleStrictKeyEvent(_ event: NSEvent) -> NSEvent? {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        let isEmergencyModifiers = flags.contains([.option, .command, .shift])
        let isKeyE = (event.keyCode == 14) // 14 is QWERTY 'E' key code on macOS

        if isEmergencyModifiers && isKeyE {
            if event.type == .keyDown && emergencyExitTimer == nil {
                Log.overlay.warning("Emergency exit shortcut pressed, starting 5s hold timer")
                emergencyExitTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: false) { [weak self] _ in
                    Task { @MainActor [weak self] in
                        Log.overlay.warning("Emergency exit held for 5s: force-skipping break")
                        self?.timerManager?.send(.skipBreak(force: true))
                    }
                }
            }
            return nil
        }

        // Any other key release or change cancels the emergency timer
        if emergencyExitTimer != nil {
            emergencyExitTimer?.invalidate()
            emergencyExitTimer = nil
            Log.overlay.debug("Emergency exit shortcut released before 5s")
        }

        // Swallow all input events in strict mode
        return nil
    }

    // MARK: - Screen Change Observation

    private func startScreenChangeObservation() {
        screenChangeObserver = NotificationCenter.default.addObserver(
            forName: NSApplication.didChangeScreenParametersNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.rebuildWindowsForScreenChange()
            }
        }
    }

    private func stopScreenChangeObservation() {
        if let observer = screenChangeObserver {
            NotificationCenter.default.removeObserver(observer)
            screenChangeObserver = nil
        }
    }
}
