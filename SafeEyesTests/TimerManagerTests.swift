import XCTest
@testable import SafeEyes

@MainActor
final class TimerManagerTests: XCTestCase {
    private var fakeSettings: InMemorySettingsStore!
    private var fakeIdle: FakeIdle!
    private var fakeClock: FakeClock!
    private var fakeNotifier: FakeNotifier!
    private var fakeOverlay: FakeOverlay!
    private var timerManager: TimerManager!

    override func setUp() {
        super.setUp()
        fakeSettings = InMemorySettingsStore(initialSettings: AppSettings(
            shortBreakIntervalMinutes: 15,
            shortBreakDurationSeconds: 15,
            longBreakEveryNShortBreaks: 4,
            longBreakDurationSeconds: 300,
            preBreakNoticeSeconds: 10,
            strictMode: false,
            allowPostpone: true,
            postponeMinutes: 5,
            idlePauseThresholdSeconds: 10
        ))
        fakeIdle = FakeIdle(initialIdleSeconds: 0)
        fakeClock = FakeClock()
        fakeNotifier = FakeNotifier()
        fakeOverlay = FakeOverlay()

        timerManager = TimerManager(
            settings: fakeSettings,
            idle: fakeIdle,
            time: fakeClock,
            notifier: fakeNotifier,
            overlay: fakeOverlay
        )
    }

    func testInitialStateAndCountdown() {
        XCTAssertEqual(timerManager.state, .working(remaining: 900, shortBreaksSinceLong: 0))
        XCTAssertEqual(timerManager.nextBreakCountdown, 900)
    }

    func testTakeBreakNowDispatchesOverlay() {
        timerManager.send(.takeBreakNow(.short))

        XCTAssertEqual(timerManager.state, .onBreak(kind: .short, remaining: 15, total: 15, shortBreaksSinceLong: 0))
        XCTAssertTrue(fakeOverlay.isShowing)
        XCTAssertEqual(fakeOverlay.lastShownKind, .short)
        XCTAssertEqual(fakeOverlay.lastShownStrict, false)
    }

    func testSkipBreakHidesOverlay() {
        timerManager.send(.takeBreakNow(.short))
        XCTAssertTrue(fakeOverlay.isShowing)

        timerManager.send(.skipBreak(force: false))
        XCTAssertFalse(fakeOverlay.isShowing)
        XCTAssertEqual(fakeOverlay.hideCallCount, 1)
        XCTAssertEqual(timerManager.state, .working(remaining: 900, shortBreaksSinceLong: 1))
    }

    func testSleepGapDiscontinuityTriggersIdleCredit() {
        // Start manager
        timerManager.start()

        // Advance fake clock by 100 seconds (greater than 5s threshold)
        fakeClock.advance(by: 100)

        // Trigger tick directly via send of idleCredit
        timerManager.send(.idleCredit(100))

        // 100s is >= short break duration (15s), so short break should be credited
        XCTAssertEqual(timerManager.state, .working(remaining: 900, shortBreaksSinceLong: 1))

        timerManager.stop()
        XCTAssertEqual(timerManager.state, .disabled)
    }

    func testSettingsPublisherChangeUpdatesTimerManager() {
        XCTAssertEqual(timerManager.nextBreakCountdown, 900)

        fakeSettings.update { settings in
            settings.shortBreakIntervalMinutes = 10
        }

        // TimerManager should have clamped remaining to 600s
        XCTAssertEqual(timerManager.nextBreakCountdown, 600)
    }
}
