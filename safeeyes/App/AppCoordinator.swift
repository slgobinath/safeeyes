import Foundation
import AppKit

@MainActor
final class AppCoordinator {
    static let shared = AppCoordinator()

    let settingsManager: SettingsManager
    let idleMonitor: IdleMonitor
    let timeSource: SystemTimeSource
    let notificationService: NotificationService
    let overlayWindowManager: OverlayWindowManager
    let timerManager: TimerManager
    var systemEventObserver: SystemEventObserver?
    var menuBarController: MenuBarController?
    var settingsWindowController: SettingsWindowController?

    init() {
        let settings = SettingsManager()
        let idle = IdleMonitor()
        let time = SystemTimeSource()
        let notifications = NotificationService.shared
        let overlay = OverlayWindowManager(settingsManager: settings)

        self.settingsManager = settings
        self.idleMonitor = idle
        self.timeSource = time
        self.notificationService = notifications
        self.overlayWindowManager = overlay

        self.timerManager = TimerManager(
            settings: settings,
            idle: idle,
            time: time,
            notifier: notifications,
            overlay: overlay
        )

        // Configure timerManager on overlay window manager
        overlay.configure(timerManager: timerManager)

        // Play chime sound when break completes if sounds are enabled
        timerManager.onPlaySound = {
            if let sound = NSSound(named: "Glass") {
                sound.play()
            } else {
                NSSound.beep()
            }
        }

        // Wire SystemEventObserver to TimerManager
        self.systemEventObserver = SystemEventObserver(timerManager: timerManager)

        // Route notification banner actions to TimerManager
        notifications.onAction = { [weak self] event in
            self?.timerManager.send(event)
        }
    }

    func start() {
        Log.app.info("SafeEyes AppCoordinator started")

        // Reconcile launch-at-login system status with stored settings
        let loginService = LoginItemService.shared
        if settingsManager.settings.launchAtLogin != loginService.isEnabled {
            settingsManager.update { $0.launchAtLogin = loginService.isEnabled }
        }

        // Request notification authorization asynchronously
        Task {
            _ = await notificationService.requestAuthorization()
        }

        // Create settings window controller
        let settingsWC = SettingsWindowController(settingsManager: settingsManager)
        self.settingsWindowController = settingsWC

        // Install menu bar controller
        let menuBar = MenuBarController(timer: timerManager) { [weak self] in
            self?.openSettings()
        }
        menuBar.install()
        self.menuBarController = menuBar

        // Start timer loop
        timerManager.start()
    }

    func openSettings() {
        Log.app.info("Opening settings window")
        settingsWindowController?.showWindow()
    }
}
