import SwiftUI

public struct CountdownRing: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    public let progress: Double
    public let displayText: String
    public let unitText: String
    public let diameter: CGFloat

    public init(
        progress: Double,
        displayText: String,
        unitText: String = "seconds",
        diameter: CGFloat = 200
    ) {
        self.progress = progress
        self.displayText = displayText
        self.unitText = unitText
        self.diameter = diameter
    }

    public var body: some View {
        ZStack {
            // Background track
            Circle()
                .stroke(Color.white.opacity(0.12), lineWidth: 10)
                .frame(width: diameter, height: diameter)

            // Animated progress ring
            Circle()
                .trim(from: 0.0, to: CGFloat(min(progress, 1.0)))
                .stroke(
                    AngularGradient(
                        gradient: Gradient(colors: [
                            Color(red: 0.2, green: 0.7, blue: 1.0),
                            Color(red: 0.3, green: 0.85, blue: 0.6)
                        ]),
                        center: .center,
                        startAngle: .degrees(-90),
                        endAngle: .degrees(270)
                    ),
                    style: StrokeStyle(lineWidth: 10, lineCap: .round)
                )
                .rotationEffect(.degrees(-90))
                .frame(width: diameter, height: diameter)
                .animation(reduceMotion ? nil : .linear(duration: 0.5), value: progress)

            // Central countdown readout
            VStack(spacing: 2) {
                Text(displayText)
                    .font(.system(size: fontSize, weight: .light, design: .rounded))
                    .foregroundColor(.white)
                    .contentTransition(.numericText())

                if !unitText.isEmpty {
                    Text(LocalizedStringKey(unitText))
                        .font(.system(size: 13, weight: .medium, design: .rounded))
                        .foregroundColor(.white.opacity(0.6))
                        .textCase(.uppercase)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Break countdown timer")
        .accessibilityValue(unitText.isEmpty ? "\(displayText) remaining" : "\(displayText) \(unitText) remaining")
    }

    private var fontSize: CGFloat {
        if displayText.count > 6 {
            return diameter * 0.18
        } else if displayText.count > 4 {
            return diameter * 0.22
        } else {
            return diameter * 0.28
        }
    }
}
