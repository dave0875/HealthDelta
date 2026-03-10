import XCTest

@testable import HealthDelta

@MainActor
final class DashboardViewModelTests: XCTestCase {
    func testExportNowRefreshesDashboardOnSuccess() async throws {
        let expectedSnapshot = SyncStatusSnapshot(
            runID: "run_test",
            generatedAt: Date(timeIntervalSince1970: 1_700_000_000),
            deltaStart: nil,
            deltaEnd: nil,
            totalRows: 3,
            totalBytes: 128,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: ["observations": 3],
            sourceFiles: ["ndjson/observations.ndjson"]
        )
        let expectedCards = [
            InsightCard(
                id: "run_test-note",
                title: "Doctor's Note",
                body: "Body",
                disclaimer: "For education only. This is not medical advice.",
                sourceLabel: "note/doctor_note.md",
                freshnessLabel: "Updated now UTC"
            )
        ]
        let syncStore = FakeSyncStatusStore(snapshot: expectedSnapshot)
        let insightsStore = FakeInsightsStore(cards: expectedCards)
        let exporter = FakeManualExporter()
        let viewModel = DashboardViewModel(
            syncStore: syncStore,
            insightsStore: insightsStore,
            manualExporter: exporter
        )

        await viewModel.exportNow()

        XCTAssertEqual(exporter.callCount, 1)
        XCTAssertEqual(viewModel.syncSnapshot, expectedSnapshot)
        XCTAssertEqual(viewModel.insightCards, expectedCards)
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isExporting)
    }

    func testExportNowSurfacesFailure() async throws {
        let syncStore = FakeSyncStatusStore(snapshot: nil)
        let insightsStore = FakeInsightsStore(cards: [])
        let exporter = FakeManualExporter(error: ManualHealthExportError.authorizationDenied)
        let viewModel = DashboardViewModel(
            syncStore: syncStore,
            insightsStore: insightsStore,
            manualExporter: exporter
        )

        await viewModel.exportNow()

        XCTAssertEqual(exporter.callCount, 1)
        XCTAssertNil(viewModel.syncSnapshot)
        XCTAssertTrue(viewModel.errorMessage?.contains("Health access was denied") == true)
        XCTAssertFalse(viewModel.isExporting)
    }
}

private final class FakeSyncStatusStore: SyncStatusLoading {
    let snapshot: SyncStatusSnapshot?

    init(snapshot: SyncStatusSnapshot?) {
        self.snapshot = snapshot
    }

    func loadLatest() throws -> SyncStatusSnapshot {
        guard let snapshot else {
            throw SyncStatusStore.LoadError.noRunDirectory
        }
        return snapshot
    }
}

private final class FakeInsightsStore: InsightsLoading {
    let cards: [InsightCard]

    init(cards: [InsightCard]) {
        self.cards = cards
    }

    func loadLatestCards() throws -> [InsightCard] {
        cards
    }
}

private final class FakeManualExporter: ManualHealthExporting {
    let error: Error?
    private(set) var callCount = 0

    init(error: Error? = nil) {
        self.error = error
    }

    func runManualExport() async throws -> String {
        callCount += 1
        if let error {
            throw error
        }
        return "run_test"
    }
}
