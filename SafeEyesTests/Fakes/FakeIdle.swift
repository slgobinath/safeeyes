import Foundation
@testable import SafeEyes

public final class FakeIdle: IdleProviding {
    public var currentIdleSeconds: TimeInterval

    public init(initialIdleSeconds: TimeInterval = 0) {
        self.currentIdleSeconds = initialIdleSeconds
    }

    public func secondsSinceLastInput() -> TimeInterval {
        currentIdleSeconds
    }
}
