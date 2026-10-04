import Foundation

public struct AppSettings: Codable, Equatable {
    public var schemaVersion: Int
    public var shortBreakIntervalMinutes: Int
    public var shortBreakDurationSeconds: Int
    public var longBreakEveryNShortBreaks: Int
    public var longBreakDurationSeconds: Int
    public var preBreakNoticeSeconds: Int
    public var strictMode: Bool
    public var allowPostpone: Bool
    public var postponeMinutes: Int
    public var idlePauseThresholdSeconds: Int
    public var pauseDuringFullscreenVideo: Bool
    public var launchAtLogin: Bool
    public var playSounds: Bool
    public var showExercises: Bool

    public static let `default` = AppSettings(
        schemaVersion: 1,
        shortBreakIntervalMinutes: 15,
        shortBreakDurationSeconds: 15,
        longBreakEveryNShortBreaks: 4,
        longBreakDurationSeconds: 300,
        preBreakNoticeSeconds: 10,
        strictMode: false,
        allowPostpone: true,
        postponeMinutes: 5,
        idlePauseThresholdSeconds: 10,
        pauseDuringFullscreenVideo: false,
        launchAtLogin: false,
        playSounds: true,
        showExercises: true
    )

    public init(
        schemaVersion: Int = 1,
        shortBreakIntervalMinutes: Int = 15,
        shortBreakDurationSeconds: Int = 15,
        longBreakEveryNShortBreaks: Int = 4,
        longBreakDurationSeconds: Int = 300,
        preBreakNoticeSeconds: Int = 10,
        strictMode: Bool = false,
        allowPostpone: Bool = true,
        postponeMinutes: Int = 5,
        idlePauseThresholdSeconds: Int = 10,
        pauseDuringFullscreenVideo: Bool = false,
        launchAtLogin: Bool = false,
        playSounds: Bool = true,
        showExercises: Bool = true
    ) {
        self.schemaVersion = schemaVersion
        self.shortBreakIntervalMinutes = shortBreakIntervalMinutes
        self.shortBreakDurationSeconds = shortBreakDurationSeconds
        self.longBreakEveryNShortBreaks = longBreakEveryNShortBreaks
        self.longBreakDurationSeconds = longBreakDurationSeconds
        self.preBreakNoticeSeconds = preBreakNoticeSeconds
        self.strictMode = strictMode
        self.allowPostpone = allowPostpone
        self.postponeMinutes = postponeMinutes
        self.idlePauseThresholdSeconds = idlePauseThresholdSeconds
        self.pauseDuringFullscreenVideo = pauseDuringFullscreenVideo
        self.launchAtLogin = launchAtLogin
        self.playSounds = playSounds
        self.showExercises = showExercises
    }

    public func validated() -> AppSettings {
        var copy = self
        copy.shortBreakIntervalMinutes = max(1, min(120, copy.shortBreakIntervalMinutes))
        copy.shortBreakDurationSeconds = max(5, min(300, copy.shortBreakDurationSeconds))
        copy.longBreakEveryNShortBreaks = max(1, min(20, copy.longBreakEveryNShortBreaks))
        copy.longBreakDurationSeconds = max(30, min(1800, copy.longBreakDurationSeconds))
        copy.preBreakNoticeSeconds = max(0, min(60, copy.preBreakNoticeSeconds))
        copy.postponeMinutes = max(1, min(30, copy.postponeMinutes))
        copy.idlePauseThresholdSeconds = max(5, min(600, copy.idlePauseThresholdSeconds))

        // In strict mode, postpone is never allowed
        if copy.strictMode {
            copy.allowPostpone = false
        }

        return copy
    }
}
