import Foundation

public enum SchedulerEvent: Equatable {
    case tick(elapsed: TimeInterval, idleSeconds: TimeInterval)
    case userPause(duration: TimeInterval?)
    case resume
    case takeBreakNow(BreakKind)
    case skipBreak(force: Bool = false)
    case postpone
    case settingsChanged
    case systemWillSleep
    case systemDidWake(sleptFor: TimeInterval)
    case screenLocked
    case screenUnlocked
    case idleCredit(TimeInterval)
}
