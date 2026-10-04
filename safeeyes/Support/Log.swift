import Foundation
import os

enum Log {
    private static let subsystem = "com.safeeyes.app"

    static let app = Logger(subsystem: subsystem, category: "app")
    static let idle = Logger(subsystem: subsystem, category: "idle")
    static let timer = Logger(subsystem: subsystem, category: "timer")
    static let overlay = Logger(subsystem: subsystem, category: "overlay")
    static let settings = Logger(subsystem: subsystem, category: "settings")
    static let notifications = Logger(subsystem: subsystem, category: "notifications")
}
