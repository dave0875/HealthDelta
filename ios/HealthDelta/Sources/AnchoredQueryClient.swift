import Foundation
import HealthKit

struct AnchoredQueryResult {
    let addedSamples: [HKSample]
    let deletedObjects: [HKDeletedObject]
    let newAnchor: HKQueryAnchor

    var didChange: Bool { !addedSamples.isEmpty || !deletedObjects.isEmpty }
}

protocol AnchoredQuerying {
    func execute(
        type: HKSampleType,
        predicate: NSPredicate?,
        anchor: HKQueryAnchor?,
        limit: Int
    ) async throws -> AnchoredQueryResult
}

final class HealthKitAnchoredQueryClient: AnchoredQuerying {
    private let store: HKHealthStore

    init(store: HKHealthStore) {
        self.store = store
    }

    func execute(
        type: HKSampleType,
        predicate: NSPredicate?,
        anchor: HKQueryAnchor?,
        limit: Int
    ) async throws -> AnchoredQueryResult {
        try await withCheckedThrowingContinuation { continuation in
            let query = HKAnchoredObjectQuery(type: type, predicate: predicate, anchor: anchor, limit: limit) { _, samples, deleted, newAnchor, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                guard let newAnchor else {
                    continuation.resume(throwing: NSError(domain: "HealthDelta", code: 1, userInfo: [NSLocalizedDescriptionKey: "Missing anchor"]))
                    return
                }

                continuation.resume(
                    returning: AnchoredQueryResult(
                        addedSamples: samples ?? [],
                        deletedObjects: deleted ?? [],
                        newAnchor: newAnchor
                    )
                )
            }
            self.store.execute(query)
        }
    }
}

final class FakeAnchoredQueryClient: AnchoredQuerying {
    struct ScriptedResponse {
        let result: AnchoredQueryResult
    }

    private(set) var receivedAnchors: [HKQueryAnchor?] = []
    private var queue: [ScriptedResponse]

    init(script: [ScriptedResponse]) {
        self.queue = script
    }

    func execute(
        type: HKSampleType,
        predicate: NSPredicate?,
        anchor: HKQueryAnchor?,
        limit: Int
    ) async throws -> AnchoredQueryResult {
        receivedAnchors.append(anchor)
        if queue.isEmpty {
            // Deterministic default: no-op with the same anchor (or zero anchor if nil).
            return AnchoredQueryResult(addedSamples: [], deletedObjects: [], newAnchor: anchor ?? HKQueryAnchor(fromValue: 0))
        }
        return queue.removeFirst().result
    }
}

