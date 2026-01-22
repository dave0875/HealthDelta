import Foundation
import XCTest

@testable import HealthDelta

final class CanonicalPersonIDStoreTests: XCTestCase {
    func testGetOrCreateIsStableAndParsesAsUUID() throws {
        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)

        let store = CanonicalPersonIDStore(directoryURL: tmp)

        let a = try store.getOrCreate()
        let b = try store.getOrCreate()

        XCTAssertEqual(a, b)
        XCTAssertNotNil(UUID(uuidString: a))
        XCTAssertEqual(a, a.lowercased())
    }

    func testPersistsAcrossStoreInstances() throws {
        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)

        let store1 = CanonicalPersonIDStore(directoryURL: tmp)
        let a = try store1.getOrCreate()

        let store2 = CanonicalPersonIDStore(directoryURL: tmp)
        let b = try store2.getOrCreate()

        XCTAssertEqual(a, b)
    }
}

