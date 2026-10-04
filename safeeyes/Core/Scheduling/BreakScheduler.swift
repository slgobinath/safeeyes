import Foundation

public enum BreakScheduler {
    public static func reduce(
        state: TimerState,
        event: SchedulerEvent,
        settings: AppSettings,
        now: Date
    ) -> (TimerState, [SchedulerEffect]) {
        switch event {
        case .tick(let elapsed, let idleSeconds):
            return handleTick(state: state, elapsed: elapsed, idleSeconds: idleSeconds, settings: settings, now: now)

        case .idleCredit(let credit):
            return handleIdleCredit(state: state, credit: credit, settings: settings)

        case .userPause(let duration):
            let until = duration.map { now.addingTimeInterval($0) }
            let snapshot = makeSnapshot(from: state, settings: settings, pausedAt: now)
            return (.paused(reason: .user(until: until), frozen: snapshot), [.cancelNotification, .hideOverlay, .stateChanged])

        case .resume:
            if case .paused(_, let snapshot) = state {
                return resumeSnapshot(snapshot)
            }
            return (state, [])

        case .takeBreakNow(let kind):
            let count = currentCount(from: state)
            let total = breakDuration(for: kind, settings: settings)
            return (.onBreak(kind: kind, remaining: total, total: total, shortBreaksSinceLong: count),
                    [.cancelNotification, .showOverlay(kind: kind, strict: settings.strictMode)])

        case .skipBreak(let force):
            return handleSkipBreak(state: state, force: force, settings: settings)

        case .postpone:
            return handlePostpone(state: state, settings: settings)

        case .settingsChanged:
            return handleSettingsChanged(state: state, settings: settings)

        case .systemWillSleep, .screenLocked:
            let snapshot = makeSnapshot(from: state, settings: settings, pausedAt: now)
            return (.paused(reason: .system, frozen: snapshot), [.hideOverlay, .cancelNotification, .stateChanged])

        case .systemDidWake(let sleptFor):
            return handleIdleCredit(state: state, credit: sleptFor, settings: settings)

        case .screenUnlocked:
            if case .paused(let reason, let snapshot) = state, reason == .system {
                let credit = snapshot.pausedAt.map { now.timeIntervalSince($0) } ?? 0
                return applyIdleCredit(credit: credit, snapshot: snapshot, settings: settings)
            }
            return (state, [])
        }
    }

    // MARK: - Private Reducer Helpers

    private static func handleTick(
        state: TimerState,
        elapsed: TimeInterval,
        idleSeconds: TimeInterval,
        settings: AppSettings,
        now: Date
    ) -> (TimerState, [SchedulerEffect]) {
        let threshold = TimeInterval(settings.idlePauseThresholdSeconds)

        switch state {
        case .disabled:
            return (.disabled, [])

        case .working(let remaining, let count):
            if idleSeconds >= threshold {
                // Add back idle threshold so idle lead-in time isn't lost
                let adjusted = remaining + threshold
                let snapshot = PausedSnapshot(
                    remaining: adjusted,
                    shortBreaksSinceLong: count,
                    pausedAt: now
                )
                return (.paused(reason: .idle, frozen: snapshot), [.stateChanged])
            }

            let newRemaining = remaining - elapsed
            let notice = TimeInterval(settings.preBreakNoticeSeconds)

            if notice > 0 && newRemaining <= notice {
                let nextKind: BreakKind = (count + 1 >= settings.longBreakEveryNShortBreaks) ? .long : .short
                return (
                    .preBreak(kind: nextKind, remaining: newRemaining, shortBreaksSinceLong: count),
                    [.scheduleNotification(kind: nextKind, leadSeconds: max(0, newRemaining))]
                )
            } else if notice == 0 && newRemaining <= 0 {
                let nextKind: BreakKind = (count + 1 >= settings.longBreakEveryNShortBreaks) ? .long : .short
                let total = breakDuration(for: nextKind, settings: settings)
                return (
                    .onBreak(kind: nextKind, remaining: total, total: total, shortBreaksSinceLong: count),
                    [.showOverlay(kind: nextKind, strict: settings.strictMode)]
                )
            } else {
                return (.working(remaining: newRemaining, shortBreaksSinceLong: count), [])
            }

        case .preBreak(let kind, let remaining, let count):
            if idleSeconds >= threshold {
                let adjusted = remaining + threshold
                let snapshot = PausedSnapshot(
                    remaining: adjusted,
                    shortBreaksSinceLong: count,
                    preBreakKind: kind,
                    pausedAt: now
                )
                return (.paused(reason: .idle, frozen: snapshot), [.cancelNotification, .stateChanged])
            }

            let newRemaining = remaining - elapsed
            if newRemaining <= 0 {
                let total = breakDuration(for: kind, settings: settings)
                return (
                    .onBreak(kind: kind, remaining: total, total: total, shortBreaksSinceLong: count),
                    [.cancelNotification, .showOverlay(kind: kind, strict: settings.strictMode)]
                )
            } else {
                return (.preBreak(kind: kind, remaining: newRemaining, shortBreaksSinceLong: count), [])
            }

        case .onBreak(let kind, let remaining, let total, let count):
            // Idle is ignored while onBreak
            let newRemaining = remaining - elapsed
            if newRemaining <= 0 {
                let nextCount = (kind == .long) ? 0 : (count + 1)
                let interval = TimeInterval(settings.shortBreakIntervalMinutes * 60)
                return (
                    .working(remaining: interval, shortBreaksSinceLong: nextCount),
                    [.hideOverlay, .playEndChime]
                )
            } else {
                return (.onBreak(kind: kind, remaining: newRemaining, total: total, shortBreaksSinceLong: count), [])
            }

        case .paused(let reason, let snapshot):
            switch reason {
            case .idle:
                if idleSeconds < threshold {
                    let credit = snapshot.pausedAt.map { now.timeIntervalSince($0) } ?? 0
                    return applyIdleCredit(credit: credit, snapshot: snapshot, settings: settings)
                }
                return (.paused(reason: .idle, frozen: snapshot), [])

            case .user(let until):
                if let until = until, now >= until {
                    return resumeSnapshot(snapshot)
                }
                return (.paused(reason: reason, frozen: snapshot), [])

            case .system:
                return (.paused(reason: reason, frozen: snapshot), [])
            }
        }
    }

    private static func handleIdleCredit(
        state: TimerState,
        credit: TimeInterval,
        settings: AppSettings
    ) -> (TimerState, [SchedulerEffect]) {
        let count = currentCount(from: state)
        let longDuration = TimeInterval(settings.longBreakDurationSeconds)
        let shortDuration = TimeInterval(settings.shortBreakDurationSeconds)
        let shortInterval = TimeInterval(settings.shortBreakIntervalMinutes * 60)

        if credit >= longDuration {
            return (
                .working(remaining: shortInterval, shortBreaksSinceLong: 0),
                [.hideOverlay, .cancelNotification, .stateChanged]
            )
        } else if credit >= shortDuration {
            return (
                .working(remaining: shortInterval, shortBreaksSinceLong: count + 1),
                [.hideOverlay, .cancelNotification, .stateChanged]
            )
        } else {
            if case .paused(_, let snapshot) = state {
                return resumeSnapshot(snapshot)
            }
            return (state, [.stateChanged])
        }
    }

    private static func applyIdleCredit(
        credit: TimeInterval,
        snapshot: PausedSnapshot,
        settings: AppSettings
    ) -> (TimerState, [SchedulerEffect]) {
        let longDuration = TimeInterval(settings.longBreakDurationSeconds)
        let shortDuration = TimeInterval(settings.shortBreakDurationSeconds)
        let shortInterval = TimeInterval(settings.shortBreakIntervalMinutes * 60)

        if credit >= longDuration {
            return (.working(remaining: shortInterval, shortBreaksSinceLong: 0), [.stateChanged])
        } else if credit >= shortDuration {
            return (.working(remaining: shortInterval, shortBreaksSinceLong: snapshot.shortBreaksSinceLong + 1), [.stateChanged])
        } else {
            return resumeSnapshot(snapshot)
        }
    }

    private static func resumeSnapshot(_ snapshot: PausedSnapshot) -> (TimerState, [SchedulerEffect]) {
        if let kind = snapshot.preBreakKind {
            return (.preBreak(kind: kind, remaining: snapshot.remaining, shortBreaksSinceLong: snapshot.shortBreaksSinceLong), [.stateChanged])
        } else {
            return (.working(remaining: snapshot.remaining, shortBreaksSinceLong: snapshot.shortBreaksSinceLong), [.stateChanged])
        }
    }

    private static func handleSkipBreak(
        state: TimerState,
        force: Bool,
        settings: AppSettings
    ) -> (TimerState, [SchedulerEffect]) {
        let shortInterval = TimeInterval(settings.shortBreakIntervalMinutes * 60)

        switch state {
        case .onBreak(let kind, _, _, let count):
            if !settings.strictMode || force {
                let nextCount = (kind == .long) ? 0 : (count + 1)
                return (.working(remaining: shortInterval, shortBreaksSinceLong: nextCount), [.hideOverlay])
            }
            return (state, [])

        case .preBreak(let kind, _, let count):
            if !settings.strictMode || force {
                let nextCount = (kind == .long) ? 0 : (count + 1)
                return (.working(remaining: shortInterval, shortBreaksSinceLong: nextCount), [.cancelNotification, .stateChanged])
            }
            return (state, [])

        default:
            return (state, [])
        }
    }

    private static func handlePostpone(
        state: TimerState,
        settings: AppSettings
    ) -> (TimerState, [SchedulerEffect]) {
        guard settings.allowPostpone && !settings.strictMode else { return (state, []) }
        let postponeSeconds = TimeInterval(settings.postponeMinutes * 60)

        switch state {
        case .onBreak(_, _, _, let count):
            return (.working(remaining: postponeSeconds, shortBreaksSinceLong: count), [.hideOverlay])
        case .preBreak(_, _, let count):
            return (.working(remaining: postponeSeconds, shortBreaksSinceLong: count), [.cancelNotification, .stateChanged])
        default:
            return (state, [])
        }
    }

    private static func handleSettingsChanged(
        state: TimerState,
        settings: AppSettings
    ) -> (TimerState, [SchedulerEffect]) {
        let maxInterval = TimeInterval(settings.shortBreakIntervalMinutes * 60)
        switch state {
        case .working(let remaining, let count):
            let clamped = min(remaining, maxInterval)
            return (.working(remaining: clamped, shortBreaksSinceLong: count), [.stateChanged])
        case .paused(let reason, var snapshot):
            snapshot.remaining = min(snapshot.remaining, maxInterval)
            return (.paused(reason: reason, frozen: snapshot), [.stateChanged])
        default:
            return (state, [.stateChanged])
        }
    }

    private static func makeSnapshot(
        from state: TimerState,
        settings: AppSettings,
        pausedAt: Date
    ) -> PausedSnapshot {
        switch state {
        case .working(let remaining, let count):
            return PausedSnapshot(remaining: remaining, shortBreaksSinceLong: count, pausedAt: pausedAt)
        case .preBreak(let kind, let remaining, let count):
            return PausedSnapshot(remaining: remaining, shortBreaksSinceLong: count, preBreakKind: kind, pausedAt: pausedAt)
        case .onBreak(_, _, _, let count):
            // If on break when sleep/user-pause happens, break ends and resumes next work interval
            let shortInterval = TimeInterval(settings.shortBreakIntervalMinutes * 60)
            return PausedSnapshot(remaining: shortInterval, shortBreaksSinceLong: count, pausedAt: pausedAt)
        case .paused(_, let snapshot):
            return snapshot
        case .disabled:
            let shortInterval = TimeInterval(settings.shortBreakIntervalMinutes * 60)
            return PausedSnapshot(remaining: shortInterval, shortBreaksSinceLong: 0, pausedAt: pausedAt)
        }
    }

    private static func currentCount(from state: TimerState) -> Int {
        switch state {
        case .working(_, let count): return count
        case .preBreak(_, _, let count): return count
        case .onBreak(_, _, _, let count): return count
        case .paused(_, let snapshot): return snapshot.shortBreaksSinceLong
        case .disabled: return 0
        }
    }

    private static func breakDuration(for kind: BreakKind, settings: AppSettings) -> TimeInterval {
        switch kind {
        case .short:
            return TimeInterval(settings.shortBreakDurationSeconds)
        case .long:
            return TimeInterval(settings.longBreakDurationSeconds)
        }
    }
}
