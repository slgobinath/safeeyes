import Foundation
import Combine
import SwiftUI

@MainActor
public final class BreakViewModel: ObservableObject {
    @Published public private(set) var remainingSeconds: TimeInterval = 0
    @Published public private(set) var totalSeconds: TimeInterval = 1
    @Published public private(set) var progress: Double = 0.0
    @Published public private(set) var breakKind: BreakKind = .short
    @Published public private(set) var isStrict: Bool = false
    @Published public private(set) var allowPostpone: Bool = true
    @Published public private(set) var currentExercise: BreakContent?

    private let timerManager: TimerManager
    private let settingsManager: SettingsStoring
    private var cancellables = Set<AnyCancellable>()

    public init(
        timerManager: TimerManager,
        settingsManager: SettingsStoring,
        kind: BreakKind,
        strict: Bool
    ) {
        self.timerManager = timerManager
        self.settingsManager = settingsManager
        self.breakKind = kind
        self.isStrict = strict
        self.allowPostpone = settingsManager.settings.allowPostpone && !strict

        if settingsManager.settings.showExercises {
            self.currentExercise = ExerciseProvider.shared.nextExercise(for: kind)
        }

        updateFromState(timerManager.state)

        timerManager.$state
            .receive(on: RunLoop.main)
            .sink { [weak self] state in
                self?.updateFromState(state)
            }
            .store(in: &cancellables)
    }

    public var formattedRemaining: String {
        let total = max(0, Int(remainingSeconds))
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let seconds = total % 60

        if hours > 0 {
            return String(format: "%dh %dm %02ds", hours, minutes, seconds)
        } else if minutes > 0 {
            return String(format: "%dm %02ds", minutes, seconds)
        } else {
            return "\(seconds)s"
        }
    }

    public func skip() {
        guard !isStrict else { return }
        timerManager.send(.skipBreak(force: false))
    }

    public func postpone() {
        guard allowPostpone && !isStrict else { return }
        timerManager.send(.postpone)
    }

    public func emergencyExit() {
        timerManager.send(.skipBreak(force: true))
    }

    private func updateFromState(_ state: TimerState) {
        if case .onBreak(let kind, let remaining, let total, _) = state {
            self.breakKind = kind
            self.remainingSeconds = max(0, remaining)
            self.totalSeconds = max(1, total)
            self.progress = min(1.0, max(0.0, 1.0 - (remaining / max(1, total))))
        }
    }
}
