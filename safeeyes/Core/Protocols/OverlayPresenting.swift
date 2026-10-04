import Foundation

@MainActor
public protocol OverlayPresenting: AnyObject {
    func show(kind: BreakKind, strict: Bool)
    func hide()
}
