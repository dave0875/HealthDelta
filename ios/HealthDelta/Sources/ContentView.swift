import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = DashboardViewModel()
    @AppStorage("orinUploadBaseURL") private var uploadBaseURL = ""
    @AppStorage("orinUploadToken") private var uploadToken = ""
    @State private var didRunLaunchAutomation = false

    var body: some View {
        NavigationStack {
            List {
                Section("Sync Status") {
                    Button(viewModel.isExporting ? "Exporting..." : "Export Now") {
                        Task {
                            await viewModel.exportNow()
                        }
                    }
                    .disabled(viewModel.isExporting)

                    if let exportProgressLabel = viewModel.exportProgressLabel {
                        ProgressView(exportProgressLabel)
                            .font(.footnote)
                    }

                    if let sync = viewModel.syncSnapshot {
                        LabeledContent("Last sync", value: sync.lastSyncLabel + " UTC")
                        LabeledContent("Last delta window", value: sync.lastDeltaLabel + (sync.deltaStart == nil ? "" : " UTC"))
                        LabeledContent("Rows exported", value: sync.totalRowsLabel)
                        LabeledContent("Bytes exported", value: sync.totalBytesLabel)
                        LabeledContent("Anchor status", value: sync.anchorStatusLabel)
                        NavigationLink("View sync details") {
                            SyncDetailsView(snapshot: sync)
                        }
                    } else {
                        Text("No sync data yet.")
                            .font(.headline)
                        Text("Run an iOS export first. Then pull outputs into the operator pipeline to unlock insights.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("ORIN Upload") {
                    TextField("Upload endpoint", text: $uploadBaseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    SecureField("Upload token", text: $uploadToken)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                    Button(viewModel.isUploading ? "Uploading..." : "Upload Latest Run") {
                        Task {
                            await viewModel.uploadLatestRun(baseURLString: uploadBaseURL, bearerToken: uploadToken)
                        }
                    }
                    .disabled(viewModel.isUploading || viewModel.syncSnapshot == nil)

                    if let uploadProgressLabel = viewModel.uploadProgressLabel {
                        ProgressView(uploadProgressLabel)
                            .font(.footnote)
                    }

                    if let uploadStatusMessage = viewModel.uploadStatusMessage {
                        Text(uploadStatusMessage)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("Uploads the newest local run directly to ORIN using the resumable upload-session API.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Insights") {
                    Button(viewModel.isFetchingInsights ? "Fetching..." : "Fetch from ORIN") {
                        Task {
                            await viewModel.fetchORINInsights(
                                baseURLString: uploadBaseURL,
                                bearerToken: uploadToken
                            )
                        }
                    }
                    .disabled(viewModel.isFetchingInsights)

                    if let insightsProgressLabel = viewModel.insightsProgressLabel {
                        ProgressView(insightsProgressLabel)
                            .font(.footnote)
                    }

                    if viewModel.insightCards.isEmpty {
                        Text("No insights available yet.")
                            .font(.headline)
                        Text(viewModel.insightsStatusMessage ?? "After your first completed run, this screen will show Doctor's Note and summary cards with freshness details.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(viewModel.insightCards) { card in
                            InsightCardView(card: card)
                        }
                    }
                }

                if let errorMessage = viewModel.errorMessage {
                    Section("Needs attention") {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("HealthDelta")
            .toolbar {
                Button("Refresh") {
                    Task {
                        await viewModel.refreshDashboard(
                            baseURLString: uploadBaseURL,
                            bearerToken: uploadToken
                        )
                    }
                }
            }
            .task {
                guard !didRunLaunchAutomation else {
                    return
                }
                didRunLaunchAutomation = true
                await viewModel.refreshDashboard(
                    baseURLString: uploadBaseURL,
                    bearerToken: uploadToken
                )
                if let config = LaunchAutomation.autoUploadConfig() {
                    print("HealthDelta auto-upload launch hook active for \(config.baseURLString)")
                    await viewModel.uploadLatestRun(
                        baseURLString: config.baseURLString,
                        bearerToken: config.bearerToken
                    )
                }
            }
        }
    }
}

private struct SyncDetailsView: View {
    let snapshot: SyncStatusSnapshot

    var body: some View {
        List {
            Section("Run") {
                LabeledContent("Run ID", value: snapshot.runID)
                LabeledContent("Generated", value: snapshot.lastSyncLabel + " UTC")
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

private struct InsightCardView: View {
    let card: InsightCard

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(card.title)
                .font(.headline)
            Text(card.freshnessLabel)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(card.body)
                .font(.body)
                .lineLimit(8)
            Text(card.disclaimer)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text("Source: \(card.sourceLabel)")
                .font(.caption2.monospaced())
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
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

    func refreshDashboard(baseURLString: String, bearerToken: String) async {
        refresh()
        guard !baseURLString.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        guard !bearerToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        await fetchORINInsights(baseURLString: baseURLString, bearerToken: bearerToken)
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

    func uploadLatestRun(baseURLString: String, bearerToken: String) async {
        guard let snapshot = syncSnapshot else {
            print("HealthDelta upload skipped: no completed local run is available")
            errorMessage = "Unable to upload run to ORIN. No completed local run is available to upload yet."
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
            await fetchORINInsights(baseURLString: baseURLString, bearerToken: bearerToken)
        } catch {
            print("HealthDelta upload failed: \(error.localizedDescription)")
            uploadStatusMessage = nil
            errorMessage = "Unable to upload run to ORIN. \(error.localizedDescription)"
        }
    }

    func fetchORINInsights(baseURLString: String, bearerToken: String) async {
        isFetchingInsights = true
        defer { isFetchingInsights = false }

        do {
            let result = try await insightsFetcher.fetchCurrentInsights(
                baseURLString: baseURLString,
                bearerToken: bearerToken
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
}
