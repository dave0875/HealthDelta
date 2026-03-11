import Foundation
import XCTest

@testable import HealthDelta

final class InsightsStoreTests: XCTestCase {
    func testFreshnessLabelsUseProvidedLocalTimezone() {
        let modified = Date(timeIntervalSince1970: 1_706_884_800)
        let timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let locale = Locale(identifier: "en_US")

        let freshnessLabel = InsightsStore.freshnessLabel(for: modified, timeZone: timeZone, locale: locale)

        XCTAssertEqual(normalizeDisplay(freshnessLabel), "Updated Feb 2, 2024 at 6:40 AM")
        XCTAssertFalse(freshnessLabel.contains("UTC"))
    }

    func testLoadLatestCardsReturnsDoctorNoteAndSummaryWithFreshness() throws {
        let fixture = try FixtureDocs()
        let runDir = fixture.documents.appendingPathComponent("HealthDelta/run_20260202_010203", isDirectory: true)
        try FileManager.default.createDirectory(at: runDir.appendingPathComponent("note", isDirectory: true), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: runDir.appendingPathComponent("reports", isDirectory: true), withIntermediateDirectories: true)

        try "{}".write(to: runDir.appendingPathComponent("manifest.json"), atomically: true, encoding: .utf8)
        try "# Doctor Note\n- Trend improving".write(
            to: runDir.appendingPathComponent("note/doctor_note.md"),
            atomically: true,
            encoding: .utf8
        )
        try "# Summary\n- Keep walking daily".write(
            to: runDir.appendingPathComponent("reports/summary.md"),
            atomically: true,
            encoding: .utf8
        )

        let modified = Date(timeIntervalSince1970: 1_706_884_800)
        try FileManager.default.setAttributes([.modificationDate: modified], ofItemAtPath: runDir.appendingPathComponent("note/doctor_note.md").path)
        try FileManager.default.setAttributes([.modificationDate: modified], ofItemAtPath: runDir.appendingPathComponent("reports/summary.md").path)

        let store = InsightsStore(fileManager: .default, appDocumentsURL: fixture.documents)
        let cards = try store.loadLatestCards()

        XCTAssertEqual(cards.count, 2)
        XCTAssertEqual(cards.map(\.title), ["Doctor's Note", "Summary"])
        XCTAssertTrue(cards.allSatisfy { $0.disclaimer.contains("not medical advice") })
        XCTAssertEqual(cards[0].sourceLabel, "note/doctor_note.md")
        XCTAssertEqual(cards[1].sourceLabel, "reports/summary.md")
        XCTAssertTrue(cards.allSatisfy { $0.freshnessLabel.contains("2024") })
    }

    func testLoadLatestCardsReturnsEmptyWhenNoArtifactsExist() throws {
        let fixture = try FixtureDocs()
        let runDir = fixture.documents.appendingPathComponent("HealthDelta/run_20260202_010203", isDirectory: true)
        try FileManager.default.createDirectory(at: runDir, withIntermediateDirectories: true)
        try "{}".write(to: runDir.appendingPathComponent("manifest.json"), atomically: true, encoding: .utf8)

        let store = InsightsStore(fileManager: .default, appDocumentsURL: fixture.documents)
        XCTAssertEqual(try store.loadLatestCards(), [])
    }
}

private func normalizeDisplay(_ value: String) -> String {
    value.replacingOccurrences(of: "\u{202F}", with: " ")
}

private struct FixtureDocs {
    let root: URL
    let documents: URL

    init() throws {
        root = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent("HealthDeltaInsightsTests", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        documents = root.appendingPathComponent("Documents", isDirectory: true)
        try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
    }
}
