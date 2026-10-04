import Foundation
import Combine

@MainActor
public protocol SettingsStoring: AnyObject {
    var settings: AppSettings { get }
    var settingsPublisher: AnyPublisher<AppSettings, Never> { get }
    func update(_ mutate: (inout AppSettings) -> Void)
    func reset()
}
