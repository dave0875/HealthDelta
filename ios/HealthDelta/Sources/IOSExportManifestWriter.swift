import CryptoKit
import Foundation

struct IOSExportManifestWriter {
    private let layout: IOSExportLayout

    init(layout: IOSExportLayout) {
        self.layout = layout
    }

    func writeManifestIfChanged(
        runID: String,
        deltaStart: Date? = nil,
        deltaEnd: Date? = nil
    ) throws {
        let url = layout.manifestURL(runID: runID)
        let existingWindow = existingDeltaWindow(url: url)
        let mergedStart = mergeStart(existing: existingWindow.start, incoming: deltaStart)
        let mergedEnd = mergeEnd(existing: existingWindow.end, incoming: deltaEnd)
        let data = try buildManifestData(runID: runID, deltaStart: mergedStart, deltaEnd: mergedEnd)

        if let existing = try? Data(contentsOf: url), existing == data {
            return
        }

        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url, options: [.atomic])
    }

    func buildManifestData(
        runID: String,
        deltaStart: Date? = nil,
        deltaEnd: Date? = nil
    ) throws -> Data {
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

        var manifest: [String: Any] = [
            "run_id": runID,
            "files": fileEntries,
            "row_counts": rowCounts,
        ]
        if let deltaStart {
            manifest["delta_start"] = iso8601(deltaStart)
        }
        if let deltaEnd {
            manifest["delta_end"] = iso8601(deltaEnd)
        }

        return try JSONSerialization.data(withJSONObject: manifest, options: [.sortedKeys])
    }

    private func iso8601(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: date)
    }

    private func existingDeltaWindow(url: URL) -> (start: Date?, end: Date?) {
        guard
            let data = try? Data(contentsOf: url),
            let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return (nil, nil)
        }
        return (
            parseISO8601(object["delta_start"] as? String),
            parseISO8601(object["delta_end"] as? String)
        )
    }

    private func mergeStart(existing: Date?, incoming: Date?) -> Date? {
        switch (existing, incoming) {
        case let (lhs?, rhs?):
            return min(lhs, rhs)
        case let (lhs?, nil):
            return lhs
        case let (nil, rhs?):
            return rhs
        case (nil, nil):
            return nil
        }
    }

    private func mergeEnd(existing: Date?, incoming: Date?) -> Date? {
        switch (existing, incoming) {
        case let (lhs?, rhs?):
            return max(lhs, rhs)
        case let (lhs?, nil):
            return lhs
        case let (nil, rhs?):
            return rhs
        case (nil, nil):
            return nil
        }
    }

    private func parseISO8601(_ value: String?) -> Date? {
        guard let value else {
            return nil
        }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: value)
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
