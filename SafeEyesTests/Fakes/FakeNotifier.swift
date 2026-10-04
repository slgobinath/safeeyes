import Foundation
@testable import SafeEyes

public final class FakeNotifier: NotificationScheduling {
    public var authorizationGranted = true
    public var scheduledNotices: [(kind: BreakKind, leadSeconds: TimeInterval)] = []
    public var cancelCallCount = 0

    public init() {}

    public func requestAuthorization() async -> Bool {
        authorizationGranted
    }

    public func scheduleBreakNotice(kind: BreakKind, leadSeconds: TimeInterval) {
        scheduledNotices.append((kind: kind, leadSeconds: leadSeconds))
    }

    public func cancel() {
        cancelCallCount += 1
    }

    public func reset() {
        scheduledNotices.removeAll()
        cancelCallCount = 0
    }
}
