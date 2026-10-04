import Foundation

public protocol NotificationScheduling: AnyObject {
    func requestAuthorization() async -> Bool
    func scheduleBreakNotice(kind: BreakKind, leadSeconds: TimeInterval)
    func cancel()
}
