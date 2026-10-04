import Foundation

public struct SystemTimeSource: TimeSource {
    public init() {}

    public var now: Date {
        Date()
    }
}
