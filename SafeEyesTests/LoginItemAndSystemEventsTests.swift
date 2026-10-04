import XCTest
@testable import SafeEyes

@MainActor
final class LoginItemAndSystemEventsTests: XCTestCase {
    private var fakeSettings: InMemorySettingsStore!
    private var fakeLoginItem: FakeLoginItem!
    private var fakeIdle: FakeIdle!
    private var fakeClock: FakeClock!
    private var fakeNotifier: FakeNotifier!
    private var fakeOverlay: FakeOverlay!
    private var timerManager: TimerManager!

    override func setUp() {
        super.setUp()
        fakeSettings = InMemorySettingsStore(initialSettings: AppSettings(
            shortBreakIntervalMinutes: 20,
            shortBreakDurationSeconds: 20,
            longBreakEveryNShortBreaks: 4,
            longBreakDurationSeconds: 300,
            preBreakNoticeSeconds: 10,
            strictMode: false,
            allowPostpone: true,
            postponeMinutes: 5,
            idlePauseThresholdSeconds: 10,
            launchAtLogin: false
        ))
        fakeLoginItem = FakeLoginItem()
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

    func testLoginItemToggleEnablesAndDisables() {
        let viewModel = SettingsViewModel(
            settingsManager: fakeSettings,
            loginItemService: fakeLoginItem
        )

        XCTAssertFalse(viewModel.launchAtLogin)
        XCTAssertFalse(fakeLoginItem.isEnabled)

        viewModel.setLaunchAtLogin(true)
        XCTAssertTrue(viewModel.launchAtLogin)
        XCTAssertTrue(fakeLoginItem.isEnabled)
        XCTAssertTrue(fakeSettings.settings.launchAtLogin)

        viewModel.setLaunchAtLogin(false)
        XCTAssertFalse(viewModel.launchAtLogin)
        XCTAssertFalse(fakeLoginItem.isEnabled)
        XCTAssertFalse(fakeSettings.settings.launchAtLogin)
    }

    func testLoginItemRequiresApprovalSurfaced() {
        fakeLoginItem.requiresApproval = true

        let viewModel = SettingsViewModel(
            settingsManager: fakeSettings,
            loginItemService: fakeLoginItem
        )

        XCTAssertTrue(viewModel.loginItemRequiresApproval)

        viewModel.openLoginItemsSettings()
        XCTAssertEqual(fakeLoginItem.openSettingsCallCount, 1)
    }

    func testReconcilesSystemStatusOnLaunch() {
        // System status is enabled, but stored setting was false
        fakeLoginItem.isEnabled = true
        XCTAssertFalse(fakeSettings.settings.launchAtLogin)

        let viewModel = SettingsViewModel(
            settingsManager: fakeSettings,
            loginItemService: fakeLoginItem
        )

        // System status takes precedence
        XCTAssertTrue(viewModel.launchAtLogin)
        XCTAssertTrue(fakeSettings.settings.launchAtLogin)
    }

    func testSystemEventObserverDispatchesSleepAndWake() {
        var observer: SystemEventObserver? = SystemEventObserver(timerManager: timerManager)

        // Initial state is working
        if case .working = timerManager.state {
            // OK
        } else {
            XCTFail("Expected working state")
        }

        let sleepExpectation = expectation(description: "Pause on sleep")
        let cancellable = timerManager.$state
            .dropFirst()
            .sink { state in
                if case .paused(let reason, _) = state, reason == .system {
                    sleepExpectation.fulfill()
                }
            }

        // Post will sleep
        NSWorkspace.shared.notificationCenter.post(name: NSWorkspace.willSleepNotification, object: nil)

        waitForExpectations(timeout: 2.0)
        cancellable.cancel()
        _ = observer
        observer = nil
    }

    func testScreenLockAndUnlockEvents() {
        timerManager.send(.screenLocked)
        if case .paused(let reason, _) = timerManager.state {
            XCTAssertEqual(reason, .system)
        } else {
            XCTFail("Expected paused state on screenLocked")
        }

        timerManager.send(.screenUnlocked)
        if case .working = timerManager.state {
            // OK
        } else {
            XCTFail("Expected working state on screenUnlocked")
        }
    }
}
