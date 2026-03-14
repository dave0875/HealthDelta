import CryptoKit
import Foundation
import HealthKit

final class IncrementalNDJSONExporter {
    private struct ExportBatch {
        let changed: Bool
        let deltaStart: Date?
        let deltaEnd: Date?
    }

    private let anchorStore: AnchorStore
    private let queryClient: AnchoredQuerying
    private let writer: NDJSONWriter
    private let canonicalPersonIDProvider: () throws -> String

    init(
        anchorStore: AnchorStore,
        queryClient: AnchoredQuerying,
        canonicalPersonIDProvider: @escaping () throws -> String = { try CanonicalPersonIDStore.defaultInAppSandbox().getOrCreate() },
        writer: NDJSONWriter = NDJSONWriter()
    ) {
        self.anchorStore = anchorStore
        self.queryClient = queryClient
        self.canonicalPersonIDProvider = canonicalPersonIDProvider
        self.writer = writer
    }

    @discardableResult
    func runOnce(
        plan: HealthKitExportPlan,
        predicate: NSPredicate? = nil,
        limit: Int = HKObjectQueryNoLimit,
        outputURL: URL
    ) async throws -> Bool {
        let batch = try await exportBatch(
            plan: plan,
            predicate: predicate,
            limit: limit,
            outputURL: outputURL
        )
        return batch.changed
    }

    @discardableResult
    func runOnce(
        runID: String,
        layout: IOSExportLayout,
        plan: HealthKitExportPlan,
        predicate: NSPredicate? = nil,
        limit: Int = HKObjectQueryNoLimit
    ) async throws -> Bool {
        try layout.ensureDirectories(runID: runID)
        let outputURL = layout.observationsNDJSONURL(runID: runID)

        let batch = try await exportBatch(
            plan: plan,
            predicate: predicate,
            limit: limit,
            outputURL: outputURL
        )
        try IOSExportManifestWriter(layout: layout).writeManifestIfChanged(
            runID: runID,
            deltaStart: batch.deltaStart,
            deltaEnd: batch.deltaEnd
        )
        return batch.changed
    }

    private func exportBatch(
        plan: HealthKitExportPlan,
        predicate: NSPredicate?,
        limit: Int,
        outputURL: URL
    ) async throws -> ExportBatch {
        let currentAnchor = anchorStore.load(forKey: plan.key)
        let result = try await queryClient.execute(type: plan.type, predicate: predicate, anchor: currentAnchor, limit: limit)

        // Persist anchor regardless of whether anything changed (deterministic bytes).
        try anchorStore.save(anchor: result.newAnchor, forKey: plan.key)

        guard result.didChange else {
            return ExportBatch(changed: false, deltaStart: nil, deltaEnd: nil)
        }

        let canonicalPersonID = try canonicalPersonIDProvider()
        let rows = result.addedSamples.map { sampleToRow(sample: $0, canonicalPersonID: canonicalPersonID) }
        let sorted = rows.sorted { a, b in
            (a["record_key"] as? String ?? "") < (b["record_key"] as? String ?? "")
        }
        try writer.appendLines(sorted, to: outputURL)

        let deltaStart = result.addedSamples.map(\.startDate).min()
        let deltaEnd = result.addedSamples.map(\.endDate).max()
        return ExportBatch(changed: true, deltaStart: deltaStart, deltaEnd: deltaEnd)
    }

    private func sampleToRow(sample: HKSample, canonicalPersonID: String) -> [String: Any] {
        let typeId = sample.sampleType.identifier
        let start = iso8601(sample.startDate)
        let end = iso8601(sample.endDate)
        let sourceID = healthKitSourceID(for: sample)

        var row: [String: Any] = [
            "schema_version": 1,
            "canonical_person_id": canonicalPersonID,
            "source": "healthkit",
            "source_id": sourceID,
            "sample_type": typeId,
            "start_time": start,
            "end_time": end,
        ]

        if let qs = sample as? HKQuantitySample {
            row["sample_kind"] = "quantity"
            if let preferred = HealthKitExportCatalog.preferredUnit(for: typeId) {
                row["value_num"] = qs.quantity.doubleValue(for: preferred.unit)
                row["unit"] = preferred.label
            }
        } else if let category = sample as? HKCategorySample {
            row["sample_kind"] = "category"
            row["category_value"] = category.value
            row["value_num"] = Double(category.value)
            let label = HealthKitExportCatalog.categoryValueLabel(for: typeId, value: category.value) ?? String(category.value)
            row["value"] = label
            row["value_text"] = label
        } else if let workout = sample as? HKWorkout {
            let activityLabel = HealthKitExportCatalog.workoutActivityLabel(for: workout.workoutActivityType)
            row["sample_kind"] = "workout"
            row["activity_type"] = activityLabel
            row["value"] = activityLabel
            row["value_text"] = activityLabel
            row["duration_seconds"] = workout.duration
            row["value_num"] = workout.duration
            row["unit"] = "s"
            if let totalEnergyBurned = workout.totalEnergyBurned {
                row["total_energy_burned_num"] = totalEnergyBurned.doubleValue(for: .kilocalorie())
                row["total_energy_burned_unit"] = "kcal"
            }
            if let totalDistance = workout.totalDistance {
                row["total_distance_num"] = totalDistance.doubleValue(for: .meter())
                row["total_distance_unit"] = "m"
            }
        }

        row["record_key"] = recordKey(for: row)
        return row
    }

    private func recordKey(for row: [String: Any]) -> String {
        if let sourceID = row["source_id"] as? String, !sourceID.isEmpty {
            return sha256Hex("healthkit:\(sourceID)")
        }

        // Fallback for legacy or malformed rows: derive from stable JSON bytes without record_key to avoid recursion.
        var minimal = row
        minimal.removeValue(forKey: "record_key")
        guard let data = try? JSONSerialization.data(withJSONObject: minimal, options: [.sortedKeys]) else {
            return ""
        }
        return sha256Hex(data)
    }

    private func healthKitSourceID(for sample: HKSample) -> String {
        "HKSample/\(sample.uuid.uuidString.lowercased())"
    }

    private func sha256Hex(_ value: String) -> String {
        guard let data = value.data(using: .utf8) else {
            return ""
        }
        return sha256Hex(data)
    }

    private func sha256Hex(_ data: Data) -> String {
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private func iso8601(_ d: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.string(from: d)
    }
}
