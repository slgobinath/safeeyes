import SwiftUI

public struct SecondaryScreenView: View {
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
            Color.black.opacity(0.92)
                .ignoresSafeArea()

            VStack(spacing: 16) {
                Text(viewModel.formattedRemaining)
                    .font(.system(size: 72, weight: .thin, design: .rounded))
                    .foregroundColor(.white.opacity(0.8))

                Text(LocalizedStringKey("Rest Your Eyes"))
                    .font(.system(size: 18, weight: .light, design: .rounded))
                    .foregroundColor(.white.opacity(0.4))
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Break in progress: \(viewModel.formattedRemaining) remaining. Rest your eyes.")
        }
        .environment(\.locale, Locale(identifier: appLanguage))
        .environment(\.layoutDirection, appLanguage == "ar" ? .rightToLeft : .leftToRight)
    }
}
