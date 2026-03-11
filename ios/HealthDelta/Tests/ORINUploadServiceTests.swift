import Foundation
import XCTest

@testable import HealthDelta

final class ORINUploadServiceTests: XCTestCase {
    func testUploadRunCreatesSessionUploadsChunksAndFinalizes() async throws {
        let archiveURL = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: false)
            .appendingPathExtension("zip")
        let archiveBytes = Data("hello-world".utf8)
        try archiveBytes.write(to: archiveURL)
        defer { try? FileManager.default.removeItem(at: archiveURL) }

        let archive = RunArchive(url: archiveURL, totalSize: archiveBytes.count, sha256: "abc123")
        let session = FakeURLSessionUploader()
        let service = ORINUploadService(
            layoutProvider: {
                IOSExportLayout(baseDirectoryURL: URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true))
            },
            archiveBuilder: FakeRunArchiveBuilder(archive: archive),
            session: session,
            chunkSize: 5
        )

        let dataset = try await service.uploadRun(
            runID: "run_test",
            baseURLString: "http://orin.local:8080",
            bearerToken: "secret"
        )

        XCTAssertEqual(dataset, "dataset_test")
        XCTAssertEqual(session.createdSessionPayload?["total_size"] as? Int, archiveBytes.count)
        XCTAssertEqual(session.createdSessionPayload?["sha256"] as? String, "abc123")
        XCTAssertEqual(session.chunkBodies, [Data("hello".utf8), Data("-worl".utf8), Data("d".utf8)])
        XCTAssertEqual(session.finalizedSessionID, "sess123")
    }

    func testUploadRunRejectsMissingToken() async throws {
        let service = ORINUploadService(
            layoutProvider: {
                IOSExportLayout(baseDirectoryURL: URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true))
            },
            archiveBuilder: FakeRunArchiveBuilder(error: RunUploadError.missingRun),
            session: FakeURLSessionUploader()
        )

        do {
            _ = try await service.uploadRun(
                runID: "run_test",
                baseURLString: "http://orin.local:8080",
                bearerToken: ""
            )
            XCTFail("expected missing token")
        } catch let error as RunUploadError {
            XCTAssertEqual(error, .missingToken)
        }
    }
}

private final class FakeRunArchiveBuilder: RunArchiveBuilding {
    let archive: RunArchive?
    let error: Error?

    init(archive: RunArchive? = nil, error: Error? = nil) {
        self.archive = archive
        self.error = error
    }

    func buildArchive(runID: String, layout: IOSExportLayout) throws -> RunArchive {
        if let error {
            throw error
        }
        return archive!
    }
}

private final class FakeURLSessionUploader: URLSessionUploading {
    private(set) var createdSessionPayload: [String: Any]?
    private(set) var chunkBodies: [Data] = []
    private(set) var finalizedSessionID: String?

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        let url = try XCTUnwrap(request.url)
        if request.httpMethod == "POST", url.path == "/upload-sessions" {
            if let body = request.httpBody,
               let object = try JSONSerialization.jsonObject(with: body) as? [String: Any] {
                createdSessionPayload = object
            }
            return (
                Data(#"{"id":"sess123"}"#.utf8),
                HTTPURLResponse(url: url, statusCode: 201, httpVersion: nil, headerFields: nil)!
            )
        }

        if request.httpMethod == "POST", url.path == "/upload-sessions/sess123/finalize" {
            finalizedSessionID = "sess123"
            return (
                Data(#"{"finalized_dataset":"dataset_test"}"#.utf8),
                HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: nil)!
            )
        }

        XCTFail("unexpected request: \(request.httpMethod ?? "") \(url.path)")
        return (
            Data(),
            HTTPURLResponse(url: url, statusCode: 500, httpVersion: nil, headerFields: nil)!
        )
    }

    func upload(for request: URLRequest, from bodyData: Data) async throws -> (Data, URLResponse) {
        let url = try XCTUnwrap(request.url)
        chunkBodies.append(bodyData)
        return (
            Data(#"{"status":"uploading"}"#.utf8),
            HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: nil)!
        )
    }
}
