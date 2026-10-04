import AppKit
import SwiftUI

@MainActor
public final class SettingsWindowController {
    private var window: NSWindow?
    private let settingsManager: SettingsManager

    public init(settingsManager: SettingsManager) {
        self.settingsManager = settingsManager
    }

    public func showWindow() {
        if let existing = window {
            existing.makeKeyAndOrderFront(nil)
            activateApp()
            return
        }

        let viewModel = SettingsViewModel(settingsManager: settingsManager)
        let rootView = SettingsRootView(viewModel: viewModel)
        let hostingController = NSHostingController(rootView: rootView)

        let newWindow = NSWindow(contentViewController: hostingController)
        newWindow.title = NSLocalizedString("SafeEyes Settings", comment: "")
        newWindow.styleMask = [.titled, .closable, .miniaturizable]
        newWindow.center()
        newWindow.setFrameAutosaveName("SafeEyesSettings")
        newWindow.isReleasedWhenClosed = false

        // When the user closes the window, hide it rather than destroying it
        newWindow.delegate = WindowCloseDelegate.shared

        self.window = newWindow
        newWindow.makeKeyAndOrderFront(nil)
        activateApp()
    }

    private func activateApp() {
        if #available(macOS 14.0, *) {
            NSApp.activate()
        } else {
            NSApp.activate(ignoringOtherApps: true)
        }
    }
}

// MARK: - Window Close Delegate (hides instead of destroying)

private final class WindowCloseDelegate: NSObject, NSWindowDelegate {
    static let shared = WindowCloseDelegate()

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        sender.orderOut(nil)
        return false
    }
}
