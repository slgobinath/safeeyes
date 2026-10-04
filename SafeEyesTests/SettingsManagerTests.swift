import XCTest
import Combine
@testable import SafeEyes

@MainActor
final class SettingsManagerTests: XCTestCase {
    private var testDefaults: UserDefaults!
    private var suiteName: String!
    private var cancellables: Set<AnyCancellable>!

    override func setUp() {
        super.setUp()
        suiteName = "com.safeeyes.test.\(UUID().uuidString)"
        testDefaults = UserDefaults(suiteName: suiteName)!
        cancellables = []
    }

    override func tearDown() {
        testDefaults.removePersistentDomain(forName: suiteName)
        testDefaults = nil
        cancellables = nil
        super.tearDown()
    }

    func testDefaultsRoundTrip() {
        let manager1 = SettingsManager(defaults: testDefaults)
        XCTAssertEqual(manager1.settings, AppSettings.default)

        manager1.update { settings in
            settings.shortBreakIntervalMinutes = 20
            settings.shortBreakDurationSeconds = 30
            settings.strictMode = true
        }

        XCTAssertEqual(manager1.settings.shortBreakIntervalMinutes, 20)
        XCTAssertEqual(manager1.settings.shortBreakDurationSeconds, 30)
        XCTAssertTrue(manager1.settings.strictMode)
        XCTAssertFalse(manager1.settings.allowPostpone) // strict mode disables postpone

        // Recreate manager with same defaults to test persistence
        let manager2 = SettingsManager(defaults: testDefaults)
        XCTAssertEqual(manager2.settings.shortBreakIntervalMinutes, 20)
        XCTAssertEqual(manager2.settings.shortBreakDurationSeconds, 30)
        XCTAssertTrue(manager2.settings.strictMode)
        XCTAssertFalse(manager2.settings.allowPostpone)
    }

    func testClampingOfOutOfRangeValues() {
        let settings = AppSettings(
            shortBreakIntervalMinutes: 999, // max 120
            shortBreakDurationSeconds: 2,   // min 5
            longBreakEveryNShortBreaks: 0,   // min 1
            longBreakDurationSeconds: 10000, // max 1800
            preBreakNoticeSeconds: 99,       // max 60
            strictMode: true,
            allowPostpone: true,             // must be false if strictMode is true
            postponeMinutes: 0,              // min 1
            idlePauseThresholdSeconds: 1     // min 5
        )

        let validated = settings.validated()
        XCTAssertEqual(validated.shortBreakIntervalMinutes, 120)
        XCTAssertEqual(validated.shortBreakDurationSeconds, 5)
        XCTAssertEqual(validated.longBreakEveryNShortBreaks, 1)
        XCTAssertEqual(validated.longBreakDurationSeconds, 1800)
        XCTAssertEqual(validated.preBreakNoticeSeconds, 60)
        XCTAssertFalse(validated.allowPostpone)
        XCTAssertEqual(validated.postponeMinutes, 1)
        XCTAssertEqual(validated.idlePauseThresholdSeconds, 5)
    }

    func testCorruptDataFallback() {
        testDefaults.set(Data("corrupt json string".utf8), forKey: SettingsManager.settingsKey)
        let manager = SettingsManager(defaults: testDefaults)
        XCTAssertEqual(manager.settings, AppSettings.default)
    }

    func testPublisherEmitsOnUpdate() {
        let manager = SettingsManager(defaults: testDefaults)
        var received: [AppSettings] = []
        let expectation = expectation(description: "Publisher emits update")

        manager.settingsPublisher
            .dropFirst() // Skip initial value
            .sink { settings in
                received.append(settings)
                expectation.fulfill()
            }
            .store(in: &cancellables)

        manager.update { settings in
            settings.shortBreakIntervalMinutes = 25
        }

        waitForExpectations(timeout: 1.0)
        XCTAssertEqual(received.count, 1)
        XCTAssertEqual(received.first?.shortBreakIntervalMinutes, 25)
    }

    func testResetRestoresDefaults() {
        let manager = SettingsManager(defaults: testDefaults)
        manager.update { settings in
            settings.shortBreakIntervalMinutes = 50
            settings.strictMode = true
        }
        XCTAssertNotEqual(manager.settings, AppSettings.default)

        manager.reset()
        XCTAssertEqual(manager.settings, AppSettings.default)
    }
}
