import SwiftUI

// MARK: - Tab definition

private enum SettingsTab: CaseIterable, Identifiable {
    case breaks, behavior, general, about

    var id: Self { self }

    var labelKey: LocalizedStringKey {
        switch self {
        case .breaks:   return "Breaks"
        case .behavior: return "Behavior"
        case .general:  return "General"
        case .about:    return "About"
        }
    }

    var symbol: String {
        switch self {
        case .breaks:   return "cup.and.saucer.fill"
        case .behavior: return "gearshape.2.fill"
        case .general:  return "wrench.and.screwdriver.fill"
        case .about:    return "info.circle.fill"
        }
    }
}

// MARK: - Root View

struct SettingsRootView: View {
    @ObservedObject var viewModel: SettingsViewModel
    @State private var selectedTab: SettingsTab = .breaks

    var body: some View {
        VStack(spacing: 0) {
            // ── Custom tab toolbar ──────────────────────────────────────────
            customTabBar
                .padding(.horizontal, 16)
                .padding(.top, 14)
                .padding(.bottom, 10)

            Divider()
                .opacity(0.4)

            // ── Tab content ────────────────────────────────────────────────
            Group {
                switch selectedTab {
                case .breaks:   BreaksTabView(viewModel: viewModel)
                case .behavior: BehaviorTabView(viewModel: viewModel)
                case .general:  GeneralTabView(viewModel: viewModel)
                case .about:    AboutTabView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(width: 480, height: 460)
        .id(viewModel.appLanguage)
        .environment(\.locale, Locale(identifier: viewModel.appLanguage))
        .environment(\.layoutDirection, viewModel.appLanguage == "ar" ? .rightToLeft : .leftToRight)
    }

    // MARK: Tab bar

    private var customTabBar: some View {
        HStack(spacing: 4) {
            ForEach(SettingsTab.allCases) { tab in
                tabButton(for: tab)
            }
        }
        .padding(4)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(.quaternary)
        )
    }

    @ViewBuilder
    private func tabButton(for tab: SettingsTab) -> some View {
        let isSelected = selectedTab == tab

        Button {
            withAnimation(.easeInOut(duration: 0.18)) {
                selectedTab = tab
            }
        } label: {
            VStack(spacing: 4) {
                Image(systemName: tab.symbol)
                    .font(.system(size: 16, weight: isSelected ? .semibold : .regular))
                    .symbolRenderingMode(.hierarchical)
                Text(tab.labelKey)
                    .font(.system(size: 11, weight: isSelected ? .semibold : .regular))
            }
            .foregroundStyle(isSelected ? Color.accentColor : .secondary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 7)
            .padding(.horizontal, 8)
            .background(
                Group {
                    if isSelected {
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .fill(.background)
                            .shadow(color: .black.opacity(0.08), radius: 3, x: 0, y: 1)
                    }
                }
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel(tab.labelKey)
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }
}
