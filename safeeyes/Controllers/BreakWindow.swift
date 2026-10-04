import AppKit

public final class BreakWindow: NSWindow {
    private var isRealTeardown = false

    public init(screen: NSScreen) {
        super.init(
            contentRect: screen.frame,
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )

        self.level = NSWindow.Level(rawValue: Int(CGShieldingWindowLevel()))
        self.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
        self.isOpaque = false
        self.backgroundColor = .clear
        self.hasShadow = false
        self.isReleasedWhenClosed = false
        self.ignoresMouseEvents = false
    }

    public override var canBecomeKey: Bool {
        return true
    }

    public override var canBecomeMain: Bool {
        return true
    }

    // Windows have no close/skip UI; intercept close calls so users/system cannot close it
    public override func performClose(_ sender: Any?) {
        // No-op by design
    }

    public override func close() {
        if isRealTeardown {
            super.close()
        }
        // No-op otherwise; only teardown() can close
    }

    public func teardown() {
        isRealTeardown = true
        orderOut(nil)
        super.close()
    }
}
