import Foundation

public struct BreakContent: Identifiable, Codable, Equatable {
    public enum TargetKind: String, Codable, Equatable {
        case short
        case long
        case both
    }

    public let id: String
    public let title: String
    public let instruction: String
    public let symbol: String
    public let kind: TargetKind

    public init(id: String, title: String, instruction: String, symbol: String, kind: TargetKind) {
        self.id = id
        self.title = title
        self.instruction = instruction
        self.symbol = symbol
        self.kind = kind
    }
}
