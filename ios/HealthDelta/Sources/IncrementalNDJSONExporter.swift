import CryptoKit
import Foundation
import HealthKit

final class IncrementalNDJSONExporter {
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
        key: String,
        type: HKSampleType,
        predicate: NSPredicate? = nil,
        limit: Int = HKObjectQueryNoLimit,
        outputURL: URL
    ) async throws -> Bool {
        let currentAnchor = anchorStore.load(forKey: key)
        let result = try await queryClient.execute(type: type, predicate: predicate, anchor: currentAnchor, limit: limit)

        // Persist anchor regardless of whether anything changed (deterministic bytes).
        try anchorStore.save(anchor: result.newAnchor, forKey: key)

        guard result.didChange else {
            return false
        }

        let canonicalPersonID = try canonicalPersonIDProvider()
        let rows = result.addedSamples.map { sampleToRow(sample: $0, canonicalPersonID: canonicalPersonID) }
        let sorted = rows.sorted { a, b in
            (a["record_key"] as? String ?? "") < (b["record_key"] as? String ?? "")
        }
        try writer.appendLines(sorted, to: outputURL)
        return true
    }

    @discardableResult
    func runOnce(
        runID: String,
        layout: IOSExportLayout,
        key: String,
        type: HKSampleType,
        predicate: NSPredicate? = nil,
        limit: Int = HKObjectQueryNoLimit
    ) async throws -> Bool {
        try layout.ensureDirectories(runID: runID)
        let outputURL = layout.observationsNDJSONURL(runID: runID)

        let changed = try await runOnce(key: key, type: type, predicate: predicate, limit: limit, outputURL: outputURL)
        try IOSExportManifestWriter(layout: layout).writeManifestIfChanged(runID: runID)
        return changed
    }

    private func sampleToRow(sample: HKSample, canonicalPersonID: String) -> [String: Any] {
        let typeId = sample.sampleType.identifier
        let start = iso8601(sample.startDate)
        let end = iso8601(sample.endDate)

        var row: [String: Any] = [
            "schema_version": 1,
            "canonical_person_id": canonicalPersonID,
            "source": "healthkit",
            "sample_type": typeId,
            "start_time": start,
            "end_time": end,
        ]

        if let qs = sample as? HKQuantitySample {
            // For the skeleton, prefer a stable numeric representation for synthetic tests.
            let unit = HKUnit.count()
            let value = qs.quantity.doubleValue(for: unit)
            row["value_num"] = value
            row["unit"] = "count"
        }

        row["record_key"] = recordKey(for: row)
        return row
    }

    private func recordKey(for row: [String: Any]) -> String {
        // Derive from stable JSON bytes without record_key to avoid recursion.
        var minimal = row
        minimal.removeValue(forKey: "record_key")
        guard let data = try? JSONSerialization.data(withJSONObject: minimal, options: [.sortedKeys]) else {
            return ""
        }
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private func iso8601(_ d: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.string(from: d)
    }
}
