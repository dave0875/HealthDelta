import CryptoKit
import Foundation

protocol RunUploading {
    @discardableResult
    func uploadRun(runID: String, baseURLString: String, bearerToken: String) async throws -> String
}

enum RunUploadError: LocalizedError, Equatable {
    case missingRun
    case invalidBaseURL
    case missingToken
    case invalidServerResponse
    case uploadFailed(String)
    case finalizeMissingDataset

    var errorDescription: String? {
        switch self {
        case .missingRun:
            return "No completed local run is available to upload yet."
        case .invalidBaseURL:
            return "Enter a valid ORIN upload endpoint URL."
        case .missingToken:
            return "Enter the ORIN upload token before uploading."
        case .invalidServerResponse:
            return "The ORIN server returned an invalid response."
        case .uploadFailed(let detail):
            return "ORIN upload failed. \(detail)"
        case .finalizeMissingDataset:
            return "ORIN finalized the upload but did not return a dataset identifier."
        }
    }
}

protocol URLSessionUploading {
    func data(for request: URLRequest) async throws -> (Data, URLResponse)
    func upload(for request: URLRequest, from bodyData: Data) async throws -> (Data, URLResponse)
}

extension URLSession: URLSessionUploading {}

struct RunArchive {
    let url: URL
    let totalSize: Int
    let sha256: String
}

protocol RunArchiveBuilding {
    func buildArchive(runID: String, layout: IOSExportLayout) throws -> RunArchive
}

final class ZipRunArchiveBuilder: RunArchiveBuilding {
    private let fileManager: FileManager
    private let tempDirectory: URL

    init(fileManager: FileManager = .default, tempDirectory: URL = FileManager.default.temporaryDirectory) {
        self.fileManager = fileManager
        self.tempDirectory = tempDirectory
    }

    func buildArchive(runID: String, layout: IOSExportLayout) throws -> RunArchive {
        let runDirectory = layout.runDirectory(runID: runID)
        guard fileManager.fileExists(atPath: runDirectory.path) else {
            throw RunUploadError.missingRun
        }

        let archiveURL = tempDirectory
            .appendingPathComponent("HealthDeltaUpload-\(UUID().uuidString)", isDirectory: false)
            .appendingPathExtension("zip")
        if fileManager.fileExists(atPath: archiveURL.path) {
            try fileManager.removeItem(at: archiveURL)
        }

        let data = try buildZipData(runDirectory: runDirectory, runID: runID)
        try data.write(to: archiveURL, options: .atomic)
        let sha = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        return RunArchive(url: archiveURL, totalSize: data.count, sha256: sha)
    }

    private func buildZipData(runDirectory: URL, runID: String) throws -> Data {
        let entries = try archiveEntries(runDirectory: runDirectory, runID: runID)
        var archive = Data()
        var centralDirectory = Data()

        for entry in entries {
            let localOffset = UInt32(archive.count)
            archive.appendLEUInt32(0x04034b50)
            archive.appendLEUInt16(20)
            archive.appendLEUInt16(0)
            archive.appendLEUInt16(0)
            archive.appendLEUInt16(0)
            archive.appendLEUInt16(0)
            archive.appendLEUInt32(entry.crc32)
            archive.appendLEUInt32(UInt32(entry.data.count))
            archive.appendLEUInt32(UInt32(entry.data.count))
            archive.appendLEUInt16(UInt16(entry.pathData.count))
            archive.appendLEUInt16(0)
            archive.append(entry.pathData)
            archive.append(entry.data)

            centralDirectory.appendLEUInt32(0x02014b50)
            centralDirectory.appendLEUInt16(20)
            centralDirectory.appendLEUInt16(20)
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt32(entry.crc32)
            centralDirectory.appendLEUInt32(UInt32(entry.data.count))
            centralDirectory.appendLEUInt32(UInt32(entry.data.count))
            centralDirectory.appendLEUInt16(UInt16(entry.pathData.count))
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt16(0)
            centralDirectory.appendLEUInt32(0)
            centralDirectory.appendLEUInt32(localOffset)
            centralDirectory.append(entry.pathData)
        }

        let centralDirectoryOffset = UInt32(archive.count)
        archive.append(centralDirectory)
        archive.appendLEUInt32(0x06054b50)
        archive.appendLEUInt16(0)
        archive.appendLEUInt16(0)
        archive.appendLEUInt16(UInt16(entries.count))
        archive.appendLEUInt16(UInt16(entries.count))
        archive.appendLEUInt32(UInt32(centralDirectory.count))
        archive.appendLEUInt32(centralDirectoryOffset)
        archive.appendLEUInt16(0)
        return archive
    }

    private func archiveEntries(runDirectory: URL, runID: String) throws -> [(pathData: Data, data: Data, crc32: UInt32)] {
        var out: [(String, Data, UInt32)] = []
        for relativePath in try fileManager.subpathsOfDirectory(atPath: runDirectory.path).sorted() {
            let fileURL = runDirectory.appendingPathComponent(relativePath, isDirectory: false)
            let values = try fileURL.resourceValues(forKeys: [.isRegularFileKey])
            guard values.isRegularFile == true else {
                continue
            }
            let data = try Data(contentsOf: fileURL)
            let zipPath = "\(runID)/\(relativePath)"
            out.append((zipPath, data, Self.crc32(data)))
        }

        return out
            .sorted { $0.0 < $1.0 }
            .compactMap { path, data, crc32 in
                guard let pathData = path.data(using: .utf8) else {
                    return nil
                }
                return (pathData, data, crc32)
            }
    }

    private static func crc32(_ data: Data) -> UInt32 {
        var crc: UInt32 = 0xFFFF_FFFF
        for byte in data {
            let index = Int((crc ^ UInt32(byte)) & 0xFF)
            crc = Self.crc32Table[index] ^ (crc >> 8)
        }
        return crc ^ 0xFFFF_FFFF
    }

    private static let crc32Table: [UInt32] = {
        (0..<256).map { value in
            var crc = UInt32(value)
            for _ in 0..<8 {
                if crc & 1 == 1 {
                    crc = 0xEDB8_8320 ^ (crc >> 1)
                } else {
                    crc >>= 1
                }
            }
            return crc
        }
    }()
}

private struct CreateUploadSessionResponse: Decodable {
    let id: String
}

private struct CreateUploadSessionRequest: Encodable {
    let totalSize: Int
    let sha256: String

    private enum CodingKeys: String, CodingKey {
        case totalSize = "total_size"
        case sha256
    }
}

private struct FinalizeUploadSessionResponse: Decodable {
    let finalizedDataset: String?

    private enum CodingKeys: String, CodingKey {
        case finalizedDataset = "finalized_dataset"
    }
}

private struct UploadPlaneErrorResponse: Decodable {
    let error: String?
    let detail: String?
}

final class ORINUploadService: RunUploading {
    private let layoutProvider: () throws -> IOSExportLayout
    private let archiveBuilder: RunArchiveBuilding
    private let session: URLSessionUploading
    private let fileManager: FileManager
    private let chunkSize: Int

    init(
        layoutProvider: @escaping () throws -> IOSExportLayout,
        archiveBuilder: RunArchiveBuilding,
        session: URLSessionUploading,
        fileManager: FileManager = .default,
        chunkSize: Int = 512 * 1024
    ) {
        self.layoutProvider = layoutProvider
        self.archiveBuilder = archiveBuilder
        self.session = session
        self.fileManager = fileManager
        self.chunkSize = chunkSize
    }

    static func live() -> ORINUploadService {
        ORINUploadService(
            layoutProvider: { try IOSExportLayout.defaultInAppSandbox() },
            archiveBuilder: ZipRunArchiveBuilder(),
            session: URLSession.shared
        )
    }

    @discardableResult
    func uploadRun(runID: String, baseURLString: String, bearerToken: String) async throws -> String {
        let trimmedURL = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let baseURL = normalizedBaseURL(trimmedURL) else {
            throw RunUploadError.invalidBaseURL
        }

        let token = bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            throw RunUploadError.missingToken
        }

        let layout = try layoutProvider()
        let archive = try archiveBuilder.buildArchive(runID: runID, layout: layout)
        defer {
            try? fileManager.removeItem(at: archive.url)
        }

        let sessionID = try await createSession(baseURL: baseURL, bearerToken: token, archive: archive)
        try await uploadChunks(baseURL: baseURL, bearerToken: token, sessionID: sessionID, archiveURL: archive.url)
        return try await finalizeSession(baseURL: baseURL, bearerToken: token, sessionID: sessionID)
    }

    private func normalizedBaseURL(_ raw: String) -> URL? {
        guard let url = URL(string: raw), let scheme = url.scheme, (scheme == "http" || scheme == "https") else {
            return nil
        }
        return url
    }

    private func createSession(baseURL: URL, bearerToken: String, archive: RunArchive) async throws -> String {
        var request = URLRequest(url: baseURL.appendingPathComponent("upload-sessions"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(CreateUploadSessionRequest(totalSize: archive.totalSize, sha256: archive.sha256))

        let (data, response) = try await session.data(for: request)
        try ensureSuccessful(response: response, data: data, allowedStatuses: [201])
        let decoded = try JSONDecoder().decode(CreateUploadSessionResponse.self, from: data)
        return decoded.id
    }

    private func uploadChunks(baseURL: URL, bearerToken: String, sessionID: String, archiveURL: URL) async throws {
        let handle = try FileHandle(forReadingFrom: archiveURL)
        defer { try? handle.close() }

        var index = 0
        while true {
            let chunk = try handle.read(upToCount: chunkSize) ?? Data()
            if chunk.isEmpty {
                break
            }

            var request = URLRequest(url: baseURL.appendingPathComponent("upload-sessions/\(sessionID)/chunks/\(index)"))
            request.httpMethod = "PUT"
            request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization")
            request.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type")

            let (data, response) = try await session.upload(for: request, from: chunk)
            try ensureSuccessful(response: response, data: data, allowedStatuses: [200])
            index += 1
        }
    }

    private func finalizeSession(baseURL: URL, bearerToken: String, sessionID: String) async throws -> String {
        var request = URLRequest(url: baseURL.appendingPathComponent("upload-sessions/\(sessionID)/finalize"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)

        let (data, response) = try await session.data(for: request)
        try ensureSuccessful(response: response, data: data, allowedStatuses: [200])
        let decoded = try JSONDecoder().decode(FinalizeUploadSessionResponse.self, from: data)
        guard let finalizedDataset = decoded.finalizedDataset, !finalizedDataset.isEmpty else {
            throw RunUploadError.finalizeMissingDataset
        }
        return finalizedDataset
    }

    private func ensureSuccessful(response: URLResponse, data: Data, allowedStatuses: Set<Int>) throws {
        guard let http = response as? HTTPURLResponse else {
            throw RunUploadError.invalidServerResponse
        }
        guard allowedStatuses.contains(http.statusCode) else {
            if let decoded = try? JSONDecoder().decode(UploadPlaneErrorResponse.self, from: data) {
                let detail = [decoded.error, decoded.detail].compactMap { $0 }.joined(separator: ": ")
                throw RunUploadError.uploadFailed(detail.isEmpty ? "HTTP \(http.statusCode)" : detail)
            }
            throw RunUploadError.uploadFailed("HTTP \(http.statusCode)")
        }
    }
}

private extension Data {
    mutating func appendLEUInt16(_ value: UInt16) {
        var little = value.littleEndian
        Swift.withUnsafeBytes(of: &little) { bytes in
            append(contentsOf: bytes)
        }
    }

    mutating func appendLEUInt32(_ value: UInt32) {
        var little = value.littleEndian
        Swift.withUnsafeBytes(of: &little) { bytes in
            append(contentsOf: bytes)
        }
    }
}
