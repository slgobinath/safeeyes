import Foundation
import Combine
import os

@MainActor
public final class SettingsManager: ObservableObject, SettingsStoring {
    public static let settingsKey = "com.safeeyes.settings.v1"

    @Published public private(set) var settings: AppSettings

    public var settingsPublisher: AnyPublisher<AppSettings, Never> {
        $settings.eraseToAnyPublisher()
    }

    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        if let data = defaults.data(forKey: Self.settingsKey) {
            self.settings = Self.loadSettings(from: data)
        } else {
            self.settings = AppSettings.default
        }
    }

    public func update(_ mutate: (inout AppSettings) -> Void) {
        var copy = settings
        mutate(&copy)
        let validated = copy.validated()
        settings = validated
        save(validated)
    }

    public func reset() {
        let resetSettings = AppSettings.default
        settings = resetSettings
        save(resetSettings)
    }

    private func save(_ newSettings: AppSettings) {
        do {
            let data = try JSONEncoder().encode(newSettings)
            defaults.set(data, forKey: Self.settingsKey)
            Log.settings.debug("Settings successfully saved")
        } catch {
            Log.settings.error("Failed to encode settings: \(error.localizedDescription, privacy: .public)")
        }
    }

    private static func loadSettings(from data: Data) -> AppSettings {
        do {
            let decoded = try JSONDecoder().decode(AppSettings.self, from: data)
            return migrate(decoded).validated()
        } catch {
            Log.settings.error("Failed to decode settings data, falling back to default: \(error.localizedDescription, privacy: .public)")
            return AppSettings.default
        }
    }

    public static func migrate(_ current: AppSettings) -> AppSettings {
        switch current.schemaVersion {
        case 1:
            return current
        default:
            // Future schema migrations go here
            return current
        }
    }
}
