import Foundation

public protocol TimeSource {
    var now: Date { get }
}
