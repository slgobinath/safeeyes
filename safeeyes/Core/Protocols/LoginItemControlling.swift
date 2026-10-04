import Foundation

public protocol LoginItemControlling: AnyObject {
    var isEnabled: Bool { get }
    var requiresApproval: Bool { get }
    func setEnabled(_ enabled: Bool) throws
    func openLoginItemsSettings()
}
