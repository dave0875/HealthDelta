import Foundation
import XCTest

@testable import HealthDelta

final class ORINInsightsServiceTests: XCTestCase {
    func testFetchCurrentInsightsReturnsCardsOnSuccess() async throws {
        let payload = """
        {"status":"ok","dataset":"dataset_1","cards":[{"id":"c1","title":"ORIN Overview","body":"Body","disclaimer":"For education only. This is not medical advice.","sourceLabel":"orin/datasets/current","freshnessLabel":"Updated now"}]}
        """
        let session = FakeHTTPSession(
            queuedResponses: [
                .init(statusCode: 200, body: Data(payload.utf8)),
            ]
        )
        let service = ORINInsightsService(session: session)

        let result = try await service.fetchCurrentInsights(
            baseURLString: "http://orin.local:8080",
            bearerToken: "token"
        )

        XCTAssertEqual(
            result,
            .cards(
                [
                    InsightCard(
                        id: "c1",
                        title: "ORIN Overview",
                        body: "Body",
                        disclaimer: "For education only. This is not medical advice.",
                        sourceLabel: "orin/datasets/current",
                        freshnessLabel: "Updated now"
                    ),
                ]
            )
        )
    }

    func testFetchCurrentInsightsReturnsNoInsightsYet() async throws {
        let payload = """
        {"status":"no_insights_yet","detail":"Upload a run first.","cards":[]}
        """
        let session = FakeHTTPSession(
            queuedResponses: [
                .init(statusCode: 200, body: Data(payload.utf8)),
            ]
        )
        let service = ORINInsightsService(session: session)

        let result = try await service.fetchCurrentInsights(
            baseURLString: "http://orin.local:8080",
            bearerToken: "token"
        )

        XCTAssertEqual(result, .noInsightsYet("Upload a run first."))
    }

    func testFetchCurrentInsightsSurfacesBackendFailure() async throws {
        let payload = """
        {"error":"insights_failed","detail":"boom"}
        """
        let session = FakeHTTPSession(
            queuedResponses: [
                .init(statusCode: 500, body: Data(payload.utf8)),
            ]
        )
        let service = ORINInsightsService(session: session)

        await XCTAssertThrowsErrorAsync(
            try await service.fetchCurrentInsights(
                baseURLString: "http://orin.local:8080",
                bearerToken: "token"
            )
        ) { error in
            XCTAssertEqual(error.localizedDescription, "ORIN upload failed. insights_failed: boom")
        }
    }
}
