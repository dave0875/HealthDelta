import Foundation
import HealthKit
import XCTest

@testable import HealthDelta

final class ManualHealthExportServiceTests: XCTestCase {
    func testRunManualExportRequestsAuthorizationAndRunsExporter() async throws {
        let auth = FakeHealthKitAuthorizer(result: true)
        let exporter = FakeIncrementalRunExporter()
        let layout = IOSExportLayout(
            baseDirectoryURL: URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
                .appendingPathComponent(UUID().uuidString, isDirectory: true)
        )
        let service = ManualHealthExportService(
            healthDataAvailable: { true },
            authorizationClient: auth,
            exporter: exporter,
            layoutProvider: { layout },
            runIDProvider: { "run_test" },
            sampleTypeProvider: {
                HKQuantityType.quantityType(forIdentifier: .stepCount)!
            }
        )

        let runID = try await service.runManualExport()

        XCTAssertEqual(runID, "run_test")
        XCTAssertEqual(auth.requestedTypeCount, 1)
        XCTAssertEqual(exporter.lastRunID, "run_test")
        XCTAssertEqual(exporter.lastKey, "steps")
        XCTAssertEqual(exporter.callCount, 1)
    }

    func testRunManualExportThrowsWhenAuthorizationDenied() async throws {
        let auth = FakeHealthKitAuthorizer(result: false)
        let exporter = FakeIncrementalRunExporter()
        let service = ManualHealthExportService(
            healthDataAvailable: { true },
            authorizationClient: auth,
            exporter: exporter,
            layoutProvider: {
                IOSExportLayout(baseDirectoryURL: URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true))
            },
            runIDProvider: { "run_test" },
            sampleTypeProvider: {
                HKQuantityType.quantityType(forIdentifier: .stepCount)!
            }
        )

        do {
            _ = try await service.runManualExport()
            XCTFail("expected authorization denial")
        } catch let error as ManualHealthExportError {
            XCTAssertEqual(error, .authorizationDenied)
        }

        XCTAssertEqual(exporter.callCount, 0)
    }
}

private final class FakeHealthKitAuthorizer: HealthKitAuthorizing {
    let result: Bool
    private(set) var requestedTypeCount = 0

    init(result: Bool) {
        self.result = result
    }

    func requestReadAuthorization(for types: Set<HKObjectType>) async throws -> Bool {
        requestedTypeCount = types.count
        return result
    }
}

private final class FakeIncrementalRunExporter: IncrementalRunExporting {
    private(set) var lastRunID: String?
    private(set) var lastKey: String?
    private(set) var callCount = 0

    func runOnce(
        runID: String,
        layout: IOSExportLayout,
        key: String,
        type: HKSampleType,
        predicate: NSPredicate?,
        limit: Int
    ) async throws -> Bool {
        lastRunID = runID
        lastKey = key
        callCount += 1
        return true
    }
}
