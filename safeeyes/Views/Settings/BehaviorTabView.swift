import SwiftUI

struct BehaviorTabView: View {
    @ObservedObject var viewModel: SettingsViewModel

    var body: some View {
        Form {
            Section {
                Toggle(LocalizedStringKey("Strict Mode"), isOn: $viewModel.strictMode)
                    .accessibilityLabel(LocalizedStringKey("Strict mode"))
                    .accessibilityHint(LocalizedStringKey("When enabled, breaks cannot be skipped or postponed"))

                Toggle(LocalizedStringKey("Allow Postpone"), isOn: $viewModel.allowPostpone)
                    .disabled(viewModel.isPostponeDisabled)
                    .accessibilityLabel(LocalizedStringKey("Allow postponing breaks"))

                if viewModel.isPostponeDisabled {
                    Text(LocalizedStringKey("Postpone is disabled in Strict Mode"))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                if viewModel.allowPostpone && !viewModel.strictMode {
                    Stepper(
                        LocalizedStringKey("Postpone duration: \(viewModel.postponeMinutes) min"),
                        value: $viewModel.postponeMinutes,
                        in: 1...30,
                        step: 1
                    )
                    .accessibilityLabel(LocalizedStringKey("Postpone duration in minutes"))
                }
            } header: {
                Label(LocalizedStringKey("Break Enforcement"), systemImage: "lock.shield")
            }

            Section {
                Stepper(
                    LocalizedStringKey("Idle pause after \(viewModel.idlePauseThresholdSeconds) sec"),
                    value: $viewModel.idlePauseThresholdSeconds,
                    in: 5...600,
                    step: 5
                )
                .accessibilityLabel(LocalizedStringKey("Idle pause threshold in seconds"))
            } header: {
                Label(LocalizedStringKey("Idle Detection"), systemImage: "moon.zzz")
            }

            Section {
                Toggle(LocalizedStringKey("Play Sounds"), isOn: $viewModel.playSounds)
                    .accessibilityLabel(LocalizedStringKey("Play end-of-break chime"))

                Toggle(LocalizedStringKey("Show Exercises"), isOn: $viewModel.showExercises)
                    .accessibilityLabel(LocalizedStringKey("Show exercise suggestions during breaks"))
            } header: {
                Label(LocalizedStringKey("Extras"), systemImage: "sparkles")
            }
        }
        .formStyle(.grouped)
    }
}
