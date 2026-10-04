import SwiftUI

struct GeneralTabView: View {
    @ObservedObject var viewModel: SettingsViewModel
    @State private var showResetConfirmation = false

    var body: some View {
        Form {
            Section {
                Toggle(LocalizedStringKey("Launch SafeEyes at Login"), isOn: Binding(
                    get: { viewModel.launchAtLogin },
                    set: { viewModel.setLaunchAtLogin($0) }
                ))
                .accessibilityLabel(LocalizedStringKey("Launch SafeEyes at login"))

                if viewModel.loginItemRequiresApproval {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(LocalizedStringKey("macOS requires user approval in System Settings for SafeEyes to launch at login."))
                            .font(.footnote)
                            .foregroundColor(.orange)

                        Button(LocalizedStringKey("Open Login Items Settings")) {
                            viewModel.openLoginItemsSettings()
                        }
                    }
                    .padding(.vertical, 4)
                }
            } header: {
                Label(LocalizedStringKey("Startup"), systemImage: "power")
            }

            Section {
                Picker(LocalizedStringKey("Language"), selection: $viewModel.appLanguage) {
                    Text("English").tag("en")
                    Text("العربية").tag("ar")
                }
                .accessibilityLabel(LocalizedStringKey("Application language"))

                Text(LocalizedStringKey("Restart the app to apply language changes to the Menu Bar."))
                    .font(.footnote)
                    .foregroundColor(.secondary)
            } header: {
                Label(LocalizedStringKey("Language"), systemImage: "globe")
            }

            Section {
                Button(role: .destructive) {
                    showResetConfirmation = true
                } label: {
                    HStack {
                        Image(systemName: "arrow.counterclockwise")
                        Text(LocalizedStringKey("Reset All Settings to Defaults"))
                    }
                }
                .accessibilityLabel(LocalizedStringKey("Reset all settings to default values"))
                .confirmationDialog(
                    LocalizedStringKey("Reset all settings to their default values?"),
                    isPresented: $showResetConfirmation,
                    titleVisibility: .visible
                ) {
                    Button(LocalizedStringKey("Reset"), role: .destructive) {
                        viewModel.resetToDefaults()
                    }
                    Button(LocalizedStringKey("Cancel"), role: .cancel) { }
                }
            } header: {
                Label(LocalizedStringKey("Reset"), systemImage: "arrow.triangle.2.circlepath")
            }
        }
        .formStyle(.grouped)
    }
}
