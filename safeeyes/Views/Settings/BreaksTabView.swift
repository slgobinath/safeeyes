import SwiftUI

struct BreaksTabView: View {
    @ObservedObject var viewModel: SettingsViewModel

    var body: some View {
        Form {
            Section {
                Stepper(
                    LocalizedStringKey("Short break every \(viewModel.shortBreakIntervalMinutes) min"),
                    value: $viewModel.shortBreakIntervalMinutes,
                    in: 1...120,
                    step: 1
                )
                .accessibilityLabel(LocalizedStringKey("Short break interval in minutes"))

                Stepper(
                    LocalizedStringKey("Short break duration: \(viewModel.shortBreakDurationSeconds) sec"),
                    value: $viewModel.shortBreakDurationSeconds,
                    in: 5...300,
                    step: 5
                )
                .accessibilityLabel(LocalizedStringKey("Short break duration in seconds"))
            } header: {
                Label(LocalizedStringKey("Short Breaks"), systemImage: "eye")
            }

            Section {
                Stepper(
                    LocalizedStringKey("Long break every \(viewModel.longBreakEveryNShortBreaks) short breaks"),
                    value: $viewModel.longBreakEveryNShortBreaks,
                    in: 1...20,
                    step: 1
                )
                .accessibilityLabel(LocalizedStringKey("Long break cadence"))

                Stepper(
                    LocalizedStringKey("Long break duration: \(viewModel.longBreakDurationMinutes) min"),
                    value: $viewModel.longBreakDurationMinutes,
                    in: 1...30,
                    step: 1
                )
                .accessibilityLabel(LocalizedStringKey("Long break duration in minutes"))
            } header: {
                Label(LocalizedStringKey("Long Breaks"), systemImage: "figure.walk")
            }

            Section {
                Stepper(
                    LocalizedStringKey("Pre-break notice: \(viewModel.preBreakNoticeSeconds) sec"),
                    value: $viewModel.preBreakNoticeSeconds,
                    in: 0...60,
                    step: 5
                )
                .accessibilityLabel(LocalizedStringKey("Pre-break notification lead time"))
            } header: {
                Label(LocalizedStringKey("Notification"), systemImage: "bell")
            }
        }
        .formStyle(.grouped)
    }
}
