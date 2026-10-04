import AppKit
import Combine

@MainActor
public final class MenuBarController: NSObject, NSMenuDelegate {
    private let timer: TimerManager
    private let onOpenSettings: () -> Void
    private var statusItem: NSStatusItem?
    private var cancellables = Set<AnyCancellable>()

    // Retained menu item references for dynamic updates
    private let statusMenuItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    /// Custom text-field view assigned to statusMenuItem.view so that
    /// it remains live-updatable even while NSEventTrackingRunLoopMode
    /// is active (i.e. while the menu is pulled down).
    private let countdownTextField: NSTextField = {
        let tf = NSTextField()
        tf.drawsBackground = false
        tf.isBordered = false
        tf.isEditable = false
        tf.isSelectable = false
        tf.font = NSFont.systemFont(ofSize: 13, weight: .regular)
        tf.textColor = NSColor.secondaryLabelColor
        return tf
    }()
    private let takeBreakItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private let shortBreakItem = NSMenuItem(title: "", action: #selector(takeShortBreak), keyEquivalent: "")
    private let longBreakItem = NSMenuItem(title: "", action: #selector(takeLongBreak), keyEquivalent: "")
    private let pauseResumeItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private let skipBreakItem = NSMenuItem(title: "", action: #selector(skipClicked), keyEquivalent: "")
    private let settingsItem = NSMenuItem(title: "", action: #selector(settingsClicked), keyEquivalent: ",")
    private let aboutItem = NSMenuItem(title: "", action: #selector(aboutClicked), keyEquivalent: "")
    private let quitItem = NSMenuItem(title: "", action: #selector(quitClicked), keyEquivalent: "q")

    public init(timer: TimerManager, onOpenSettings: @escaping () -> Void) {
        self.timer = timer
        self.onOpenSettings = onOpenSettings
        super.init()

        shortBreakItem.target = self
        longBreakItem.target = self
        skipBreakItem.target = self
        settingsItem.target = self
        aboutItem.target = self
        quitItem.target = self

        // Observe timer state changes to refresh menu bar icon and text
        timer.$state
            .sink { [weak self] _ in
                self?.refresh()
            }
            .store(in: &cancellables)

        // Ensure 1 Hz live countdown updates on RunLoop.main in .common mode while the menu is tracked/open
        Timer.publish(every: 1.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.refresh()
            }
            .store(in: &cancellables)
    }

    public func install() {
        guard statusItem == nil else { return }

        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        let menu = NSMenu()
        menu.delegate = self

        // Status Line – use a custom NSTextField so the countdown ticks
        // live while the menu is open (NSEventTrackingRunLoopMode exemption).
        // IMPORTANT: NSMenuItem.view must have an explicit frame; a zero-frame
        // view is invisible. We use frame-based layout (no Auto Layout on the
        // container itself) so AppKit can measure it before the menu is shown.
        statusMenuItem.isEnabled = false

        let containerWidth: CGFloat = 240
        let containerHeight: CGFloat = 26
        let hPad: CGFloat = 14
        let vPad: CGFloat = 4

        let container = NSView(frame: NSRect(x: 0, y: 0, width: containerWidth, height: containerHeight))
        // The text field fills the container minus padding; autoresizes with the container.
        countdownTextField.translatesAutoresizingMaskIntoConstraints = true
        countdownTextField.frame = NSRect(
            x: hPad,
            y: vPad,
            width: containerWidth - hPad * 2,
            height: containerHeight - vPad * 2
        )
        countdownTextField.autoresizingMask = [.width, .height]
        container.addSubview(countdownTextField)
        statusMenuItem.view = container
        menu.addItem(statusMenuItem)

        // Take a Break Now Submenu
        let takeBreakSubmenu = NSMenu()
        takeBreakSubmenu.addItem(shortBreakItem)
        takeBreakSubmenu.addItem(longBreakItem)
        takeBreakItem.submenu = takeBreakSubmenu
        menu.addItem(takeBreakItem)

        // Pause / Resume Item
        menu.addItem(pauseResumeItem)

        // Skip Next Break
        menu.addItem(skipBreakItem)

        menu.addItem(NSMenuItem.separator())
        menu.addItem(settingsItem)
        menu.addItem(aboutItem)
        menu.addItem(NSMenuItem.separator())
        menu.addItem(quitItem)

        item.menu = menu
        self.statusItem = item

        refresh()
    }

    public func refresh() {
        updateIcon()
        updateStaticMenuTitles()
        updateCountdownTextField()
        updatePauseResumeMenu()
        updateSkipAndQuitItems()
    }

    // MARK: - NSMenuDelegate

    public func menuWillOpen(_ menu: NSMenu) {
        refresh()
    }

    // MARK: - Localization Helper

    private func loc(_ key: String) -> String {
        let chosenLang: String? = UserDefaults.standard.string(forKey: "appLanguage") ?? {
            guard let langs = UserDefaults.standard.array(forKey: "AppleLanguages") as? [String],
                  let first = langs.first else { return nil }
            return first
        }()

        if let lang = chosenLang {
            if lang.hasPrefix("ar"),
               let path = Bundle.main.path(forResource: "ar", ofType: "lproj"),
               let bundle = Bundle(path: path) {
                return bundle.localizedString(forKey: key, value: key, table: nil)
            } else if lang.hasPrefix("en"),
                      let path = Bundle.main.path(forResource: "en", ofType: "lproj"),
                      let bundle = Bundle(path: path) {
                return bundle.localizedString(forKey: key, value: key, table: nil)
            }
        }
        return NSLocalizedString(key, comment: "")
    }

    // MARK: - Typography & Title Formatting

    private func setItemTitle(
        _ item: NSMenuItem,
        title: String,
        font: NSFont = NSFont.menuBarFont(ofSize: 0),
        isSecondary: Bool = false
    ) {
        item.title = title

        let isArabic: Bool = {
            if let saved = UserDefaults.standard.string(forKey: "appLanguage") {
                return saved == "ar"
            }
            if let langs = UserDefaults.standard.array(forKey: "AppleLanguages") as? [String],
               let first = langs.first {
                return first.hasPrefix("ar")
            }
            return Locale.preferredLanguages.first?.hasPrefix("ar") == true
        }()

        let paragraphStyle = NSMutableParagraphStyle()
        paragraphStyle.baseWritingDirection = isArabic ? .rightToLeft : .leftToRight
        paragraphStyle.alignment = .natural

        var attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .paragraphStyle: paragraphStyle
        ]
        if isSecondary {
            attributes[.foregroundColor] = NSColor.secondaryLabelColor
        }
        item.attributedTitle = NSAttributedString(string: title, attributes: attributes)
    }

    // MARK: - UI Updates

    private func updateIcon() {
        guard let button = statusItem?.button else { return }

        let isPausedOrDisabled: Bool
        switch timer.state {
        case .paused, .disabled:
            isPausedOrDisabled = true
        default:
            isPausedOrDisabled = false
        }

        let symbolName = isPausedOrDisabled ? "eye.slash" : "eye"
        let image = NSImage(systemSymbolName: symbolName, accessibilityDescription: "SafeEyes")
        image?.isTemplate = true
        button.image = image
    }

    private func updateStaticMenuTitles() {
        setItemTitle(takeBreakItem, title: loc("Take a Break Now"))
        setItemTitle(shortBreakItem, title: loc("Short Break"))
        setItemTitle(longBreakItem, title: loc("Long Break"))
        setItemTitle(skipBreakItem, title: loc("Skip Next Break"))
        setItemTitle(settingsItem, title: loc("Settings…"))
        setItemTitle(aboutItem, title: loc("About SafeEyes"))
        setItemTitle(quitItem, title: loc("Quit SafeEyes"))
    }

    // MARK: - Live Countdown TextField

    private func isArabic() -> Bool {
        if let saved = UserDefaults.standard.string(forKey: "appLanguage") {
            return saved == "ar"
        }
        if let langs = UserDefaults.standard.array(forKey: "AppleLanguages") as? [String],
           let first = langs.first {
            return first.hasPrefix("ar")
        }
        return Locale.preferredLanguages.first?.hasPrefix("ar") == true
    }

    private func updateCountdownTextField() {
        let arabic = isArabic()
        countdownTextField.alignment = arabic ? .right : .left

        let text: String
        switch timer.state {
        case .working(let remaining, _):
            let format = loc("Next break in %@")
            text = String(format: format, formatTime(remaining))

        case .preBreak(let kind, let remaining, _):
            let format = (kind == .short)
                ? loc("Short break in %@")
                : loc("Long break in %@")
            text = String(format: format, formatTime(remaining))

        case .onBreak(let kind, let remaining, _, _):
            let format = (kind == .short)
                ? loc("On a short break (%@)")
                : loc("On a long break (%@)")
            text = String(format: format, formatTime(remaining))

        case .paused(let reason, _):
            switch reason {
            case .idle:
                text = loc("Paused (idle)")
            case .user(let until):
                if let until = until {
                    let formatter = DateFormatter()
                    formatter.dateFormat = "HH:mm"
                    let format = loc("Paused until %@")
                    text = String(format: format, formatter.string(from: until))
                } else {
                    text = loc("Paused")
                }
            case .system:
                text = loc("Paused (system)")
            }

        case .disabled:
            text = loc("SafeEyes Disabled")
        }

        // Build an attributed string so we can enforce font + writing direction
        // without touching NSMenuItem.attributedTitle (which is suppressed during tracking).
        let paragraphStyle = NSMutableParagraphStyle()
        paragraphStyle.baseWritingDirection = arabic ? .rightToLeft : .leftToRight
        paragraphStyle.alignment = arabic ? .right : .left

        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 13, weight: .regular),
            .foregroundColor: NSColor.secondaryLabelColor,
            .paragraphStyle: paragraphStyle
        ]
        countdownTextField.attributedStringValue = NSAttributedString(string: text, attributes: attrs)
    }

    private func updatePauseResumeMenu() {
        switch timer.state {
        case .paused:
            setItemTitle(pauseResumeItem, title: loc("Resume"))
            pauseResumeItem.target = self
            pauseResumeItem.action = #selector(resumeClicked)
            pauseResumeItem.submenu = nil
        default:
            setItemTitle(pauseResumeItem, title: loc("Pause"))
            pauseResumeItem.target = nil
            pauseResumeItem.action = nil

            let pauseSubmenu = NSMenu()

            let m30 = NSMenuItem(title: "", action: #selector(pauseDurationClicked(_:)), keyEquivalent: "")
            m30.tag = 30
            m30.target = self
            setItemTitle(m30, title: loc("30 Minutes"))
            pauseSubmenu.addItem(m30)

            let m60 = NSMenuItem(title: "", action: #selector(pauseDurationClicked(_:)), keyEquivalent: "")
            m60.tag = 60
            m60.target = self
            setItemTitle(m60, title: loc("1 Hour"))
            pauseSubmenu.addItem(m60)

            let m120 = NSMenuItem(title: "", action: #selector(pauseDurationClicked(_:)), keyEquivalent: "")
            m120.tag = 120
            m120.target = self
            setItemTitle(m120, title: loc("2 Hours"))
            pauseSubmenu.addItem(m120)

            let mForever = NSMenuItem(title: "", action: #selector(pauseDurationClicked(_:)), keyEquivalent: "")
            mForever.tag = 0
            mForever.target = self
            setItemTitle(mForever, title: loc("Until I Resume"))
            pauseSubmenu.addItem(mForever)

            pauseResumeItem.submenu = pauseSubmenu
        }
    }

    private func updateSkipAndQuitItems() {
        let isStrict = false
        let isStrictOnBreak = false

        // In strict mode while onBreak, quit is disabled
        quitItem.isEnabled = !isStrictOnBreak

        // Skip next break is hidden in strict mode
        skipBreakItem.isHidden = isStrict
    }

    private func formatTime(_ seconds: TimeInterval) -> String {
        let s = max(0, Int(seconds))
        let hours = s / 3600
        let minutes = (s % 3600) / 60
        let remainder = s % 60

        if hours > 0 {
            return String(format: "%dh %dm %02ds", hours, minutes, remainder)
        } else if minutes > 0 {
            return String(format: "%dm %02ds", minutes, remainder)
        } else {
            return "\(remainder)s"
        }
    }

    // MARK: - Actions

    @objc private func takeShortBreak() {
        timer.send(.takeBreakNow(.short))
    }

    @objc private func takeLongBreak() {
        timer.send(.takeBreakNow(.long))
    }

    @objc private func pauseDurationClicked(_ sender: NSMenuItem) {
        let minutes = sender.tag
        if minutes == 0 {
            timer.send(.userPause(duration: nil))
        } else {
            timer.send(.userPause(duration: TimeInterval(minutes * 60)))
        }
    }

    @objc private func resumeClicked() {
        timer.send(.resume)
    }

    @objc private func skipClicked() {
        timer.send(.skipBreak(force: false))
    }

    @objc private func settingsClicked() {
        onOpenSettings()
    }

    @objc private func aboutClicked() {
        NSApp.orderFrontStandardAboutPanel(
            options: [
                NSApplication.AboutPanelOptionKey.applicationName: "SafeEyes",
                NSApplication.AboutPanelOptionKey.version: "1.0.0"
            ]
        )
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func quitClicked() {
        NSApp.terminate(nil)
    }
}
