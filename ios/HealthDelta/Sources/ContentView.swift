import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = DashboardViewModel()

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

                Section("Insights") {
                    if viewModel.insightCards.isEmpty {
                        Text("No insights available yet.")
                            .font(.headline)
                        Text("After your first completed run, this screen will show Doctor's Note and summary cards with freshness details.")
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
                    viewModel.refresh()
                }
            }
            .task {
                viewModel.refresh()
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

    private let syncStore: SyncStatusLoading
    private let insightsStore: InsightsLoading
    private let manualExporter: ManualHealthExporting

    init(
        syncStore: SyncStatusLoading = SyncStatusStore(),
        insightsStore: InsightsLoading = InsightsStore(),
        manualExporter: ManualHealthExporting = ManualHealthExportService.live()
    ) {
        self.syncStore = syncStore
        self.insightsStore = insightsStore
        self.manualExporter = manualExporter
    }

    func refresh() {
        do {
            syncSnapshot = try syncStore.loadLatest()
            insightCards = try insightsStore.loadLatestCards()
            errorMessage = nil
        } catch SyncStatusStore.LoadError.noRunDirectory {
            syncSnapshot = nil
            insightCards = []
            errorMessage = nil
        } catch {
            syncSnapshot = nil
            insightCards = []
            errorMessage = "Unable to load local run data. \(error.localizedDescription)"
        }
    }

    func exportNow() async {
        isExporting = true
        defer { isExporting = false }

        do {
            _ = try await manualExporter.runManualExport()
            refresh()
        } catch {
            errorMessage = "Unable to export HealthKit data. \(error.localizedDescription)"
        }
    }
}
