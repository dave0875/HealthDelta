import Foundation
import XCTest

@testable import HealthDelta

struct QueuedHTTPResponse {
    let statusCode: Int
    let body: Data
}

final class FakeHTTPSession: URLSessionUploading {
    var queuedResponses: [QueuedHTTPResponse]

    init(queuedResponses: [QueuedHTTPResponse]) {
        self.queuedResponses = queuedResponses
    }

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        try dequeueResponse(for: request)
    }

    func upload(for request: URLRequest, from bodyData: Data) async throws -> (Data, URLResponse) {
        try dequeueResponse(for: request)
    }

    private func dequeueResponse(for request: URLRequest) throws -> (Data, URLResponse) {
        guard !queuedResponses.isEmpty else {
            throw URLError(.badServerResponse)
        }
        let next = queuedResponses.removeFirst()
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "http://localhost")!,
            statusCode: next.statusCode,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        return (next.body, response)
    }
}

func XCTAssertThrowsErrorAsync<T>(
    _ expression: @autoclosure () async throws -> T,
    _ errorHandler: (Error) -> Void,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        _ = try await expression()
        XCTFail("Expected error to be thrown", file: file, line: line)
    } catch {
        errorHandler(error)
    }
}
