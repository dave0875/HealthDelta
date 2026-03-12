import Foundation
import XCTest

@testable import HealthDelta

final class ORINPatientScopeServiceTests: XCTestCase {
    func testFetchCurrentPatientsReturnsShareSafeOptions() async throws {
        let payload = """
        {"dataset":"dataset_1","patients":[{"canonical_person_id":"person-a","display_label":"Patient 1","row_count":1200,"min_event_time":"2026-03-01T00:00:00Z","max_event_time":"2026-03-11T00:00:00Z"},{"canonical_person_id":"unresolved","display_label":"Unresolved records","row_count":50,"min_event_time":"2026-03-10T00:00:00Z","max_event_time":"2026-03-11T00:00:00Z"}]}
        """
        let session = FakeHTTPSession(
            queuedResponses: [
                .init(statusCode: 200, body: Data(payload.utf8)),
            ]
        )
        let service = ORINPatientScopeService(session: session)

        let result = try await service.fetchCurrentPatients(
            baseURLString: "http://orin.local:8080",
            bearerToken: "token"
        )

        XCTAssertEqual(
            result,
            [
                ORINPatientScope(
                    canonicalPersonID: "person-a",
                    displayLabel: "Patient 1",
                    rowCount: 1200,
                    minEventTime: "2026-03-01T00:00:00Z",
                    maxEventTime: "2026-03-11T00:00:00Z"
                ),
                ORINPatientScope(
                    canonicalPersonID: "unresolved",
                    displayLabel: "Unresolved records",
                    rowCount: 50,
                    minEventTime: "2026-03-10T00:00:00Z",
                    maxEventTime: "2026-03-11T00:00:00Z"
                ),
            ]
        )
    }

    func testFetchCurrentPatientsUsesPatientsCurrentPath() async throws {
        let payload = """
        {"dataset":"dataset_1","patients":[]}
        """
        let session = FakeHTTPSession(
            queuedResponses: [
                .init(statusCode: 200, body: Data(payload.utf8)),
            ]
        )
        let service = ORINPatientScopeService(session: session)

        _ = try await service.fetchCurrentPatients(
            baseURLString: "http://orin.local:8080",
            bearerToken: "token"
        )

        let url = try XCTUnwrap(session.seenRequests.last?.url)
        XCTAssertEqual(url.path, "/patients/current")
    }
}
