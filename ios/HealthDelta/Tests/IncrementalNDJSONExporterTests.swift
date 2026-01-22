import Foundation
import HealthKit
import XCTest

@testable import HealthDelta

final class IncrementalNDJSONExporterTests: XCTestCase {
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
        let outURL = tmp.appendingPathComponent("out.ndjson", isDirectory: false)

        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: anchorsDir),
            queryClient: FakeAnchoredQueryClient(script: script)
        )

        let wrote1 = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
        XCTAssertTrue(wrote1)
        let bytes1 = try Data(contentsOf: outURL)
        XCTAssertTrue(bytes1.count > 0)
        XCTAssertEqual(bytes1.last, 0x0A)

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
            let outURL = tmp.appendingPathComponent("out.ndjson", isDirectory: false)

            let exporter = IncrementalNDJSONExporter(anchorStore: AnchorStore(directoryURL: anchorsDir), queryClient: FakeAnchoredQueryClient(script: script))
            _ = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
            _ = try await exporter.runOnce(key: "steps", type: type, outputURL: outURL)
            return try Data(contentsOf: outURL)
        }

        let a = try await runOnceInFreshDir()
        let b = try await runOnceInFreshDir()
        XCTAssertEqual(a, b)
    }
}

