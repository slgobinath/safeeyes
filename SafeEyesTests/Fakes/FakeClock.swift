import Foundation
@testable import SafeEyes

public final class FakeClock: TimeSource {
    public var now: Date

    public init(initialDate: Date = Date(timeIntervalSince1970: 1_700_000_000)) {
        self.now = initialDate
    }

    public func advance(by seconds: TimeInterval) {
        now = now.addingTimeInterval(seconds)
    }
}
