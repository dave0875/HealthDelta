import Foundation
import XCTest

@testable import HealthDelta

final class SyncStatusStoreTests: XCTestCase {
    func testDisplayLabelsUseProvidedLocalTimezone() {
        let generatedAt = Date(timeIntervalSince1970: 1_706_884_800)
        let deltaStart = Date(timeIntervalSince1970: 1_769_904_000)
        let deltaEnd = Date(timeIntervalSince1970: 1_769_934_600)
        let timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let locale = Locale(identifier: "en_US")

        let snapshot = SyncStatusSnapshot(
            runID: "run_test",
            generatedAt: generatedAt,
            deltaStart: deltaStart,
            deltaEnd: deltaEnd,
            totalRows: 1,
            totalBytes: 1,
            fileCount: 1,
            anchorFiles: 1,
            rowCounts: [:],
            sourceFiles: []
        )

        let localSync = snapshot.lastSyncLabel(timeZone: timeZone, locale: locale)
        let localDelta = snapshot.lastDeltaLabel(timeZone: timeZone, locale: locale)
        let utcSync = SyncStatusStore.displayDateString(
            from: generatedAt,
            timeZone: TimeZone(secondsFromGMT: 0)!,
            locale: locale
        )

        XCTAssertEqual(normalizeDisplay(localSync), "Feb 2, 2024 at 6:40 AM")
        XCTAssertEqual(normalizeDisplay(localDelta), "Jan 31, 2026 at 4:00 PM -> Feb 1, 2026 at 12:30 AM")
        XCTAssertNotEqual(localSync, utcSync)
    }

    func testLoadLatestBuildsDeterministicSnapshot() throws {
        let fixture = try FixtureDirs()
        let runDir = fixture.documents.appendingPathComponent("HealthDelta/run_20260202_010203", isDirectory: true)
        try FileManager.default.createDirectory(at: runDir, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: runDir.appendingPathComponent("ndjson", isDirectory: true), withIntermediateDirectories: true)

        let manifest = """
        {"delta_end":"2026-02-01T08:30:00.000Z","delta_start":"2026-02-01T00:00:00.000Z","files":[{"path":"ndjson/observations.ndjson","sha256":"x","size_bytes":1250}],"row_counts":{"observations":2},"run_id":"run_20260202_010203"}
        """
        try manifest.write(to: runDir.appendingPathComponent("manifest.json"), atomically: true, encoding: .utf8)

        let ndjson = """
        {"unexpected":"payload"}
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
        XCTAssertNotNil(snapshot.generatedAt)
        XCTAssertNotNil(snapshot.deltaStart)
        XCTAssertNotNil(snapshot.deltaEnd)
        XCTAssertEqual(snapshot.generatedAt!.timeIntervalSince1970, 1_706_884_800.0, accuracy: 1.0)
        XCTAssertEqual(snapshot.deltaStart!.timeIntervalSince1970, 1_769_904_000.0, accuracy: 1.0)
        XCTAssertEqual(snapshot.deltaEnd!.timeIntervalSince1970, 1_769_934_600.0, accuracy: 1.0)
        XCTAssertNotEqual(snapshot.lastSyncLabel, "Unknown")
        XCTAssertNotEqual(snapshot.lastDeltaLabel, "Not available yet")
    }

    func testLoadLatestDoesNotParseNDJSONWhenManifestLacksDeltaWindow() throws {
        let fixture = try FixtureDirs()
        let runDir = fixture.documents.appendingPathComponent("HealthDelta/run_legacy", isDirectory: true)
        try FileManager.default.createDirectory(at: runDir, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: runDir.appendingPathComponent("ndjson", isDirectory: true), withIntermediateDirectories: true)

        let manifest = """
        {"files":[{"path":"ndjson/observations.ndjson","sha256":"x","size_bytes":12}],"row_counts":{"observations":1},"run_id":"run_legacy"}
        """
        try manifest.write(to: runDir.appendingPathComponent("manifest.json"), atomically: true, encoding: .utf8)
        try "not-json-at-all\n".write(
            to: runDir.appendingPathComponent("ndjson/observations.ndjson"),
            atomically: true,
            encoding: .utf8
        )

        let store = SyncStatusStore(
            fileManager: .default,
            appDocumentsURL: fixture.documents,
            appSupportURL: fixture.appSupport
        )
        let snapshot = try store.loadLatest()

        XCTAssertEqual(snapshot.runID, "run_legacy")
        XCTAssertNil(snapshot.deltaStart)
        XCTAssertNil(snapshot.deltaEnd)
        XCTAssertEqual(snapshot.lastDeltaLabel, "Not available yet")
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

    func testLoadLatestSkipsNewerManifestOnlyStubRun() throws {
        let fixture = try FixtureDirs()
        let root = fixture.documents.appendingPathComponent("HealthDelta", isDirectory: true)
        let goodRun = root.appendingPathComponent("run_good", isDirectory: true)
        let stubRun = root.appendingPathComponent("run_stub", isDirectory: true)
        try FileManager.default.createDirectory(at: goodRun.appendingPathComponent("ndjson", isDirectory: true), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: stubRun.appendingPathComponent("ndjson", isDirectory: true), withIntermediateDirectories: true)

        try """
        {"files":[{"path":"ndjson/observations.ndjson","sha256":"x","size_bytes":12}],"row_counts":{"observations":1},"run_id":"run_good"}
        """.write(to: goodRun.appendingPathComponent("manifest.json"), atomically: true, encoding: .utf8)
        try "{\"start_time\":\"2026-02-01T00:00:00Z\",\"end_time\":\"2026-02-01T01:00:00Z\"}\n".write(
            to: goodRun.appendingPathComponent("ndjson/observations.ndjson"),
            atomically: true,
            encoding: .utf8
        )

        try """
        {"files":[],"row_counts":{"observations":0},"run_id":"run_stub"}
        """.write(to: stubRun.appendingPathComponent("manifest.json"), atomically: true, encoding: .utf8)

        let oldDate = Date(timeIntervalSince1970: 1_700_000_000)
        let newDate = Date(timeIntervalSince1970: 1_800_000_000)
        try FileManager.default.setAttributes([.modificationDate: oldDate], ofItemAtPath: goodRun.path)
        try FileManager.default.setAttributes([.modificationDate: newDate], ofItemAtPath: stubRun.path)

        let store = SyncStatusStore(
            fileManager: .default,
            appDocumentsURL: fixture.documents,
            appSupportURL: fixture.appSupport
        )
        let snapshot = try store.loadLatest()

        XCTAssertEqual(snapshot.runID, "run_good")
        XCTAssertEqual(snapshot.totalRows, 1)
    }
}

private func normalizeDisplay(_ value: String) -> String {
    value.replacingOccurrences(of: "\u{202F}", with: " ")
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
