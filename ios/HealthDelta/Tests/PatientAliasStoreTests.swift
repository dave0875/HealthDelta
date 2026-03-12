import Foundation
import XCTest

@testable import HealthDelta

final class PatientAliasStoreTests: XCTestCase {
    func testSaveAndLoadAliasRoundTrip() throws {
        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)

        let store = PatientAliasStore(directoryURL: tmp)
        try store.saveAlias("Dad", for: "person-1")

        let aliases = try store.loadAliases()
        XCTAssertEqual(aliases["person-1"], "Dad")
    }

    func testSavingBlankAliasClearsEntry() throws {
        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)

        let store = PatientAliasStore(directoryURL: tmp)
        try store.saveAlias("Dad", for: "person-1")
        try store.saveAlias("   ", for: "person-1")

        let aliases = try store.loadAliases()
        XCTAssertNil(aliases["person-1"])
    }
}
