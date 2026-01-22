import Foundation
import HealthKit
import XCTest

@testable import HealthDelta

final class AnchoredQueryClientTests: XCTestCase {
    private func _anchorBytes(_ a: HKQueryAnchor) throws -> Data {
        try NSKeyedArchiver.archivedData(withRootObject: a, requiringSecureCoding: true)
    }

    func testAnchorProgressionDeterministic() async throws {
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
            .init(result: AnchoredQueryResult(addedSamples: [], deletedObjects: [], newAnchor: a1)),
        ]

        let client = FakeAnchoredQueryClient(script: script)

        let r1 = try await client.execute(type: type, predicate: nil, anchor: nil, limit: 100)
        XCTAssertTrue(r1.didChange)
        XCTAssertEqual(try _anchorBytes(r1.newAnchor), try _anchorBytes(a1))

        let r2 = try await client.execute(type: type, predicate: nil, anchor: r1.newAnchor, limit: 100)
        XCTAssertFalse(r2.didChange)
        XCTAssertEqual(try _anchorBytes(r2.newAnchor), try _anchorBytes(a1))

        XCTAssertEqual(client.receivedAnchors.count, 2)
        XCTAssertNil(client.receivedAnchors[0])
        XCTAssertNotNil(client.receivedAnchors[1])
        XCTAssertEqual(try _anchorBytes(client.receivedAnchors[1]!), try _anchorBytes(a1))
    }

    func testNoOpWhenNoNewSamples() async throws {
        let type = HKQuantityType.quantityType(forIdentifier: .stepCount)!
        let anchor = HKQueryAnchor(fromValue: 42)
        let script: [FakeAnchoredQueryClient.ScriptedResponse] = [
            .init(result: AnchoredQueryResult(addedSamples: [], deletedObjects: [], newAnchor: anchor))
        ]
        let client = FakeAnchoredQueryClient(script: script)

        let r = try await client.execute(type: type, predicate: nil, anchor: anchor, limit: 100)
        XCTAssertFalse(r.didChange)
        XCTAssertEqual(try _anchorBytes(r.newAnchor), try _anchorBytes(anchor))
    }
}
