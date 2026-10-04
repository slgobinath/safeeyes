import Foundation

public enum SchedulerEffect: Equatable {
    case scheduleNotification(kind: BreakKind, leadSeconds: TimeInterval)
    case cancelNotification
    case showOverlay(kind: BreakKind, strict: Bool)
    case hideOverlay
    case playEndChime
    case stateChanged
}
