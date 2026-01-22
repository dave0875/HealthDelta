import CryptoKit
import Foundation
import HealthKit
import XCTest

@testable import HealthDelta

final class IOSExportManifestTests: XCTestCase {
    func testManifestBytesAreDeterministicAcrossReruns() throws {
        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let base = tmp.appendingPathComponent("HealthDelta", isDirectory: true)
        let runID = "run_1"

        let layout = IOSExportLayout(baseDirectoryURL: base)
        try layout.ensureDirectories(runID: runID)

        let observationsURL = layout.observationsNDJSONURL(runID: runID)
        try "a\nb\n".data(using: .utf8)!.write(to: observationsURL, options: [.atomic])

        let writer = IOSExportManifestWriter(layout: layout)
        let a = try writer.buildManifestData(runID: runID)
        let b = try writer.buildManifestData(runID: runID)
        XCTAssertEqual(a, b)

        let obj = try JSONSerialization.jsonObject(with: a, options: [])
        guard let dict = obj as? [String: Any] else {
            XCTFail("manifest not a JSON object")
            return
        }

        XCTAssertEqual(dict["run_id"] as? String, runID)

        let counts = dict["row_counts"] as? [String: Any]
        XCTAssertEqual(counts?["observations"] as? Int, 2)

        let files = dict["files"] as? [[String: Any]]
        XCTAssertEqual(files?.count, 1)
        XCTAssertEqual(files?.first?["path"] as? String, "ndjson/observations.ndjson")
        XCTAssertEqual(files?.first?["size_bytes"] as? Int, 4)

        let sha = files?.first?["sha256"] as? String
        XCTAssertEqual(sha, _sha256Hex(Data("a\nb\n".utf8)))
    }

    private func _sha256Hex(_ data: Data) -> String {
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    func testExporterWritesManifestAlongsideNDJSON() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let sample = HKQuantitySample(
            type: type,
            quantity: HKQuantity(unit: .count(), doubleValue: 1),
            start: Date(timeIntervalSince1970: 0),
            end: Date(timeIntervalSince1970: 0)
        )

        let a1 = HKQueryAnchor(fromValue: 1)
        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [sample], deletedObjects: [], newAnchor: a1)),
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let base = tmp.appendingPathComponent("HealthDelta", isDirectory: true)
        let layout = IOSExportLayout(baseDirectoryURL: base)

        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: tmp.appendingPathComponent("anchors", isDirectory: true)),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { "123e4567-e89b-42d3-a456-426614174000" }
        )

        let changed = try await exporter.runOnce(runID: "run_1", layout: layout, key: "steps", type: type)
        XCTAssertTrue(changed)

        let manifestURL = layout.manifestURL(runID: "run_1")
        XCTAssertTrue(FileManager.default.fileExists(atPath: manifestURL.path))
    }
}
