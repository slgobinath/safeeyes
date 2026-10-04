import Foundation
@testable import SafeEyes

@MainActor
public final class FakeOverlay: OverlayPresenting {
    public var isShowing = false
    public var lastShownKind: BreakKind?
    public var lastShownStrict: Bool?
    public var showCallCount = 0
    public var hideCallCount = 0

    public init() {}

    public func show(kind: BreakKind, strict: Bool) {
        isShowing = true
        lastShownKind = kind
        lastShownStrict = strict
        showCallCount += 1
    }

    public func hide() {
        isShowing = false
        hideCallCount += 1
    }

    public func reset() {
        isShowing = false
        lastShownKind = nil
        lastShownStrict = nil
        showCallCount = 0
        hideCallCount = 0
    }
}
