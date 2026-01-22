import Foundation
import XCTest

@testable import HealthDelta

final class IOSExportLayoutTests: XCTestCase {
    func testOutputPathsAreDeterministicForFixedRunID() {
        let tmp = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let base = tmp.appendingPathComponent("HealthDelta", isDirectory: true)

        let layout = IOSExportLayout(baseDirectoryURL: base)

        let a = layout.observationsNDJSONURL(runID: "run_1")
        let b = layout.observationsNDJSONURL(runID: "run_1")

        XCTAssertEqual(a, b)
        XCTAssertEqual(
            a,
            base
                .appendingPathComponent("run_1", isDirectory: true)
                .appendingPathComponent("ndjson", isDirectory: true)
                .appendingPathComponent("observations.ndjson", isDirectory: false)
        )
    }
}

