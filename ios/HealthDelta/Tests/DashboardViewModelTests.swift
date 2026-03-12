import XCTest

@testable import HealthDelta

@MainActor
final class DashboardViewModelTests: XCTestCase {
    func testBuildPatientScopeOptionsIncludesLocalAndManualChoices() {
        let options = buildPatientScopeOptions(
            localCanonicalPersonID: "local-person",
            manualCanonicalPersonID: "manual-person"
        )

        XCTAssertEqual(options.map(\.title), [
            "All patients",
            "This iPhone's record",
            "Manual patient selection",
        ])
        XCTAssertEqual(options[1].subtitle, "local-person")
        XCTAssertEqual(options[2].subtitle, "manual-person")
    }

    func testBuildPatientScopeOptionsSkipsDuplicateManualChoice() {
        let options = buildPatientScopeOptions(
            localCanonicalPersonID: "local-person",
            manualCanonicalPersonID: "local-person"
        )

        XCTAssertEqual(options.map(\.title), [
            "All patients",
            "This iPhone's record",
        ])
    }

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
        let uploader = FakeRunUploader()
        let viewModel = DashboardViewModel(
            syncStore: syncStore,
            insightsStore: insightsStore,
            manualExporter: exporter,
            runUploader: uploader,
            insightsFetcher: FakeInsightsFetcher()
        )

        await viewModel.exportNow()

        XCTAssertEqual(exporter.callCount, 1)
        XCTAssertEqual(viewModel.syncSnapshot, expectedSnapshot)
        XCTAssertEqual(viewModel.insightCards, expectedCards)
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isExporting)
        XCTAssertNil(viewModel.exportProgressLabel)
    }

    func testExportNowSurfacesFailure() async throws {
        let syncStore = FakeSyncStatusStore(snapshot: nil)
        let insightsStore = FakeInsightsStore(cards: [])
        let exporter = FakeManualExporter(error: ManualHealthExportError.authorizationDenied)
        let uploader = FakeRunUploader()
        let viewModel = DashboardViewModel(
            syncStore: syncStore,
            insightsStore: insightsStore,
            manualExporter: exporter,
            runUploader: uploader,
            insightsFetcher: FakeInsightsFetcher()
        )

        await viewModel.exportNow()

        XCTAssertEqual(exporter.callCount, 1)
        XCTAssertNil(viewModel.syncSnapshot)
        XCTAssertTrue(viewModel.errorMessage?.contains("Health access was denied") == true)
        XCTAssertFalse(viewModel.isExporting)
        XCTAssertNil(viewModel.exportProgressLabel)
    }

    func testExportNowExposesInProgressIndicatorWhileRunning() async throws {
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
        let gate = AsyncGate()
        let exporter = FakeManualExporter(gate: gate)
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: expectedSnapshot),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: exporter,
            runUploader: FakeRunUploader(),
            insightsFetcher: FakeInsightsFetcher()
        )

        let task = Task {
            await viewModel.exportNow()
        }
        await gate.waitUntilBlocked()

        XCTAssertTrue(viewModel.isExporting)
        XCTAssertEqual(viewModel.exportProgressLabel, "Exporting HealthKit data...")

        await gate.resume()
        await task.value

        XCTAssertFalse(viewModel.isExporting)
        XCTAssertNil(viewModel.exportProgressLabel)
    }

    func testUploadLatestRunSurfacesSuccessStatus() async throws {
        let snapshot = SyncStatusSnapshot(
            runID: "run_upload",
            generatedAt: Date(timeIntervalSince1970: 1_700_000_000),
            deltaStart: nil,
            deltaEnd: nil,
            totalRows: 2,
            totalBytes: 64,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: ["observations": 2],
            sourceFiles: ["ndjson/observations.ndjson"]
        )
        let uploader = FakeRunUploader(dataset: "dataset_test")
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: snapshot),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: uploader,
            insightsFetcher: FakeInsightsFetcher()
        )

        viewModel.refresh()
        await viewModel.uploadLatestRun(baseURLString: "http://orin.local:8080", bearerToken: "token")

        XCTAssertEqual(uploader.callCount, 1)
        XCTAssertEqual(uploader.lastRunID, "run_upload")
        XCTAssertEqual(viewModel.uploadStatusMessage, "Uploaded run_upload to ORIN dataset dataset_test.")
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isUploading)
        XCTAssertNil(viewModel.uploadProgressLabel)
    }

    func testUploadLatestRunReloadsSyncSnapshotBeforeUploading() async throws {
        let staleSnapshot = SyncStatusSnapshot(
            runID: "run_stale",
            generatedAt: Date(timeIntervalSince1970: 1_700_000_000),
            deltaStart: nil,
            deltaEnd: nil,
            totalRows: 1,
            totalBytes: 32,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: ["observations": 1],
            sourceFiles: ["ndjson/observations.ndjson"]
        )
        let freshSnapshot = SyncStatusSnapshot(
            runID: "run_fresh",
            generatedAt: Date(timeIntervalSince1970: 1_700_000_100),
            deltaStart: nil,
            deltaEnd: nil,
            totalRows: 5,
            totalBytes: 128,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: ["observations": 5],
            sourceFiles: ["ndjson/observations.ndjson"]
        )
        let syncStore = FakeSyncStatusStore(snapshots: [staleSnapshot, freshSnapshot])
        let uploader = FakeRunUploader(dataset: "dataset_test")
        let viewModel = DashboardViewModel(
            syncStore: syncStore,
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: uploader,
            insightsFetcher: FakeInsightsFetcher()
        )

        viewModel.refresh()
        XCTAssertEqual(viewModel.syncSnapshot?.runID, "run_stale")

        await viewModel.uploadLatestRun(baseURLString: "http://orin.local:8080", bearerToken: "token")

        XCTAssertEqual(uploader.lastRunID, "run_fresh")
        XCTAssertEqual(viewModel.syncSnapshot?.runID, "run_fresh")
    }

    func testUploadLatestRunSurfacesFailure() async throws {
        let snapshot = SyncStatusSnapshot(
            runID: "run_upload",
            generatedAt: Date(timeIntervalSince1970: 1_700_000_000),
            deltaStart: nil,
            deltaEnd: nil,
            totalRows: 2,
            totalBytes: 64,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: ["observations": 2],
            sourceFiles: ["ndjson/observations.ndjson"]
        )
        let uploader = FakeRunUploader(error: RunUploadError.missingToken)
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: snapshot),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: uploader,
            insightsFetcher: FakeInsightsFetcher()
        )

        viewModel.refresh()
        await viewModel.uploadLatestRun(baseURLString: "http://orin.local:8080", bearerToken: "")

        XCTAssertEqual(uploader.callCount, 1)
        XCTAssertTrue(viewModel.errorMessage?.contains("Enter the ORIN upload token") == true)
        XCTAssertNil(viewModel.uploadStatusMessage)
        XCTAssertFalse(viewModel.isUploading)
        XCTAssertNil(viewModel.uploadProgressLabel)
    }

    func testUploadLatestRunExposesInProgressIndicatorWhileRunning() async throws {
        let snapshot = SyncStatusSnapshot(
            runID: "run_upload",
            generatedAt: Date(timeIntervalSince1970: 1_700_000_000),
            deltaStart: nil,
            deltaEnd: nil,
            totalRows: 2,
            totalBytes: 64,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: ["observations": 2],
            sourceFiles: ["ndjson/observations.ndjson"]
        )
        let gate = AsyncGate()
        let uploader = FakeRunUploader(gate: gate)
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: snapshot),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: uploader,
            insightsFetcher: FakeInsightsFetcher()
        )

        viewModel.refresh()

        let task = Task {
            await viewModel.uploadLatestRun(baseURLString: "http://orin.local:8080", bearerToken: "token")
        }
        await gate.waitUntilBlocked()

        XCTAssertTrue(viewModel.isUploading)
        XCTAssertEqual(viewModel.uploadProgressLabel, "Uploading latest run to ORIN...")

        await gate.resume()
        await task.value

        XCTAssertFalse(viewModel.isUploading)
        XCTAssertNil(viewModel.uploadProgressLabel)
    }

    func testFetchORINInsightsLoadsCardsOnSuccess() async throws {
        let cards = [
            InsightCard(
                id: "orin-1",
                title: "ORIN Overview",
                body: "Body",
                disclaimer: "For education only. This is not medical advice.",
                sourceLabel: "orin/datasets/current",
                freshnessLabel: "Updated now"
            )
        ]
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: nil),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: FakeRunUploader(),
            insightsFetcher: FakeInsightsFetcher(result: .cards(cards))
        )

        await viewModel.fetchORINInsights(baseURLString: "http://orin.local:8080", bearerToken: "token")

        XCTAssertEqual(viewModel.insightCards, cards)
        XCTAssertEqual(viewModel.insightsStatusMessage, "Showing ORIN-generated insights.")
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isFetchingInsights)
        XCTAssertNil(viewModel.insightsProgressLabel)
    }

    func testFetchORINInsightsPassesSelectedFilters() async throws {
        let fetcher = FakeInsightsFetcher(result: .cards([]))
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: nil),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: FakeRunUploader(),
            insightsFetcher: fetcher
        )

        await viewModel.fetchORINInsights(
            baseURLString: "http://orin.local:8080",
            bearerToken: "token",
            canonicalPersonID: "person-123",
            windowDays: 30
        )

        XCTAssertEqual(fetcher.lastCanonicalPersonID, "person-123")
        XCTAssertEqual(fetcher.lastWindowDays, 30)
    }

    func testFetchORINInsightsShowsNoInsightsYetState() async throws {
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: nil),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: FakeRunUploader(),
            insightsFetcher: FakeInsightsFetcher(result: .noInsightsYet("Upload a run first."))
        )

        await viewModel.fetchORINInsights(baseURLString: "http://orin.local:8080", bearerToken: "token")

        XCTAssertEqual(viewModel.insightCards, [])
        XCTAssertEqual(viewModel.insightsStatusMessage, "Upload a run first.")
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertFalse(viewModel.isFetchingInsights)
    }

    func testFetchORINInsightsSurfacesFailure() async throws {
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: nil),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: FakeRunUploader(),
            insightsFetcher: FakeInsightsFetcher(error: RunUploadError.uploadFailed("boom"))
        )

        await viewModel.fetchORINInsights(baseURLString: "http://orin.local:8080", bearerToken: "token")

        XCTAssertTrue(viewModel.errorMessage?.contains("Unable to fetch ORIN insights. ORIN upload failed. boom") == true)
        XCTAssertFalse(viewModel.isFetchingInsights)
    }

    func testRefreshDashboardUsesRemoteInsightsWhenConfigured() async throws {
        let localCards = [
            InsightCard(
                id: "local-1",
                title: "Local",
                body: "Body",
                disclaimer: "For education only. This is not medical advice.",
                sourceLabel: "local",
                freshnessLabel: "Updated local"
            )
        ]
        let remoteCards = [
            InsightCard(
                id: "orin-1",
                title: "ORIN Overview",
                body: "Remote",
                disclaimer: "For education only. This is not medical advice.",
                sourceLabel: "orin/datasets/current",
                freshnessLabel: "Updated remote"
            )
        ]
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: nil),
            insightsStore: FakeInsightsStore(cards: localCards),
            manualExporter: FakeManualExporter(),
            runUploader: FakeRunUploader(),
            insightsFetcher: FakeInsightsFetcher(result: .cards(remoteCards))
        )

        await viewModel.refreshDashboard(baseURLString: "http://orin.local:8080", bearerToken: "token")

        XCTAssertEqual(viewModel.insightCards, remoteCards)
        XCTAssertEqual(viewModel.insightsStatusMessage, "Showing ORIN-generated insights.")
    }

    func testClinicalCompassPresentationShowsFirstExportStateWithoutData() async throws {
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: nil),
            insightsStore: FakeInsightsStore(cards: []),
            manualExporter: FakeManualExporter(),
            runUploader: FakeRunUploader(),
            insightsFetcher: FakeInsightsFetcher()
        )

        viewModel.refresh()

        XCTAssertEqual(viewModel.clinicalOverviewTitle, "Ready for your first export")
        XCTAssertTrue(viewModel.clinicalOverviewBody.contains("Export Now"))
        XCTAssertEqual(viewModel.coverageIndicatorLabel, "No data")
        XCTAssertEqual(viewModel.confidenceIndicatorLabel, "Unavailable")
        XCTAssertEqual(viewModel.primaryTrendTitle, "Primary trend")
    }

    func testClinicalCompassPresentationDerivesCalmSummaryFromInsights() async throws {
        let snapshot = SyncStatusSnapshot(
            runID: "run_cumulative",
            generatedAt: Date(timeIntervalSince1970: 1_700_000_000),
            deltaStart: Date(timeIntervalSince1970: 1_690_000_000),
            deltaEnd: Date(timeIntervalSince1970: 1_700_000_000),
            totalRows: 230_383,
            totalBytes: 13_792_887,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: ["observations": 230_383],
            sourceFiles: ["ndjson/observations.ndjson"]
        )
        let cards = [
            InsightCard(
                id: "orin-overview",
                title: "HealthDelta Summary",
                body: "Daily activity is above your recent baseline.\nObserved window remains broad and longitudinal.",
                disclaimer: "For education only. This is not medical advice.",
                sourceLabel: "orin/ollama",
                freshnessLabel: "Updated now"
            ),
            InsightCard(
                id: "orin-summary",
                title: "Summary",
                body: "Rows by source: ios=230,383.\nShare-safe report unresolved clinical reference rows: 0.",
                disclaimer: "For education only. This is not medical advice.",
                sourceLabel: "orin/ollama",
                freshnessLabel: "Updated now"
            ),
        ]
        let viewModel = DashboardViewModel(
            syncStore: FakeSyncStatusStore(snapshot: snapshot),
            insightsStore: FakeInsightsStore(cards: cards),
            manualExporter: FakeManualExporter(),
            runUploader: FakeRunUploader(),
            insightsFetcher: FakeInsightsFetcher()
        )

        viewModel.refresh()

        XCTAssertEqual(viewModel.clinicalOverviewTitle, "Overview")
        XCTAssertTrue(viewModel.clinicalOverviewBody.contains("recent baseline"))
        XCTAssertEqual(viewModel.coverageIndicatorLabel, "Longitudinal")
        XCTAssertEqual(viewModel.confidenceIndicatorLabel, "Moderate")
        XCTAssertEqual(viewModel.primaryTrendTitle, "HealthDelta Summary")
        XCTAssertTrue(viewModel.clinicalNotes.contains("Current record is activity-led."))
        XCTAssertTrue(viewModel.clinicalNotes.contains { $0.contains("Rows by source") })
    }
}

private actor AsyncGate {
    private var continuation: CheckedContinuation<Void, Never>?
    private var started = false
    private var startContinuations: [CheckedContinuation<Void, Never>] = []

    func wait() async {
        started = true
        for continuation in startContinuations {
            continuation.resume()
        }
        startContinuations.removeAll()
        await withCheckedContinuation { continuation in
            self.continuation = continuation
        }
    }

    func waitUntilBlocked() async {
        if started {
            return
        }
        await withCheckedContinuation { continuation in
            startContinuations.append(continuation)
        }
    }

    func resume() {
        continuation?.resume()
        continuation = nil
    }
}

private final class FakeSyncStatusStore: SyncStatusLoading {
    private var snapshots: [SyncStatusSnapshot?]

    init(snapshot: SyncStatusSnapshot?) {
        self.snapshots = [snapshot]
    }

    init(snapshots: [SyncStatusSnapshot?]) {
        self.snapshots = snapshots
    }

    func loadLatest() throws -> SyncStatusSnapshot {
        let snapshot = snapshots.count > 1 ? snapshots.removeFirst() : snapshots.first ?? nil
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
    let gate: AsyncGate?
    private(set) var callCount = 0

    init(error: Error? = nil, gate: AsyncGate? = nil) {
        self.error = error
        self.gate = gate
    }

    func runManualExport() async throws -> String {
        callCount += 1
        if let gate {
            await gate.wait()
        }
        if let error {
            throw error
        }
        return "run_test"
    }
}

private final class FakeRunUploader: RunUploading {
    let dataset: String
    let error: Error?
    let gate: AsyncGate?
    private(set) var callCount = 0
    private(set) var lastRunID: String?

    init(dataset: String = "dataset_test", error: Error? = nil, gate: AsyncGate? = nil) {
        self.dataset = dataset
        self.error = error
        self.gate = gate
    }

    func uploadRun(runID: String, baseURLString: String, bearerToken: String) async throws -> String {
        callCount += 1
        lastRunID = runID
        if let gate {
            await gate.wait()
        }
        if let error {
            throw error
        }
        return dataset
    }
}

private final class FakeInsightsFetcher: ORINInsightsFetching {
    let result: ORINInsightsFetchResult
    let error: Error?
    private(set) var lastCanonicalPersonID: String?
    private(set) var lastWindowDays: Int?

    init(result: ORINInsightsFetchResult = .cards([]), error: Error? = nil) {
        self.result = result
        self.error = error
    }

    func fetchCurrentInsights(
        baseURLString: String,
        bearerToken: String,
        canonicalPersonID: String?,
        windowDays: Int?
    ) async throws -> ORINInsightsFetchResult {
        lastCanonicalPersonID = canonicalPersonID
        lastWindowDays = windowDays
        if let error {
            throw error
        }
        return result
    }
}
