import XCTest
@testable import SafeEyes

final class BreakSchedulerTests: XCTestCase {
    private var baseDate: Date!
    private var settings: AppSettings!

    override func setUp() {
        super.setUp()
        baseDate = Date(timeIntervalSince1970: 1_700_000_000)
        settings = AppSettings(
            shortBreakIntervalMinutes: 15,
            shortBreakDurationSeconds: 15,
            longBreakEveryNShortBreaks: 4,
            longBreakDurationSeconds: 300,
            preBreakNoticeSeconds: 10,
            strictMode: false,
            allowPostpone: true,
            postponeMinutes: 5,
            idlePauseThresholdSeconds: 10
        )
    }

    func testFullShortBreakCycle() {
        // Start working: 900s remaining, 0 short breaks
        var state = TimerState.working(remaining: 900, shortBreaksSinceLong: 0)

        // 1. Tick down to 10 seconds -> triggers preBreak
        let (preState, preEffects) = BreakScheduler.reduce(
            state: state,
            event: .tick(elapsed: 890, idleSeconds: 0),
            settings: settings,
            now: baseDate
        )

        XCTAssertEqual(preState, .preBreak(kind: .short, remaining: 10, shortBreaksSinceLong: 0))
        XCTAssertEqual(preEffects, [.scheduleNotification(kind: .short, leadSeconds: 10)])
        state = preState

        // 2. Tick 10 seconds -> triggers onBreak(short)
        let (breakState, breakEffects) = BreakScheduler.reduce(
            state: state,
            event: .tick(elapsed: 10, idleSeconds: 0),
            settings: settings,
            now: baseDate.addingTimeInterval(10)
        )

        XCTAssertEqual(breakState, .onBreak(kind: .short, remaining: 15, total: 15, shortBreaksSinceLong: 0))
        XCTAssertEqual(breakEffects, [.cancelNotification, .showOverlay(kind: .short, strict: false)])
        state = breakState

        // 3. Tick through break duration (15s) -> back to working with counter = 1
        let (workState, workEffects) = BreakScheduler.reduce(
            state: state,
            event: .tick(elapsed: 15, idleSeconds: 0),
            settings: settings,
            now: baseDate.addingTimeInterval(25)
        )

        XCTAssertEqual(workState, .working(remaining: 900, shortBreaksSinceLong: 1))
        XCTAssertEqual(workEffects, [.hideOverlay, .playEndChime])
    }

    func testEveryFourthBreakIsLong() {
        // Start with 3 short breaks already taken
        let state = TimerState.working(remaining: 15, shortBreaksSinceLong: 3)

        // Tick into preBreak -> next kind should be .long
        let (preState, _) = BreakScheduler.reduce(
            state: state,
            event: .tick(elapsed: 5, idleSeconds: 0),
            settings: settings,
            now: baseDate
        )
        XCTAssertEqual(preState, .preBreak(kind: .long, remaining: 10, shortBreaksSinceLong: 3))

        // Tick into onBreak -> should be long break (300s)
        let (breakState, breakEffects) = BreakScheduler.reduce(
            state: preState,
            event: .tick(elapsed: 10, idleSeconds: 0),
            settings: settings,
            now: baseDate.addingTimeInterval(10)
        )
        XCTAssertEqual(breakState, .onBreak(kind: .long, remaining: 300, total: 300, shortBreaksSinceLong: 3))
        XCTAssertEqual(breakEffects, [.cancelNotification, .showOverlay(kind: .long, strict: false)])

        // Finish long break -> counter resets to 0
        let (nextWorkState, _) = BreakScheduler.reduce(
            state: breakState,
            event: .tick(elapsed: 300, idleSeconds: 0),
            settings: settings,
            now: baseDate.addingTimeInterval(310)
        )
        XCTAssertEqual(nextWorkState, .working(remaining: 900, shortBreaksSinceLong: 0))
    }

    func testIdlePauseFreezesCountdown() {
        let state = TimerState.working(remaining: 500, shortBreaksSinceLong: 1)

        // User idle for 12 seconds (threshold is 10s)
        let (pausedState, effects) = BreakScheduler.reduce(
            state: state,
            event: .tick(elapsed: 1, idleSeconds: 12),
            settings: settings,
            now: baseDate
        )

        // Threshold of 10s is added back to remaining: 500 + 10 = 510
        if case .paused(let reason, let snapshot) = pausedState {
            XCTAssertEqual(reason, .idle)
            XCTAssertEqual(snapshot.remaining, 510)
            XCTAssertEqual(snapshot.shortBreaksSinceLong, 1)
        } else {
            XCTFail("Expected paused(.idle), got \(pausedState)")
        }
        XCTAssertEqual(effects, [.stateChanged])
    }

    func testIdleCreditShortDurationCreditsBreak() {
        let state = TimerState.working(remaining: 400, shortBreaksSinceLong: 1)

        // Away for 20 seconds (short break duration is 15s, long is 300s)
        let (newState, effects) = BreakScheduler.reduce(
            state: state,
            event: .idleCredit(20),
            settings: settings,
            now: baseDate
        )

        XCTAssertEqual(newState, .working(remaining: 900, shortBreaksSinceLong: 2))
        XCTAssertEqual(effects, [.hideOverlay, .cancelNotification, .stateChanged])
    }

    func testIdleCreditLongDurationResetsCycle() {
        let state = TimerState.working(remaining: 400, shortBreaksSinceLong: 3)

        // Away for 350 seconds (long break duration is 300s)
        let (newState, effects) = BreakScheduler.reduce(
            state: state,
            event: .idleCredit(350),
            settings: settings,
            now: baseDate
        )

        XCTAssertEqual(newState, .working(remaining: 900, shortBreaksSinceLong: 0))
        XCTAssertEqual(effects, [.hideOverlay, .cancelNotification, .stateChanged])
    }

    func testIdleIgnoredDuringBreak() {
        let state = TimerState.onBreak(kind: .short, remaining: 15, total: 15, shortBreaksSinceLong: 0)

        // User has high idle while looking away
        let (nextState, effects) = BreakScheduler.reduce(
            state: state,
            event: .tick(elapsed: 5, idleSeconds: 60),
            settings: settings,
            now: baseDate
        )

        XCTAssertEqual(nextState, .onBreak(kind: .short, remaining: 10, total: 15, shortBreaksSinceLong: 0))
        XCTAssertEqual(effects, [])
    }

    func testSkipInStrictModeIsRejected() {
        var strictSettings = settings!
        strictSettings.strictMode = true

        let state = TimerState.onBreak(kind: .short, remaining: 10, total: 15, shortBreaksSinceLong: 0)

        // Regular skip is rejected
        let (rejectedState, rejectedEffects) = BreakScheduler.reduce(
            state: state,
            event: .skipBreak(force: false),
            settings: strictSettings,
            now: baseDate
        )
        XCTAssertEqual(rejectedState, state)
        XCTAssertEqual(rejectedEffects, [])

        // Emergency exit (forced skip) succeeds
        let (forcedState, forcedEffects) = BreakScheduler.reduce(
            state: state,
            event: .skipBreak(force: true),
            settings: strictSettings,
            now: baseDate
        )
        XCTAssertEqual(forcedState, .working(remaining: 900, shortBreaksSinceLong: 1))
        XCTAssertEqual(forcedEffects, [.hideOverlay])
    }

    func testPostponeResetsTimer() {
        let state = TimerState.onBreak(kind: .short, remaining: 10, total: 15, shortBreaksSinceLong: 2)

        let (newState, effects) = BreakScheduler.reduce(
            state: state,
            event: .postpone,
            settings: settings,
            now: baseDate
        )

        // Postpone set to 5 minutes = 300 seconds
        XCTAssertEqual(newState, .working(remaining: 300, shortBreaksSinceLong: 2))
        XCTAssertEqual(effects, [.hideOverlay])
    }

    func testSettingsChangeClampsRemaining() {
        let state = TimerState.working(remaining: 800, shortBreaksSinceLong: 0)

        var newSettings = settings!
        newSettings.shortBreakIntervalMinutes = 10 // 600 seconds max

        let (clampedState, effects) = BreakScheduler.reduce(
            state: state,
            event: .settingsChanged,
            settings: newSettings,
            now: baseDate
        )

        XCTAssertEqual(clampedState, .working(remaining: 600, shortBreaksSinceLong: 0))
        XCTAssertEqual(effects, [.stateChanged])
    }

    func testUserPauseWithExpiryResumes() {
        let state = TimerState.working(remaining: 500, shortBreaksSinceLong: 1)

        // Pause for 60 seconds
        let (pausedState, _) = BreakScheduler.reduce(
            state: state,
            event: .userPause(duration: 60),
            settings: settings,
            now: baseDate
        )

        // At +30 seconds, tick should stay paused
        let (stillPaused, _) = BreakScheduler.reduce(
            state: pausedState,
            event: .tick(elapsed: 1, idleSeconds: 0),
            settings: settings,
            now: baseDate.addingTimeInterval(30)
        )
        XCTAssertEqual(stillPaused, pausedState)

        // At +61 seconds, tick should resume to working
        let (resumedState, effects) = BreakScheduler.reduce(
            state: pausedState,
            event: .tick(elapsed: 1, idleSeconds: 0),
            settings: settings,
            now: baseDate.addingTimeInterval(61)
        )
        XCTAssertEqual(resumedState, .working(remaining: 500, shortBreaksSinceLong: 1))
        XCTAssertEqual(effects, [.stateChanged])
    }
}
