import Foundation
import UserNotifications
import os

public final class NotificationService: NSObject, NotificationScheduling, UNUserNotificationCenterDelegate {
    public static let shared = NotificationService()

    public static let notificationIdentifier = "safeeyes.prebreak"
    public static let categoryIdentifier = "PREBREAK"
    public static let actionSkipIdentifier = "ACTION_SKIP"
    public static let actionPostponeIdentifier = "ACTION_POSTPONE"

    public var onAction: ((SchedulerEvent) -> Void)?

    private var isAuthorized = false

    public override init() {
        super.init()
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        setupCategories(in: center)
    }

    public func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound])
            self.isAuthorized = granted
            Log.notifications.info("Notification authorization status: \(granted, privacy: .public)")
            return granted
        } catch {
            Log.notifications.error("Notification authorization request failed: \(error.localizedDescription, privacy: .public)")
            self.isAuthorized = false
            return false
        }
    }

    public func scheduleBreakNotice(kind: BreakKind, leadSeconds: TimeInterval) {
        let center = UNUserNotificationCenter.current()

        let content = UNMutableNotificationContent()
        content.title = NSLocalizedString("SafeEyes Break Notice", comment: "")
        let secondsInt = max(1, Int(leadSeconds))
        let kindStr = (kind == .short)
            ? NSLocalizedString("Short", comment: "")
            : NSLocalizedString("Long", comment: "")
        let bodyFormat = NSLocalizedString("%@ break will start in %ld seconds. Prepare to rest your eyes.", comment: "")
        content.body = String(format: bodyFormat, kindStr, secondsInt)
        content.sound = .default
        content.categoryIdentifier = Self.categoryIdentifier

        let trigger: UNNotificationTrigger?
        if leadSeconds > 1.0 {
            trigger = UNTimeIntervalNotificationTrigger(timeInterval: leadSeconds, repeats: false)
        } else {
            trigger = nil
        }

        let request = UNNotificationRequest(
            identifier: Self.notificationIdentifier,
            content: content,
            trigger: trigger
        )

        center.add(request) { error in
            if let error = error {
                Log.notifications.error("Failed to add notification request: \(error.localizedDescription, privacy: .public)")
            } else {
                Log.notifications.debug("Scheduled pre-break notification with lead seconds: \(leadSeconds, privacy: .public)")
            }
        }
    }

    public func cancel() {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: [Self.notificationIdentifier])
        center.removeDeliveredNotifications(withIdentifiers: [Self.notificationIdentifier])
        Log.notifications.debug("Cancelled pre-break notification")
    }

    // MARK: - Category & Action Setup

    private func setupCategories(in center: UNUserNotificationCenter) {
        let skipAction = UNNotificationAction(
            identifier: Self.actionSkipIdentifier,
            title: NSLocalizedString("Skip", comment: ""),
            options: []
        )
        let postponeAction = UNNotificationAction(
            identifier: Self.actionPostponeIdentifier,
            title: NSLocalizedString("Postpone", comment: ""),
            options: []
        )

        let category = UNNotificationCategory(
            identifier: Self.categoryIdentifier,
            actions: [skipAction, postponeAction],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )

        center.setNotificationCategories([category])
    }

    // MARK: - UNUserNotificationCenterDelegate

    public func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        // Foreground presentation ensures banner and sound show even when app is active
        return [.banner, .sound]
    }

    public func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let actionId = response.actionIdentifier
        Log.notifications.info("User interacted with notification action: \(actionId, privacy: .public)")

        await MainActor.run {
            switch actionId {
            case Self.actionSkipIdentifier:
                onAction?(.skipBreak(force: false))
            case Self.actionPostponeIdentifier:
                onAction?(.postpone)
            default:
                break
            }
        }
    }
}
