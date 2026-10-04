import Foundation

public protocol IdleProviding {
    func secondsSinceLastInput() -> TimeInterval
}
