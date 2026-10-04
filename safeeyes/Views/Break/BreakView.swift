import SwiftUI

public struct BreakView: View {
    @ObservedObject public var viewModel: BreakViewModel
    @AppStorage("appLanguage") private var appLanguage: String = {
        UserDefaults.standard.string(forKey: "appLanguage") ??
        (Locale.preferredLanguages.first?.hasPrefix("ar") == true ? "ar" : "en")
    }()

    public init(viewModel: BreakViewModel) {
        self.viewModel = viewModel
    }

    public var body: some View {
        ZStack {
            // Background blur + deep dark tint
            Color.black.opacity(0.85)
                .ignoresSafeArea()
            Rectangle()
                .fill(.ultraThinMaterial)
                .ignoresSafeArea()

            VStack(spacing: 32) {
                // Header: Break Kind badge
                HStack(spacing: 8) {
                    Image(systemName: viewModel.breakKind == .short ? "eye" : "figure.walk")
                        .font(.system(size: 15, weight: .semibold))
                    Text(LocalizedStringKey(viewModel.breakKind == .short ? "SHORT BREAK" : "LONG BREAK"))
                        .font(.system(size: 13, weight: .bold, design: .rounded))
                        .tracking(1.5)
                }
                .foregroundColor(.white.opacity(0.75))
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Capsule().fill(Color.white.opacity(0.1)))
                .accessibilityElement(children: .combine)
                .accessibilityLabel(LocalizedStringKey(viewModel.breakKind == .short ? "Short break active" : "Long break active"))

                // Centerpiece: Countdown ring
                CountdownRing(
                    progress: viewModel.progress,
                    displayText: viewModel.formattedRemaining,
                    unitText: "",
                    diameter: 220
                )

                // Exercise info (if available)
                if let exercise = viewModel.currentExercise {
                    VStack(spacing: 12) {
                        HStack(spacing: 8) {
                            Image(systemName: exercise.symbol)
                                .font(.system(size: 20))
                                .foregroundColor(.cyan)
                            Text(LocalizedStringKey(exercise.title))
                                .font(.system(size: 24, weight: .semibold, design: .rounded))
                                .foregroundColor(.white)
                        }

                        Text(LocalizedStringKey(exercise.instruction))
                            .font(.system(size: 16, weight: .regular))
                            .foregroundColor(.white.opacity(0.8))
                            .multilineTextAlignment(.center)
                            .lineSpacing(4)
                            .frame(maxWidth: 480)
                    }
                    .padding(.horizontal, 24)
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("Exercise: \(exercise.title). \(exercise.instruction)")
                }

                Spacer().frame(height: 16)

                // Actions area
                if viewModel.isStrict {
                    HStack(spacing: 8) {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 14))
                        Text(LocalizedStringKey("Strict Mode Active"))
                            .font(.system(size: 14, weight: .medium, design: .rounded))
                    }
                    .foregroundColor(.white.opacity(0.5))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Capsule().stroke(Color.white.opacity(0.2), lineWidth: 1))
                    .accessibilityLabel(LocalizedStringKey("Strict mode is active. Skipping and postponing are disabled."))
                } else {
                    HStack(spacing: 20) {
                        if viewModel.allowPostpone {
                            Button(action: {
                                viewModel.postpone()
                            }) {
                                HStack(spacing: 6) {
                                    Image(systemName: "clock.arrow.circlepath")
                                        .flipsForRightToLeftLayoutDirection(true)
                                    Text(LocalizedStringKey("Postpone"))
                                }
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(.white.opacity(0.9))
                                .padding(.horizontal, 20)
                                .padding(.vertical, 10)
                                .background(Capsule().fill(Color.white.opacity(0.15)))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel(LocalizedStringKey("Postpone break"))
                            .accessibilityHint(LocalizedStringKey("Postpones the break for the configured duration"))
                        }

                        Button(action: {
                            viewModel.skip()
                        }) {
                            HStack(spacing: 6) {
                                Image(systemName: "forward.end.fill")
                                    .flipsForRightToLeftLayoutDirection(true)
                                Text(LocalizedStringKey("Skip (Esc)"))
                            }
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(.white)
                            .padding(.horizontal, 22)
                            .padding(.vertical, 10)
                            .background(Capsule().fill(Color.cyan.opacity(0.8)))
                        }
                        .buttonStyle(.plain)
                        .keyboardShortcut(.cancelAction) // Esc shortcut
                        .accessibilityLabel(LocalizedStringKey("Skip break"))
                        .accessibilityHint(LocalizedStringKey("Skips the current break. Can also press Escape."))
                    }
                }
            }
            .padding(40)
        }
        .environment(\.locale, Locale(identifier: appLanguage))
        .environment(\.layoutDirection, appLanguage == "ar" ? .rightToLeft : .leftToRight)
    }
}
