import Foundation
import Combine

@MainActor
public final class TimerManager: ObservableObject {
    @Published public private(set) var state: TimerState

    public var onPlaySound: (() -> Void)?

    private let settings: SettingsStoring
    private let idle: IdleProviding
    private let time: TimeSource
    private let notifier: NotificationScheduling
    private let overlay: OverlayPresenting

    private var timer: Timer?
    private var lastTickDate: Date?
    private var cancellables = Set<AnyCancellable>()

    public init(
        settings: SettingsStoring,
        idle: IdleProviding,
        time: TimeSource,
        notifier: NotificationScheduling,
        overlay: OverlayPresenting
    ) {
        self.settings = settings
        self.idle = idle
        self.time = time
        self.notifier = notifier
        self.overlay = overlay

        let initialInterval = TimeInterval(settings.settings.shortBreakIntervalMinutes * 60)
        self.state = .working(remaining: initialInterval, shortBreaksSinceLong: 0)

        // Observe settings changes
        settings.settingsPublisher
            .dropFirst()
            .sink { [weak self] newSettings in
                self?.send(.settingsChanged, overrideSettings: newSettings)
            }
            .store(in: &cancellables)
    }

    public var nextBreakCountdown: TimeInterval? {
        switch state {
        case .working(let remaining, _):
            return remaining
        case .preBreak(_, let remaining, _):
            return remaining
        case .onBreak(_, let remaining, _, _):
            return remaining
        case .paused(_, let snapshot):
            return snapshot.remaining
        case .disabled:
            return nil
        }
    }

    public func start() {
        stop()

        let initialInterval = TimeInterval(settings.settings.shortBreakIntervalMinutes * 60)
        state = .working(remaining: initialInterval, shortBreaksSinceLong: 0)
        lastTickDate = time.now

        let newTimer = Timer(timeInterval: 1.0, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                self?.performTick()
            }
        }
        RunLoop.main.add(newTimer, forMode: .common)
        self.timer = newTimer
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
        lastTickDate = nil
        state = .disabled
    }

    public func send(_ event: SchedulerEvent, overrideSettings: AppSettings? = nil) {
        let (newState, effects) = BreakScheduler.reduce(
            state: state,
            event: event,
            settings: overrideSettings ?? settings.settings,
            now: time.now
        )
        self.state = newState
        execute(effects: effects)
    }

    private func performTick() {
        guard let previous = lastTickDate else {
            lastTickDate = time.now
            return
        }

        let currentNow = time.now
        let elapsed = currentNow.timeIntervalSince(previous)
        lastTickDate = currentNow

        if elapsed > 5.0 {
            // Discontinuity detected (system sleep or thread stall)
            send(.idleCredit(elapsed))
        } else {
            let idleSeconds = idle.secondsSinceLastInput()
            send(.tick(elapsed: elapsed, idleSeconds: idleSeconds))
        }
    }

    private func execute(effects: [SchedulerEffect]) {
        for effect in effects {
            switch effect {
            case .scheduleNotification(let kind, let leadSeconds):
                notifier.scheduleBreakNotice(kind: kind, leadSeconds: leadSeconds)
            case .cancelNotification:
                notifier.cancel()
            case .showOverlay(let kind, let strict):
                overlay.show(kind: kind, strict: strict)
            case .hideOverlay:
                overlay.hide()
            case .playEndChime:
                if settings.settings.playSounds {
                    onPlaySound?()
                }
            case .stateChanged:
                break
            }
        }
    }
}
