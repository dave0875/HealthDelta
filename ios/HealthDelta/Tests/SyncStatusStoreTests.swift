import Foundation
import XCTest

@testable import HealthDelta

final class SyncStatusStoreTests: XCTestCase {
    func testLoadLatestBuildsDeterministicSnapshot() throws {
        let fixture = try FixtureDirs()
        let runDir = fixture.documents.appendingPathComponent("HealthDelta/run_20260202_010203", isDirectory: true)
        try FileManager.default.createDirectory(at: runDir, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: runDir.appendingPathComponent("ndjson", isDirectory: true), withIntermediateDirectories: true)

        let manifest = """
        {"files":[{"path":"ndjson/observations.ndjson","sha256":"x","size_bytes":1250}],"row_counts":{"observations":2},"run_id":"run_20260202_010203"}
        """
        try manifest.write(to: runDir.appendingPathComponent("manifest.json"), atomically: true, encoding: .utf8)

        let ndjson = """
        {"start_time":"2026-02-01T00:00:00.000Z","end_time":"2026-02-01T01:00:00.000Z"}
        {"start_time":"2026-02-01T05:00:00.000Z","end_time":"2026-02-01T08:30:00.000Z"}
        """
        try ndjson.write(to: runDir.appendingPathComponent("ndjson/observations.ndjson"), atomically: true, encoding: .utf8)

        let manifestDate = Date(timeIntervalSince1970: 1_706_884_800) // 2024-02-01T00:00:00Z
        try FileManager.default.setAttributes([.modificationDate: manifestDate], ofItemAtPath: runDir.appendingPathComponent("manifest.json").path)

        let anchorDir = fixture.appSupport.appendingPathComponent("HealthDelta/anchors", isDirectory: true)
        try FileManager.default.createDirectory(at: anchorDir, withIntermediateDirectories: true)
        try "anchor".write(to: anchorDir.appendingPathComponent("steps.anchor"), atomically: true, encoding: .utf8)

        let store = SyncStatusStore(
            fileManager: .default,
            appDocumentsURL: fixture.documents,
            appSupportURL: fixture.appSupport
        )
        let snapshot = try store.loadLatest()

        XCTAssertEqual(snapshot.runID, "run_20260202_010203")
        XCTAssertEqual(snapshot.totalRows, 2)
        XCTAssertEqual(snapshot.totalRowsLabel, "2")
        XCTAssertEqual(snapshot.totalBytes, 1250)
        XCTAssertEqual(snapshot.fileCount, 1)
        XCTAssertEqual(snapshot.anchorFiles, 1)
        XCTAssertEqual(snapshot.rowCounts, ["observations": 2])
        XCTAssertEqual(snapshot.sourceFiles, ["ndjson/observations.ndjson"])
        XCTAssertTrue(snapshot.lastSyncLabel.contains("2024"))
        XCTAssertTrue(snapshot.lastSyncLabel.contains("12:00 AM"))
        XCTAssertTrue(snapshot.lastDeltaLabel.contains("2026"))
        XCTAssertTrue(snapshot.lastDeltaLabel.contains("8:30 AM"))
    }

    func testLoadLatestThrowsWhenNoRunDirectoryExists() throws {
        let fixture = try FixtureDirs()
        let store = SyncStatusStore(
            fileManager: .default,
            appDocumentsURL: fixture.documents,
            appSupportURL: fixture.appSupport
        )

        XCTAssertThrowsError(try store.loadLatest()) { error in
            XCTAssertEqual(error as? SyncStatusStore.LoadError, .noRunDirectory)
        }
    }
}

private struct FixtureDirs {
    let root: URL
    let documents: URL
    let appSupport: URL

    init() throws {
        root = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent("HealthDeltaSyncStatusTests", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        documents = root.appendingPathComponent("Documents", isDirectory: true)
        appSupport = root.appendingPathComponent("ApplicationSupport", isDirectory: true)
        try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: appSupport, withIntermediateDirectories: true)
    }
}
