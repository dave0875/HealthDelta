import Foundation
import HealthKit
import XCTest

@testable import HealthDelta

final class AnchorStoreTests: XCTestCase {
    func testSerializeStableBytesForSameAnchorInput() throws {
        let store = AnchorStore(directoryURL: URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true))
        let anchor = HKQueryAnchor(fromValue: 123)

        let a = try store.serialize(anchor: anchor)
        let b = try store.serialize(anchor: anchor)
        XCTAssertEqual(a, b)
    }

    func testSaveLoadRoundtrip() throws {
        let dir = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let store = AnchorStore(directoryURL: dir)

        let key = "HKSampleType:HeartRate|predicate:none"
        let anchor = HKQueryAnchor(fromValue: 999)

        try store.save(anchor: anchor, forKey: key)
        let loaded = store.load(forKey: key)
        XCTAssertNotNil(loaded)

        let a = try store.serialize(anchor: anchor)
        let b = try store.serialize(anchor: loaded!)
        XCTAssertEqual(a, b)
    }

    func testMissingAndCorruptFilesHandledGracefully() throws {
        let dir = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let store = AnchorStore(directoryURL: dir)

        XCTAssertNil(store.load(forKey: "missing"))

        let key = "corrupt"
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = store.fileURL(forKey: key)
        try Data("not an anchor".utf8).write(to: url, options: [.atomic])
        XCTAssertNil(store.load(forKey: key))
    }
}

