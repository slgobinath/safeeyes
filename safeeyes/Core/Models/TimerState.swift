import Foundation

public enum PauseReason: Equatable {
    case idle
    case user(until: Date?)
    case system
}

public struct PausedSnapshot: Equatable {
    public var remaining: TimeInterval
    public var shortBreaksSinceLong: Int
    public var preBreakKind: BreakKind?
    public var pausedAt: Date?

    public init(
        remaining: TimeInterval,
        shortBreaksSinceLong: Int,
        preBreakKind: BreakKind? = nil,
        pausedAt: Date? = nil
    ) {
        self.remaining = remaining
        self.shortBreaksSinceLong = shortBreaksSinceLong
        self.preBreakKind = preBreakKind
        self.pausedAt = pausedAt
    }
}

public enum TimerState: Equatable {
    case working(remaining: TimeInterval, shortBreaksSinceLong: Int)
    case preBreak(kind: BreakKind, remaining: TimeInterval, shortBreaksSinceLong: Int)
    case onBreak(kind: BreakKind, remaining: TimeInterval, total: TimeInterval, shortBreaksSinceLong: Int)
    case paused(reason: PauseReason, frozen: PausedSnapshot)
    case disabled
}
