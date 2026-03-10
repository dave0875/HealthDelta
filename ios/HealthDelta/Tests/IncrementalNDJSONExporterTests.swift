import CryptoKit
import Foundation
import HealthKit
import XCTest

@testable import HealthDelta

final class IncrementalNDJSONExporterTests: XCTestCase {
    private let _fixedCanonicalPersonID = "123e4567-e89b-42d3-a456-426614174000"

    private func _makeSample(type: HKQuantityType) -> HKQuantitySample {
        HKQuantitySample(
            type: type,
            quantity: HKQuantity(unit: .count(), doubleValue: 1),
            start: Date(timeIntervalSince1970: 0),
            end: Date(timeIntervalSince1970: 0)
        )
    }

    func testDeterministicOutputAndNoOpWhenUnchanged() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let sample = _makeSample(type: type)

        let a1 = HKQueryAnchor(fromValue: 1)
        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [sample], deletedObjects: [], newAnchor: a1)),
            .init(result: AnchoredQueryResult(addedSamples: [], deletedObjects: [], newAnchor: a1)),
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let anchorsDir = tmp.appendingPathComponent("anchors", isDirectory: true)
        let outBase = tmp.appendingPathComponent("HealthDelta", isDirectory: true)
        let outURL = IOSExportLayout(baseDirectoryURL: outBase).observationsNDJSONURL(runID: "run_1")

        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: anchorsDir),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
        )

        let wrote1 = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
        XCTAssertTrue(wrote1)
        let bytes1 = try Data(contentsOf: outURL)
        XCTAssertTrue(bytes1.count > 0)
        XCTAssertEqual(bytes1.last, 0x0A)
        let rows1 = try _rows(from: bytes1)
        _assertAllRowsHaveCanonicalPersonID(rows1)
        XCTAssertEqual(rows1.count, 1)
        XCTAssertTrue((rows1[0]["source_id"] as? String)?.hasPrefix("HKSample/") == true)
        XCTAssertEqual(rows1[0]["record_key"] as? String, _expectedRecordKey(sourceID: rows1[0]["source_id"] as? String ?? ""))

        let wrote2 = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
        XCTAssertFalse(wrote2)
        let bytes2 = try Data(contentsOf: outURL)
        XCTAssertEqual(bytes2, bytes1)
    }

    func testDeterministicOutputAcrossFreshReruns() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let sample = _makeSample(type: type)
        let a1 = HKQueryAnchor(fromValue: 1)

        func runOnceInFreshDir() async throws -> Data {
            let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
                .init(result: AnchoredQueryResult(addedSamples: [sample], deletedObjects: [], newAnchor: a1)),
                .init(result: AnchoredQueryResult(addedSamples: [], deletedObjects: [], newAnchor: a1)),
            ]

            let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
            let anchorsDir = tmp.appendingPathComponent("anchors", isDirectory: true)
            let outBase = tmp.appendingPathComponent("HealthDelta", isDirectory: true)
            let outURL = IOSExportLayout(baseDirectoryURL: outBase).observationsNDJSONURL(runID: "run_1")

            let exporter = IncrementalNDJSONExporter(
                anchorStore: AnchorStore(directoryURL: anchorsDir),
                queryClient: FakeAnchoredQueryClient(script: script),
                canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
            )
            _ = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
            _ = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
            let bytes = try Data(contentsOf: outURL)
            _assertAllRowsHaveCanonicalPersonID(try _rows(from: bytes))
            return bytes
        }

        let a = try await runOnceInFreshDir()
        let b = try await runOnceInFreshDir()
        XCTAssertEqual(a, b)
    }

    func testDistinctSamplesWithSameVisibleFieldsProduceDistinctRecordKeys() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let sampleA = _makeSample(type: type)
        let sampleB = _makeSample(type: type)
        XCTAssertNotEqual(sampleA.uuid, sampleB.uuid)

        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [sampleA, sampleB], deletedObjects: [], newAnchor: HKQueryAnchor(fromValue: 1)))
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let anchorsDir = tmp.appendingPathComponent("anchors", isDirectory: true)
        let outBase = tmp.appendingPathComponent("HealthDelta", isDirectory: true)
        let outURL = IOSExportLayout(baseDirectoryURL: outBase).observationsNDJSONURL(runID: "run_1")

        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: anchorsDir),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
        )

        let wrote = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
        XCTAssertTrue(wrote)

        let rows = try _rows(from: Data(contentsOf: outURL))
        XCTAssertEqual(rows.count, 2)
        let sourceIDs = rows.compactMap { $0["source_id"] as? String }
        let recordKeys = rows.compactMap { $0["record_key"] as? String }
        XCTAssertEqual(Set(sourceIDs).count, 2)
        XCTAssertEqual(Set(recordKeys).count, 2)
        XCTAssertEqual(Set(zip(sourceIDs, recordKeys).map(_expectedRecordKeyPair)), Set(recordKeys))
    }

    private func _rows(from bytes: Data) throws -> [[String: Any]] {
        guard let s = String(data: bytes, encoding: .utf8) else {
            XCTFail("invalid UTF-8")
            return []
        }
        let lines = s.split(separator: "\n")
        XCTAssertFalse(lines.isEmpty)

        return try lines.map { line in
            let obj = try JSONSerialization.jsonObject(with: Data(line.utf8), options: [])
            guard let dict = obj as? [String: Any] else {
                XCTFail("not a JSON object")
                return [:]
            }
            return dict
        }
    }

    private func _assertAllRowsHaveCanonicalPersonID(_ rows: [[String: Any]]) {
        for dict in rows {
            XCTAssertEqual(dict["canonical_person_id"] as? String, _fixedCanonicalPersonID)
        }
    }

    private func _expectedRecordKey(sourceID: String) -> String {
        let digest = SHA256.hash(data: Data("healthkit:\(sourceID)".utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private func _expectedRecordKeyPair(_ pair: (String, String)) -> String {
        _expectedRecordKey(sourceID: pair.0)
    }
}
