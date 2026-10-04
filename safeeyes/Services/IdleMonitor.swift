import Foundation
import CoreGraphics
import os

public struct IdleMonitor: IdleProviding {
    private static var didLogFailure = false

    public init() {}

    public func secondsSinceLastInput() -> TimeInterval {
        guard let anyEventType = CGEventType(rawValue: ~0) else {
            Self.logFailureOnce("Failed to create wildcard CGEventType for idle detection")
            return 0
        }

        let seconds = CGEventSource.secondsSinceLastEventType(.combinedSessionState, eventType: anyEventType)
        if seconds.isNaN || seconds < 0 {
            Self.logFailureOnce("CGEventSource returned invalid idle seconds: \(seconds)")
            return 0
        }

        return seconds
    }

    private static func logFailureOnce(_ message: String) {
        guard !didLogFailure else { return }
        didLogFailure = true
        Log.idle.error("\(message, privacy: .public)")
    }
}
