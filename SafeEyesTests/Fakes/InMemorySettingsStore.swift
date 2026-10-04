import Foundation
import Combine
@testable import SafeEyes

@MainActor
public final class InMemorySettingsStore: SettingsStoring {
    @Published public private(set) var settings: AppSettings

    public var settingsPublisher: AnyPublisher<AppSettings, Never> {
        $settings.eraseToAnyPublisher()
    }

    public init(initialSettings: AppSettings = .default) {
        self.settings = initialSettings
    }

    public func update(_ mutate: (inout AppSettings) -> Void) {
        var copy = settings
        mutate(&copy)
        settings = copy.validated()
    }

    public func reset() {
        settings = .default
    }
}
