import Foundation
import ServiceManagement
import os

/// Service responsible for registering and unregistering SafeEyes as a login item
/// using Apple's modern SMAppService (macOS 13+).
public final class LoginItemService: LoginItemControlling {
    public static let shared = LoginItemService()

    public init() {}

    /// Whether SafeEyes is currently registered and enabled to launch at login.
    public var isEnabled: Bool {
        return SMAppService.mainApp.status == .enabled
    }

    /// Whether the login item is awaiting user approval in macOS System Settings.
    public var requiresApproval: Bool {
        return SMAppService.mainApp.status == .requiresApproval
    }

    /// Registers or unregisters SafeEyes from launching at login.
    public func setEnabled(_ enabled: Bool) throws {
        if enabled {
            if SMAppService.mainApp.status != .enabled {
                try SMAppService.mainApp.register()
                Log.app.info("Registered SafeEyes mainApp with SMAppService")
            }
        } else {
            if SMAppService.mainApp.status == .enabled || SMAppService.mainApp.status == .requiresApproval {
                try SMAppService.mainApp.unregister()
                Log.app.info("Unregistered SafeEyes mainApp from SMAppService")
            }
        }
    }

    /// Opens System Settings -> General -> Login Items so the user can grant approval.
    public func openLoginItemsSettings() {
        Log.app.info("Opening System Settings Login Items")
        SMAppService.openSystemSettingsLoginItems()
    }
}
