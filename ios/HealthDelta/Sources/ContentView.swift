import SwiftUI

private enum ClinicalCompassPalette {
    static let backgroundTop = Color(red: 0.93, green: 0.96, blue: 0.95)
    static let backgroundBottom = Color(red: 0.98, green: 0.98, blue: 0.97)
    static let card = Color.white.opacity(0.88)
    static let border = Color(red: 0.77, green: 0.84, blue: 0.83)
    static let accent = Color(red: 0.17, green: 0.44, blue: 0.46)
    static let accentSoft = Color(red: 0.77, green: 0.88, blue: 0.86)
    static let slate = Color(red: 0.17, green: 0.22, blue: 0.26)
    static let muted = Color(red: 0.38, green: 0.45, blue: 0.49)
    static let caution = Color(red: 0.63, green: 0.38, blue: 0.24)
}

struct ContentView: View {
    @StateObject private var viewModel = DashboardViewModel()
    @AppStorage("orinUploadBaseURL") private var uploadBaseURL = ""
    @AppStorage("orinUploadToken") private var uploadToken = ""
    @AppStorage("orinInsightsCanonicalPersonID") private var insightsCanonicalPersonID = ""
    @AppStorage("orinInsightsWindowDays") private var insightsWindowDays = 0
    @State private var didRunLaunchAutomation = false
    @State private var showsConnectionSettings = false
    @State private var localCanonicalPersonID: String?
    @State private var showsManualPatientEntry = false
    @State private var patientAliases: [String: String] = [:]
    @State private var showsPatientAliasEditor = false
    @State private var patientAliasDraft = ""

    var body: some View {
        NavigationStack {
            ZStack {
                LinearGradient(
                    colors: [ClinicalCompassPalette.backgroundTop, ClinicalCompassPalette.backgroundBottom],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        headerView
                        scopeCard
                        overviewCard
                        actionRow
                        primaryTrendCard
                        clinicalNotesCard
                        dataScopeCard
                        connectionStatusCard

                        if let errorMessage = viewModel.errorMessage {
                            attentionCard(message: errorMessage)
                        }

                        Text("For education only. This is not medical advice.")
                            .font(.footnote)
                            .foregroundStyle(ClinicalCompassPalette.muted)
                            .padding(.top, 2)
                    }
                    .padding(.horizontal, 18)
                    .padding(.top, 20)
                    .padding(.bottom, 28)
                }
                .scrollIndicators(.hidden)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        Task {
                            await viewModel.refreshDashboard(
                                baseURLString: uploadBaseURL,
                                bearerToken: uploadToken,
                                canonicalPersonID: normalizedCanonicalPersonID,
                                windowDays: normalizedWindowDays
                            )
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .font(.headline)
                    }
                    .accessibilityLabel("Refresh")

                    Button {
                        showsConnectionSettings = true
                    } label: {
                        Image(systemName: "slider.horizontal.3")
                            .font(.headline)
                    }
                    .accessibilityLabel("Connection settings")
                }
            }
            .sheet(isPresented: $showsConnectionSettings) {
                ConnectionSettingsSheet(
                    uploadBaseURL: $uploadBaseURL,
                    uploadToken: $uploadToken,
                    uploadStatusMessage: viewModel.uploadStatusMessage
                )
            }
            .sheet(isPresented: $showsPatientAliasEditor) {
                PatientAliasSheet(
                    canonicalPersonID: normalizedCanonicalPersonID,
                    aliasDraft: $patientAliasDraft,
                    onSave: savePatientAlias
                )
            }
            .task {
                guard !didRunLaunchAutomation else {
                    return
                }
                didRunLaunchAutomation = true
                refreshLocalScopeMetadata()
                await viewModel.refreshDashboard(
                    baseURLString: uploadBaseURL,
                    bearerToken: uploadToken,
                    canonicalPersonID: normalizedCanonicalPersonID,
                    windowDays: normalizedWindowDays
                )
                if let config = LaunchAutomation.autoUploadConfig() {
                    print("HealthDelta auto-upload launch hook active for \(config.baseURLString)")
                    await viewModel.uploadLatestRun(
                        baseURLString: config.baseURLString,
                        bearerToken: config.bearerToken,
                        canonicalPersonID: normalizedCanonicalPersonID,
                        windowDays: normalizedWindowDays
                    )
                }
            }
        }
    }

    private var headerView: some View {
        HStack(alignment: .top, spacing: 16) {
            ZStack {
                RoundedRectangle(cornerRadius: 26, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [ClinicalCompassPalette.accent, ClinicalCompassPalette.accentSoft],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 72, height: 72)

                Image(systemName: "heart.text.square.fill")
                    .font(.system(size: 34, weight: .semibold))
                    .foregroundStyle(.white)

                Image(systemName: "cross.case.fill")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(ClinicalCompassPalette.accent)
                    .padding(7)
                    .background(Color.white.opacity(0.95), in: Circle())
                    .offset(x: 22, y: 22)
            }
            .shadow(color: ClinicalCompassPalette.accent.opacity(0.18), radius: 20, y: 10)

            VStack(alignment: .leading, spacing: 10) {
                Text("HealthDelta")
                    .font(.largeTitle.weight(.semibold))
                    .fontDesign(.serif)
                    .foregroundStyle(ClinicalCompassPalette.slate)

                Text("Clinical Compass")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(ClinicalCompassPalette.accent)
                    .textCase(.uppercase)

                Text("A calmer view of your current record, recent trend, and data quality.")
                    .font(.callout)
                    .foregroundStyle(ClinicalCompassPalette.muted)
            }
        }
    }

    private var scopeCard: some View {
        CompassCard {
            VStack(alignment: .leading, spacing: 14) {
                CompassSectionHeader(
                    eyebrow: "Scope",
                    title: "Patient & Window"
                )

                Menu {
                    Button("All data") { insightsWindowDays = 0 }
                    Button("7 days") { insightsWindowDays = 7 }
                    Button("30 days") { insightsWindowDays = 30 }
                    Button("90 days") { insightsWindowDays = 90 }
                } label: {
                    ScopeSelectionButton(
                        title: "Evaluation window",
                        value: windowLabel,
                        detail: "Choose how much ORIN history is summarized.",
                        systemImage: "calendar"
                    )
                }
                .buttonStyle(.plain)

                VStack(alignment: .leading, spacing: 10) {
                    Text("Patient scope")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(ClinicalCompassPalette.muted)
                        .textCase(.uppercase)

                    VStack(spacing: 10) {
                        ForEach(patientScopeOptions) { option in
                            PatientScopeButton(
                                title: option.title,
                                subtitle: option.subtitle,
                                isSelected: option.value == normalizedCanonicalPersonID
                            ) {
                                applyPatientScope(option)
                            }
                        }
                    }

                    Button {
                        showsManualPatientEntry.toggle()
                    } label: {
                        Label(
                            showsManualPatientEntry || hasManualPatientOverride ? "Hide manual patient ID" : "Enter a different patient ID",
                            systemImage: "pencil.line"
                        )
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(ClinicalCompassPalette.accent)
                    }
                    .buttonStyle(.plain)

                    if showsManualPatientEntry || hasManualPatientOverride {
                        TextField("Manual canonical_person_id", text: $insightsCanonicalPersonID)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .font(.footnote.monospaced())
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .background(
                                RoundedRectangle(cornerRadius: 16, style: .continuous)
                                    .fill(Color.white.opacity(0.92))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                                            .stroke(ClinicalCompassPalette.border.opacity(0.8), lineWidth: 1)
                                    )
                            )

                        Text("Only use a manual patient ID when you need a record other than this iPhone's local export identity.")
                            .font(.footnote)
                            .foregroundStyle(ClinicalCompassPalette.muted)
                    }

                    if let normalizedCanonicalPersonID {
                        Button {
                            patientAliasDraft = patientAliases[normalizedCanonicalPersonID] ?? ""
                            showsPatientAliasEditor = true
                        } label: {
                            Label(
                                patientAliases[normalizedCanonicalPersonID]?.isEmpty == false ? "Edit local patient label" : "Add local patient label",
                                systemImage: "person.crop.square.badge.plus"
                            )
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(ClinicalCompassPalette.accent)
                        }
                        .buttonStyle(.plain)

                        Text("Patient labels stay on this iPhone only. They are not exported or uploaded to ORIN.")
                            .font(.footnote)
                            .foregroundStyle(ClinicalCompassPalette.muted)
                    }
                }

                Text("Window and patient scope shape both ORIN refreshes and remote summaries.")
                    .font(.footnote)
                    .foregroundStyle(ClinicalCompassPalette.muted)
            }
        }
    }

    private var overviewCard: some View {
        CompassCard(highlighted: true) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(viewModel.clinicalOverviewTitle)
                            .font(.title2.weight(.semibold))
                            .fontDesign(.rounded)
                            .foregroundStyle(ClinicalCompassPalette.slate)
                        Text(viewModel.clinicalOverviewBody)
                            .font(.body)
                            .foregroundStyle(ClinicalCompassPalette.slate)
                    }
                    Spacer(minLength: 12)
                    Image(systemName: "cross.case")
                        .font(.title2.weight(.semibold))
                        .foregroundStyle(ClinicalCompassPalette.accent)
                }

                if let activeStatusLine = viewModel.activeStatusLine {
                    ProgressView(activeStatusLine)
                        .font(.footnote)
                        .tint(ClinicalCompassPalette.accent)
                }

                HStack(spacing: 12) {
                    StatusBadge(
                        title: "Coverage",
                        value: viewModel.coverageIndicatorLabel,
                        tint: ClinicalCompassPalette.accent
                    )
                    StatusBadge(
                        title: "Confidence",
                        value: viewModel.confidenceIndicatorLabel,
                        tint: viewModel.confidenceIndicatorLabel == "Review needed" ? ClinicalCompassPalette.caution : ClinicalCompassPalette.accent
                    )
                }

                if let message = viewModel.insightsStatusMessage {
                    Text(message)
                        .font(.footnote)
                        .foregroundStyle(ClinicalCompassPalette.muted)
                }
            }
        }
    }

    private var actionRow: some View {
        HStack(spacing: 10) {
            CompassActionButton(
                title: "Export",
                systemImage: "square.and.arrow.down",
                emphasized: true,
                isBusy: viewModel.isExporting
            ) {
                Task {
                    await exportNow()
                }
            }
            .disabled(viewModel.isExporting)

            CompassActionButton(
                title: "Sync to ORIN",
                systemImage: "arrow.triangle.2.circlepath.circle",
                emphasized: false,
                isBusy: viewModel.isUploading
            ) {
                Task {
                    await viewModel.uploadLatestRun(
                        baseURLString: uploadBaseURL,
                        bearerToken: uploadToken,
                        canonicalPersonID: normalizedCanonicalPersonID,
                        windowDays: normalizedWindowDays
                    )
                }
            }
            .disabled(viewModel.isUploading || viewModel.syncSnapshot == nil)

            CompassActionButton(
                title: "Refresh",
                systemImage: "waveform.path.ecg",
                emphasized: false,
                isBusy: viewModel.isFetchingInsights
            ) {
                Task {
                    await viewModel.refreshDashboard(
                        baseURLString: uploadBaseURL,
                        bearerToken: uploadToken,
                        canonicalPersonID: normalizedCanonicalPersonID,
                        windowDays: normalizedWindowDays
                    )
                }
            }
            .disabled(viewModel.isFetchingInsights)
        }
    }

    private var primaryTrendCard: some View {
        CompassCard {
            VStack(alignment: .leading, spacing: 14) {
                CompassSectionHeader(
                    eyebrow: "Primary Trend",
                    title: viewModel.primaryTrendTitle
                )

                TrendAccent()

                Text(viewModel.primaryTrendBody)
                    .font(.body)
                    .foregroundStyle(ClinicalCompassPalette.slate)
            }
        }
    }

    private var clinicalNotesCard: some View {
        CompassCard {
            VStack(alignment: .leading, spacing: 14) {
                CompassSectionHeader(
                    eyebrow: "Clinical Notes",
                    title: "What stands out"
                )

                if viewModel.clinicalNotes.isEmpty {
                    Text("A more detailed note will appear here after refreshes complete.")
                        .font(.body)
                        .foregroundStyle(ClinicalCompassPalette.muted)
                } else {
                    ForEach(viewModel.clinicalNotes.prefix(4), id: \.self) { note in
                        HStack(alignment: .top, spacing: 10) {
                            Circle()
                                .fill(ClinicalCompassPalette.accent)
                                .frame(width: 7, height: 7)
                                .padding(.top, 6)
                            Text(note)
                                .font(.body)
                                .foregroundStyle(ClinicalCompassPalette.slate)
                        }
                    }
                }
            }
        }
    }

    private var dataScopeCard: some View {
        CompassCard {
            VStack(alignment: .leading, spacing: 14) {
                CompassSectionHeader(
                    eyebrow: "Data Scope",
                    title: "Clinical context"
                )

                VStack(alignment: .leading, spacing: 10) {
                    LabeledValueRow(label: "Patient", value: patientScopeSummary)
                    LabeledValueRow(label: "Window", value: windowLabel)
                    LabeledValueRow(label: "Latest sync", value: viewModel.latestSyncLabel)
                    LabeledValueRow(label: "Anchors", value: viewModel.anchorStatusLabel)
                }

                if let snapshot = viewModel.syncSnapshot {
                    NavigationLink {
                        SyncDetailsView(snapshot: snapshot)
                    } label: {
                        HStack {
                            Text("View sync details")
                                .font(.subheadline.weight(.semibold))
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.footnote.weight(.semibold))
                        }
                        .foregroundStyle(ClinicalCompassPalette.accent)
                    }
                }
            }
        }
    }

    private var connectionStatusCard: some View {
        CompassCard {
            VStack(alignment: .leading, spacing: 14) {
                CompassSectionHeader(
                    eyebrow: "Connection",
                    title: "Operational settings"
                )

                Text(connectionSummary)
                    .font(.body)
                    .foregroundStyle(ClinicalCompassPalette.slate)

                Button {
                    showsConnectionSettings = true
                } label: {
                    Label("Connection settings", systemImage: "slider.horizontal.3")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(ClinicalCompassPalette.accent)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func attentionCard(message: String) -> some View {
        CompassCard {
            VStack(alignment: .leading, spacing: 10) {
                CompassSectionHeader(
                    eyebrow: "Needs attention",
                    title: "Please review"
                )
                Text(message)
                    .font(.body)
                    .foregroundStyle(ClinicalCompassPalette.caution)
            }
        }
    }

    private var normalizedCanonicalPersonID: String? {
        let trimmed = insightsCanonicalPersonID.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private var patientScopeOptions: [PatientScopeOption] {
        buildPatientScopeOptions(
            localCanonicalPersonID: localCanonicalPersonID,
            manualCanonicalPersonID: normalizedCanonicalPersonID,
            patientAliases: patientAliases
        )
    }

    private var hasManualPatientOverride: Bool {
        guard let normalizedCanonicalPersonID else {
            return false
        }
        return normalizedCanonicalPersonID != localCanonicalPersonID
    }

    private var normalizedWindowDays: Int? {
        insightsWindowDays > 0 ? insightsWindowDays : nil
    }

    private var windowLabel: String {
        normalizedWindowDays.map { "\($0) days" } ?? "All data"
    }

    private var patientScopeSummary: String {
        if let normalizedCanonicalPersonID {
            if let alias = patientAliases[normalizedCanonicalPersonID], !alias.isEmpty {
                return alias
            }
            if normalizedCanonicalPersonID == localCanonicalPersonID {
                return "This iPhone's record"
            }
            return "Manual patient"
        }
        return "All patients"
    }

    private func applyPatientScope(_ option: PatientScopeOption) {
        insightsCanonicalPersonID = option.value ?? ""
        showsManualPatientEntry = false
    }

    private func exportNow() async {
        await viewModel.exportNow()
        refreshLocalScopeMetadata()
    }

    private func refreshLocalScopeMetadata() {
        do {
            localCanonicalPersonID = try CanonicalPersonIDStore.defaultInAppSandbox().loadIfPresent()
        } catch {
            localCanonicalPersonID = nil
        }
        do {
            patientAliases = try PatientAliasStore.defaultInAppSandbox().loadAliases()
        } catch {
            patientAliases = [:]
        }
    }

    private func savePatientAlias() {
        guard let normalizedCanonicalPersonID else {
            return
        }
        do {
            try PatientAliasStore.defaultInAppSandbox().saveAlias(patientAliasDraft, for: normalizedCanonicalPersonID)
            refreshLocalScopeMetadata()
            showsPatientAliasEditor = false
        } catch {
            viewModel.errorMessage = "Unable to save the local patient label."
        }
    }

    private var connectionSummary: String {
        let hasURL = !uploadBaseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        let hasToken = !uploadToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        switch (hasURL, hasToken) {
        case (true, true):
            return "ORIN connection is configured. Main care actions stay on the dashboard; endpoint and token stay here."
        case (true, false), (false, true):
            return "Connection settings are incomplete. Finish the ORIN endpoint and token here before syncing remotely."
        case (false, false):
            return "Connection settings are optional until you want remote sync and ORIN-generated summaries."
        }
    }
}

struct PatientScopeOption: Identifiable, Equatable {
    let id: String
    let title: String
    let subtitle: String?
    let value: String?
}

func buildPatientScopeOptions(
    localCanonicalPersonID: String?,
    manualCanonicalPersonID: String?,
    patientAliases: [String: String]
) -> [PatientScopeOption] {
    var options: [PatientScopeOption] = [
        PatientScopeOption(
            id: "all-patients",
            title: "All patients",
            subtitle: "Use the full ORIN dataset in scope.",
            value: nil
        )
    ]

    if let localCanonicalPersonID, !localCanonicalPersonID.isEmpty {
        let localAlias = patientAliases[localCanonicalPersonID]
        options.append(
            PatientScopeOption(
                id: "local-patient",
                title: localAlias?.isEmpty == false ? localAlias! : "This iPhone's record",
                subtitle: localAlias?.isEmpty == false ? "Local-only label for this iPhone's record." : "Add a local patient label to make this easier to recognize.",
                value: localCanonicalPersonID
            )
        )
    }

    if let manualCanonicalPersonID, !manualCanonicalPersonID.isEmpty, manualCanonicalPersonID != localCanonicalPersonID {
        let manualAlias = patientAliases[manualCanonicalPersonID]
        options.append(
            PatientScopeOption(
                id: "manual-patient",
                title: manualAlias?.isEmpty == false ? manualAlias! : "Manual patient selection",
                subtitle: manualAlias?.isEmpty == false ? "Local-only label for the selected ORIN patient." : "A specific ORIN patient is selected with a manual canonical ID.",
                value: manualCanonicalPersonID
            )
        )
    }

    return options
}

private struct PatientAliasSheet: View {
    let canonicalPersonID: String?
    @Binding var aliasDraft: String
    let onSave: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Local patient label") {
                    TextField("For example: Me, Dad, Primary record", text: $aliasDraft)
                        .textInputAutocapitalization(.words)
                        .autocorrectionDisabled()

                    Text("This label stays on this iPhone only and is never exported or uploaded.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Current patient") {
                    Text(canonicalPersonID ?? "No patient selected")
                        .font(.footnote.monospaced())
                        .textSelection(.enabled)
                }
            }
            .navigationTitle("Patient Label")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Save") {
                        onSave()
                    }
                }
            }
        }
    }
}

private struct ConnectionSettingsSheet: View {
    @Binding var uploadBaseURL: String
    @Binding var uploadToken: String
    let uploadStatusMessage: String?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("ORIN connection") {
                    TextField("Upload endpoint", text: $uploadBaseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)

                    SecureField("Upload token", text: $uploadToken)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section("Status") {
                    Text(uploadStatusMessage ?? "Remote uploads use these settings, but the main care view keeps them out of the primary experience.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Connection Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

private struct CompassCard<Content: View>: View {
    let highlighted: Bool
    @ViewBuilder var content: Content

    init(highlighted: Bool = false, @ViewBuilder content: () -> Content) {
        self.highlighted = highlighted
        self.content = content()
    }

    var body: some View {
        content
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .fill(highlighted ? ClinicalCompassPalette.card : ClinicalCompassPalette.card.opacity(0.92))
                    .overlay(
                        RoundedRectangle(cornerRadius: 24, style: .continuous)
                            .stroke(highlighted ? ClinicalCompassPalette.accentSoft : ClinicalCompassPalette.border.opacity(0.9), lineWidth: 1)
                    )
            )
            .shadow(color: ClinicalCompassPalette.accent.opacity(0.06), radius: 18, x: 0, y: 10)
    }
}

private struct CompassSectionHeader: View {
    let eyebrow: String
    let title: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(eyebrow)
                .font(.caption.weight(.semibold))
                .foregroundStyle(ClinicalCompassPalette.accent)
                .textCase(.uppercase)
            Text(title)
                .font(.headline)
                .foregroundStyle(ClinicalCompassPalette.slate)
        }
    }
}

private struct ScopeSelectionButton: View {
    let title: String
    let value: String
    let detail: String
    let systemImage: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: systemImage)
                .font(.headline)
                .foregroundStyle(ClinicalCompassPalette.accent)
                .frame(width: 20, height: 20)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(ClinicalCompassPalette.muted)
                    .textCase(.uppercase)
                Text(value)
                    .font(.headline)
                    .foregroundStyle(ClinicalCompassPalette.slate)
                Text(detail)
                    .font(.footnote)
                    .foregroundStyle(ClinicalCompassPalette.muted)
            }
            Spacer(minLength: 12)
            Image(systemName: "chevron.down")
                .font(.caption.weight(.semibold))
                .foregroundStyle(ClinicalCompassPalette.muted)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.white.opacity(0.92))
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .stroke(ClinicalCompassPalette.border.opacity(0.8), lineWidth: 1)
                )
        )
    }
}

private struct PatientScopeButton: View {
    let title: String
    let subtitle: String?
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.headline)
                    .foregroundStyle(isSelected ? ClinicalCompassPalette.accent : ClinicalCompassPalette.border)
                    .padding(.top, 2)

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(ClinicalCompassPalette.slate)

                    if let subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(title == "This iPhone's record" || title == "Manual patient selection" ? .footnote.monospaced() : .footnote)
                            .foregroundStyle(ClinicalCompassPalette.muted)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                    }
                }

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(isSelected ? ClinicalCompassPalette.accentSoft.opacity(0.45) : Color.white.opacity(0.92))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .stroke(isSelected ? ClinicalCompassPalette.accent.opacity(0.45) : ClinicalCompassPalette.border.opacity(0.8), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
    }
}

private struct StatusBadge: View {
    let title: String
    let value: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(ClinicalCompassPalette.muted)
            Text(value)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(ClinicalCompassPalette.slate)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(tint.opacity(0.10))
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .stroke(tint.opacity(0.28), lineWidth: 1)
                )
        )
    }
}

private struct CompassActionButton: View {
    let title: String
    let systemImage: String
    let emphasized: Bool
    let isBusy: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                if isBusy {
                    ProgressView()
                        .tint(emphasized ? .white : ClinicalCompassPalette.accent)
                } else {
                    Image(systemName: systemImage)
                        .font(.headline)
                }
                Text(title)
                    .font(.footnote.weight(.semibold))
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
            }
            .foregroundStyle(emphasized ? Color.white : ClinicalCompassPalette.accent)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(emphasized ? ClinicalCompassPalette.accent : Color.white.opacity(0.9))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(ClinicalCompassPalette.border.opacity(emphasized ? 0 : 0.85), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
    }
}

private struct TrendAccent: View {
    var body: some View {
        HStack(alignment: .bottom, spacing: 6) {
            ForEach([0.32, 0.48, 0.42, 0.63, 0.56, 0.74, 0.68], id: \.self) { height in
                Capsule()
                    .fill(ClinicalCompassPalette.accent.opacity(0.18))
                    .frame(maxWidth: .infinity)
                    .frame(height: 60 * height)
            }
        }
        .frame(height: 64)
    }
}

private struct LabeledValueRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(ClinicalCompassPalette.muted)
            Spacer(minLength: 12)
            Text(value)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(ClinicalCompassPalette.slate)
                .multilineTextAlignment(.trailing)
        }
    }
}

private struct SyncDetailsView: View {
    let snapshot: SyncStatusSnapshot

    var body: some View {
        List {
            Section("Run") {
                LabeledContent("Run ID", value: snapshot.runID)
                LabeledContent("Generated", value: snapshot.lastSyncLabel)
                LabeledContent("Source files", value: "\(snapshot.fileCount)")
                LabeledContent("Rows", value: snapshot.totalRowsLabel)
                LabeledContent("Bytes", value: snapshot.totalBytesLabel)
                LabeledContent("Anchors", value: "\(snapshot.anchorFiles)")
            }

            Section("Row Counts") {
                if snapshot.rowCounts.isEmpty {
                    Text("No row counts found in manifest.")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(snapshot.rowCounts.keys.sorted(), id: \.self) { key in
                        LabeledContent(key, value: "\(snapshot.rowCounts[key] ?? 0)")
                    }
                }
            }

            Section("Source Paths") {
                if snapshot.sourceFiles.isEmpty {
                    Text("No source file entries in manifest.")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(snapshot.sourceFiles, id: \.self) { path in
                        Text(path)
                            .font(.footnote.monospaced())
                    }
                }
            }
        }
        .navigationTitle("Sync Details")
    }
}

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published var syncSnapshot: SyncStatusSnapshot?
    @Published var insightCards: [InsightCard] = []
    @Published var errorMessage: String?
    @Published var isExporting = false
    @Published var isUploading = false
    @Published var isFetchingInsights = false
    @Published var uploadStatusMessage: String?
    @Published var insightsStatusMessage: String?

    var exportProgressLabel: String? {
        isExporting ? "Exporting HealthKit data..." : nil
    }

    var uploadProgressLabel: String? {
        isUploading ? "Uploading latest run to ORIN..." : nil
    }

    var insightsProgressLabel: String? {
        isFetchingInsights ? "Fetching insights from ORIN..." : nil
    }

    var activeStatusLine: String? {
        exportProgressLabel ?? uploadProgressLabel ?? insightsProgressLabel ?? uploadStatusMessage
    }

    var clinicalOverviewTitle: String {
        if errorMessage != nil {
            return "Needs attention"
        }
        if isExporting {
            return "Creating a fresh export"
        }
        if isUploading {
            return "Syncing to ORIN"
        }
        if isFetchingInsights {
            return "Refreshing your care view"
        }
        if !insightCards.isEmpty {
            return "Overview"
        }
        if syncSnapshot != nil {
            return "Your record is ready"
        }
        return "Ready for your first export"
    }

    var clinicalOverviewBody: String {
        if let errorMessage {
            return errorMessage
        }
        if isExporting {
            return "HealthDelta is preparing a new on-device export so the care view can refresh with the latest observations."
        }
        if isUploading {
            return "Your newest local run is moving to ORIN so the dashboard can shift from device status to longitudinal interpretation."
        }
        if isFetchingInsights {
            return "ORIN is refreshing the current care summary using the selected patient and evaluation window."
        }
        if let card = insightCards.first {
            return conciseBody(card.body)
        }
        if syncSnapshot != nil {
            return "A local record is available. Use Refresh to pull a fuller ORIN summary, or Export to capture a new bedside-ready snapshot."
        }
        return "Start with Export Now to create your first local health record. Once ORIN is connected, this screen will shift from setup to clinical guidance."
    }

    var coverageIndicatorLabel: String {
        guard let syncSnapshot, syncSnapshot.totalRows > 0 else {
            return "No data"
        }
        if syncSnapshot.totalRows >= 50_000 {
            return "Longitudinal"
        }
        if syncSnapshot.totalRows >= 1_000 {
            return "Observed"
        }
        return "Limited"
    }

    var confidenceIndicatorLabel: String {
        if errorMessage != nil {
            return "Review needed"
        }
        guard let syncSnapshot, syncSnapshot.totalRows > 0 else {
            return "Unavailable"
        }
        if insightCards.isEmpty {
            return "Developing"
        }
        if syncSnapshot.totalRows >= 50_000 {
            return "Moderate"
        }
        return "Developing"
    }

    var primaryTrendTitle: String {
        insightCards.first?.title ?? "Primary trend"
    }

    var primaryTrendBody: String {
        if let card = insightCards.first {
            return conciseBody(card.body)
        }
        if syncSnapshot != nil {
            return "A fuller trend summary appears after ORIN refreshes the current scope."
        }
        return "No longitudinal trend is available yet."
    }

    var clinicalNotes: [String] {
        var notes: [String] = []
        if isObservationOnlyRecord {
            notes.append("Current record is activity-led.")
        }
        if let second = insightCards.dropFirst().first {
            notes.append(contentsOf: noteLines(from: second.body))
        } else if let first = insightCards.first {
            notes.append(contentsOf: noteLines(from: first.body).dropFirst())
        }
        if let syncSnapshot, syncSnapshot.anchorFiles > 0 {
            notes.append("Incremental anchors are active for on-device continuation.")
        }
        if insightCards.isEmpty, let insightsStatusMessage, !insightsStatusMessage.isEmpty {
            notes.append(insightsStatusMessage)
        }
        return deduped(notes).prefix(4).map { $0 }
    }

    var latestSyncLabel: String {
        syncSnapshot?.lastSyncLabel ?? "Not available yet"
    }

    var anchorStatusLabel: String {
        syncSnapshot?.anchorStatusLabel ?? "No anchors saved yet"
    }

    private var isObservationOnlyRecord: Bool {
        guard let syncSnapshot else {
            return false
        }
        return Set(syncSnapshot.rowCounts.keys) == ["observations"]
    }

    private let syncStore: SyncStatusLoading
    private let insightsStore: InsightsLoading
    private let manualExporter: ManualHealthExporting
    private let runUploader: RunUploading
    private let insightsFetcher: ORINInsightsFetching

    init(
        syncStore: SyncStatusLoading = SyncStatusStore(),
        insightsStore: InsightsLoading = InsightsStore(),
        manualExporter: ManualHealthExporting = ManualHealthExportService.live(),
        runUploader: RunUploading = ORINUploadService.live(),
        insightsFetcher: ORINInsightsFetching = ORINInsightsService.live()
    ) {
        self.syncStore = syncStore
        self.insightsStore = insightsStore
        self.manualExporter = manualExporter
        self.runUploader = runUploader
        self.insightsFetcher = insightsFetcher
    }

    func refresh() {
        do {
            syncSnapshot = try syncStore.loadLatest()
            insightCards = try insightsStore.loadLatestCards()
            insightsStatusMessage = insightCards.isEmpty ? nil : "Showing local insight artifacts."
            errorMessage = nil
        } catch SyncStatusStore.LoadError.noRunDirectory {
            syncSnapshot = nil
            insightCards = []
            insightsStatusMessage = nil
            errorMessage = nil
        } catch {
            syncSnapshot = nil
            insightCards = []
            insightsStatusMessage = nil
            errorMessage = "Unable to load local run data. \(error.localizedDescription)"
        }
    }

    func refreshDashboard(
        baseURLString: String,
        bearerToken: String,
        canonicalPersonID: String? = nil,
        windowDays: Int? = nil
    ) async {
        refresh()
        guard !baseURLString.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        guard !bearerToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        await fetchORINInsights(
            baseURLString: baseURLString,
            bearerToken: bearerToken,
            canonicalPersonID: canonicalPersonID,
            windowDays: windowDays
        )
    }

    func exportNow() async {
        isExporting = true
        defer { isExporting = false }

        do {
            _ = try await manualExporter.runManualExport()
            uploadStatusMessage = nil
            refresh()
        } catch {
            errorMessage = "Unable to export HealthKit data. \(error.localizedDescription)"
        }
    }

    func uploadLatestRun(
        baseURLString: String,
        bearerToken: String,
        canonicalPersonID: String? = nil,
        windowDays: Int? = nil
    ) async {
        let snapshot: SyncStatusSnapshot
        do {
            snapshot = try syncStore.loadLatest()
            syncSnapshot = snapshot
        } catch SyncStatusStore.LoadError.noRunDirectory {
            print("HealthDelta upload skipped: no completed local run is available")
            errorMessage = "Unable to upload run to ORIN. No completed local run is available to upload yet."
            return
        } catch {
            print("HealthDelta upload skipped: unable to reload latest run \(error.localizedDescription)")
            errorMessage = "Unable to upload run to ORIN. \(error.localizedDescription)"
            return
        }

        isUploading = true
        defer { isUploading = false }

        do {
            print("HealthDelta upload starting for run \(snapshot.runID)")
            let dataset = try await runUploader.uploadRun(
                runID: snapshot.runID,
                baseURLString: baseURLString,
                bearerToken: bearerToken
            )
            print("HealthDelta upload succeeded with dataset \(dataset)")
            uploadStatusMessage = "Uploaded \(snapshot.runID) to ORIN dataset \(dataset)."
            errorMessage = nil
            await fetchORINInsights(
                baseURLString: baseURLString,
                bearerToken: bearerToken,
                canonicalPersonID: canonicalPersonID,
                windowDays: windowDays
            )
        } catch {
            print("HealthDelta upload failed: \(error.localizedDescription)")
            uploadStatusMessage = nil
            errorMessage = "Unable to upload run to ORIN. \(error.localizedDescription)"
        }
    }

    func fetchORINInsights(
        baseURLString: String,
        bearerToken: String,
        canonicalPersonID: String? = nil,
        windowDays: Int? = nil
    ) async {
        isFetchingInsights = true
        defer { isFetchingInsights = false }

        do {
            let result = try await insightsFetcher.fetchCurrentInsights(
                baseURLString: baseURLString,
                bearerToken: bearerToken,
                canonicalPersonID: canonicalPersonID,
                windowDays: windowDays
            )
            switch result {
            case .cards(let cards):
                insightCards = cards
                insightsStatusMessage = cards.isEmpty ? "ORIN returned no insight cards." : "Showing ORIN-generated insights."
                errorMessage = nil
            case .noInsightsYet(let detail):
                if insightCards.isEmpty {
                    insightCards = []
                }
                insightsStatusMessage = detail
                errorMessage = nil
            }
        } catch {
            if insightCards.isEmpty {
                insightsStatusMessage = nil
            }
            errorMessage = "Unable to fetch ORIN insights. \(error.localizedDescription)"
        }
    }

    private func conciseBody(_ text: String) -> String {
        let lines = noteLines(from: text)
        if lines.isEmpty {
            return text.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return lines.prefix(2).joined(separator: " ")
    }

    private func noteLines(from text: String) -> [String] {
        text
            .components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private func deduped(_ values: [String]) -> [String] {
        var seen: Set<String> = []
        var out: [String] = []
        for value in values {
            if seen.insert(value).inserted {
                out.append(value)
            }
        }
        return out
    }
}
