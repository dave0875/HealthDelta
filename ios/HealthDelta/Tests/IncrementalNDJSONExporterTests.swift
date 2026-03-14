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
        let plan = HealthKitExportPlan(key: "steps", type: type)
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

        let wrote1 = try await exporter.runOnce(plan: plan, outputURL: outURL)
        XCTAssertTrue(wrote1)
        let bytes1 = try Data(contentsOf: outURL)
        XCTAssertTrue(bytes1.count > 0)
        XCTAssertEqual(bytes1.last, 0x0A)
        let rows1 = try _rows(from: bytes1)
        _assertAllRowsHaveCanonicalPersonID(rows1)
        XCTAssertEqual(rows1.count, 1)
        XCTAssertTrue((rows1[0]["source_id"] as? String)?.hasPrefix("HKSample/") == true)
        XCTAssertEqual(rows1[0]["record_key"] as? String, _expectedRecordKey(sourceID: rows1[0]["source_id"] as? String ?? ""))

        let wrote2 = try await exporter.runOnce(plan: plan, outputURL: outURL)
        XCTAssertFalse(wrote2)
        let bytes2 = try Data(contentsOf: outURL)
        XCTAssertEqual(bytes2, bytes1)
    }

    func testDeterministicOutputAcrossFreshReruns() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let plan = HealthKitExportPlan(key: "steps", type: type)
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
            _ = try await exporter.runOnce(plan: plan, outputURL: outURL)
            _ = try await exporter.runOnce(plan: plan, outputURL: outURL)
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
        let plan = HealthKitExportPlan(key: "steps", type: type)
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

        let wrote = try await exporter.runOnce(plan: plan, outputURL: outURL)
        XCTAssertTrue(wrote)

        let rows = try _rows(from: Data(contentsOf: outURL))
        XCTAssertEqual(rows.count, 2)
        let sourceIDs = rows.compactMap { $0["source_id"] as? String }
        let recordKeys = rows.compactMap { $0["record_key"] as? String }
        XCTAssertEqual(Set(sourceIDs).count, 2)
        XCTAssertEqual(Set(recordKeys).count, 2)
        XCTAssertEqual(Set(zip(sourceIDs, recordKeys).map(_expectedRecordKeyPair)), Set(recordKeys))
    }

    func testQuantitySamplesUseTypeSpecificUnits() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .heartRate)!
        let plan = HealthKitExportPlan(key: "heart_rate", type: type)
        let sample = HKQuantitySample(
            type: type,
            quantity: HKQuantity(unit: .count().unitDivided(by: .minute()), doubleValue: 72),
            start: Date(timeIntervalSince1970: 0),
            end: Date(timeIntervalSince1970: 0)
        )

        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [sample], deletedObjects: [], newAnchor: HKQueryAnchor(fromValue: 1)))
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let outURL = IOSExportLayout(baseDirectoryURL: tmp.appendingPathComponent("HealthDelta", isDirectory: true)).observationsNDJSONURL(runID: "run_1")
        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: tmp.appendingPathComponent("anchors", isDirectory: true)),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
        )

        _ = try await exporter.runOnce(plan: plan, outputURL: outURL)
        let row = try XCTUnwrap(_rows(from: Data(contentsOf: outURL)).first)
        XCTAssertEqual(row["sample_kind"] as? String, "quantity")
        XCTAssertEqual(row["sample_type"] as? String, HKQuantityTypeIdentifier.heartRate.rawValue)
        XCTAssertEqual(row["unit"] as? String, "count/min")
        XCTAssertEqual(row["value_num"] as? Double, 72)
    }

    func testCategorySamplesEncodeValueAndLabel() async throws {
        let type = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis)!
        let plan = HealthKitExportPlan(key: "sleep_analysis", type: type)
        let sample = HKCategorySample(
            type: type,
            value: HKCategoryValueSleepAnalysis.asleepCore.rawValue,
            start: Date(timeIntervalSince1970: 0),
            end: Date(timeIntervalSince1970: 600)
        )

        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [sample], deletedObjects: [], newAnchor: HKQueryAnchor(fromValue: 1)))
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let outURL = IOSExportLayout(baseDirectoryURL: tmp.appendingPathComponent("HealthDelta", isDirectory: true)).observationsNDJSONURL(runID: "run_1")
        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: tmp.appendingPathComponent("anchors", isDirectory: true)),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
        )

        _ = try await exporter.runOnce(plan: plan, outputURL: outURL)
        let row = try XCTUnwrap(_rows(from: Data(contentsOf: outURL)).first)
        XCTAssertEqual(row["sample_kind"] as? String, "category")
        XCTAssertEqual(row["sample_type"] as? String, HKCategoryTypeIdentifier.sleepAnalysis.rawValue)
        XCTAssertEqual(row["category_value"] as? Int, HKCategoryValueSleepAnalysis.asleepCore.rawValue)
        XCTAssertEqual(row["value"] as? String, "asleep_core")
        XCTAssertEqual(row["value_text"] as? String, "asleep_core")
    }

    func testWorkoutSamplesEncodeActivityAndTotals() async throws {
        let type = HKObjectType.workoutType()
        let plan = HealthKitExportPlan(key: "workouts", type: type)
        let sample = HKWorkout(
            activityType: .running,
            start: Date(timeIntervalSince1970: 0),
            end: Date(timeIntervalSince1970: 1800),
            duration: 1800,
            totalEnergyBurned: HKQuantity(unit: .kilocalorie(), doubleValue: 450),
            totalDistance: HKQuantity(unit: .meter(), doubleValue: 5000),
            metadata: nil
        )

        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [sample], deletedObjects: [], newAnchor: HKQueryAnchor(fromValue: 1)))
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let outURL = IOSExportLayout(baseDirectoryURL: tmp.appendingPathComponent("HealthDelta", isDirectory: true)).observationsNDJSONURL(runID: "run_1")
        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: tmp.appendingPathComponent("anchors", isDirectory: true)),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
        )

        _ = try await exporter.runOnce(plan: plan, outputURL: outURL)
        let row = try XCTUnwrap(_rows(from: Data(contentsOf: outURL)).first)
        XCTAssertEqual(row["sample_kind"] as? String, "workout")
        XCTAssertEqual(row["sample_type"] as? String, HKWorkoutType.workoutType().identifier)
        XCTAssertEqual(row["activity_type"] as? String, "running")
        XCTAssertEqual(row["value_text"] as? String, "running")
        XCTAssertEqual(row["unit"] as? String, "s")
        XCTAssertEqual(row["duration_seconds"] as? Double, 1800)
        XCTAssertEqual(row["total_energy_burned_num"] as? Double, 450)
        XCTAssertEqual(row["total_energy_burned_unit"] as? String, "kcal")
        XCTAssertEqual(row["total_distance_num"] as? Double, 5000)
        XCTAssertEqual(row["total_distance_unit"] as? String, "m")
    }

    func testRunWithLayoutWritesManifestDeltaWindowFromExportedSamples() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let plan = HealthKitExportPlan(key: "steps", type: type)
        let sampleA = HKQuantitySample(
            type: type,
            quantity: HKQuantity(unit: .count(), doubleValue: 10),
            start: Date(timeIntervalSince1970: 100),
            end: Date(timeIntervalSince1970: 200)
        )
        let sampleB = HKQuantitySample(
            type: type,
            quantity: HKQuantity(unit: .count(), doubleValue: 20),
            start: Date(timeIntervalSince1970: 300),
            end: Date(timeIntervalSince1970: 500)
        )

        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [sampleA, sampleB], deletedObjects: [], newAnchor: HKQueryAnchor(fromValue: 1)))
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let layout = IOSExportLayout(baseDirectoryURL: tmp.appendingPathComponent("HealthDelta", isDirectory: true))
        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: tmp.appendingPathComponent("anchors", isDirectory: true)),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
        )

        _ = try await exporter.runOnce(runID: "run_1", layout: layout, plan: plan)

        let manifestURL = layout.manifestURL(runID: "run_1")
        let manifestData = try Data(contentsOf: manifestURL)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: manifestData) as? [String: Any])

        XCTAssertEqual(object["delta_start"] as? String, "1970-01-01T00:01:40.000Z")
        XCTAssertEqual(object["delta_end"] as? String, "1970-01-01T00:08:20.000Z")
    }

    func testRunWithLayoutMergesManifestDeltaWindowAcrossPlans() async throws {
        let stepsType = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let heartType = HKQuantityType.quantityType(forIdentifier: .heartRate)!
        let stepsPlan = HealthKitExportPlan(key: "steps", type: stepsType)
        let heartPlan = HealthKitExportPlan(key: "heart_rate", type: heartType)

        let earlySample = HKQuantitySample(
            type: heartType,
            quantity: HKQuantity(unit: .count().unitDivided(by: .minute()), doubleValue: 70),
            start: Date(timeIntervalSince1970: 50),
            end: Date(timeIntervalSince1970: 75)
        )
        let lateSample = HKQuantitySample(
            type: stepsType,
            quantity: HKQuantity(unit: .count(), doubleValue: 100),
            start: Date(timeIntervalSince1970: 300),
            end: Date(timeIntervalSince1970: 900)
        )

        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [lateSample], deletedObjects: [], newAnchor: HKQueryAnchor(fromValue: 1))),
            .init(result: AnchoredQueryResult(addedSamples: [earlySample], deletedObjects: [], newAnchor: HKQueryAnchor(fromValue: 2))),
        ]

        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true).appendingPathComponent(UUID().uuidString, isDirectory: true)
        let layout = IOSExportLayout(baseDirectoryURL: tmp.appendingPathComponent("HealthDelta", isDirectory: true))
        let exporter = IncrementalNDJSONExporter(
            anchorStore: AnchorStore(directoryURL: tmp.appendingPathComponent("anchors", isDirectory: true)),
            queryClient: FakeAnchoredQueryClient(script: script),
            canonicalPersonIDProvider: { self._fixedCanonicalPersonID }
        )

        _ = try await exporter.runOnce(runID: "run_1", layout: layout, plan: stepsPlan)
        _ = try await exporter.runOnce(runID: "run_1", layout: layout, plan: heartPlan)

        let manifestURL = layout.manifestURL(runID: "run_1")
        let manifestData = try Data(contentsOf: manifestURL)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: manifestData) as? [String: Any])

        XCTAssertEqual(object["delta_start"] as? String, "1970-01-01T00:00:50.000Z")
        XCTAssertEqual(object["delta_end"] as? String, "1970-01-01T00:15:00.000Z")
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
