import CryptoKit
import Foundation

struct IOSExportManifestWriter {
    private let layout: IOSExportLayout

    init(layout: IOSExportLayout) {
        self.layout = layout
    }

    func writeManifestIfChanged(runID: String) throws {
        let data = try buildManifestData(runID: runID)
        let url = layout.manifestURL(runID: runID)

        if let existing = try? Data(contentsOf: url), existing == data {
            return
        }

        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url, options: [.atomic])
    }

    func buildManifestData(runID: String) throws -> Data {
        let fileEntries = try layout.ndjsonFilesForManifest(runID: runID).map { relPath -> [String: Any] in
            let url = layout.runDirectory(runID: runID).appendingPathComponent(relPath, isDirectory: false)
            let (sha, sizeBytes) = try sha256HexAndSize(url: url)
            return [
                "path": relPath,
                "size_bytes": sizeBytes,
                "sha256": sha,
            ]
        }

        let rowCounts: [String: Any] = try [
            "observations": layout.countNDJSONRows(url: layout.observationsNDJSONURL(runID: runID)),
        ]

        let manifest: [String: Any] = [
            "run_id": runID,
            "files": fileEntries,
            "row_counts": rowCounts,
        ]

        return try JSONSerialization.data(withJSONObject: manifest, options: [.sortedKeys])
    }

    private func sha256HexAndSize(url: URL) throws -> (String, Int) {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }

        var hasher = SHA256()
        var size = 0
        while true {
            let chunk = try handle.read(upToCount: 64 * 1024) ?? Data()
            if chunk.isEmpty { break }
            size += chunk.count
            hasher.update(data: chunk)
        }

        let digest = hasher.finalize()
        let hex = digest.map { String(format: "%02x", $0) }.joined()
        return (hex, size)
    }
}
