import Foundation

struct IOSExportLayout {
    let baseDirectoryURL: URL

    init(baseDirectoryURL: URL) {
        self.baseDirectoryURL = baseDirectoryURL
    }

    static func defaultInAppSandbox() throws -> IOSExportLayout {
        let fm = FileManager.default
        guard let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first else {
            throw CocoaError(.fileNoSuchFile)
        }
        return IOSExportLayout(baseDirectoryURL: docs.appendingPathComponent("HealthDelta", isDirectory: true))
    }

    func runDirectory(runID: String) -> URL {
        baseDirectoryURL.appendingPathComponent(runID, isDirectory: true)
    }

    func ndjsonDirectory(runID: String) -> URL {
        runDirectory(runID: runID).appendingPathComponent("ndjson", isDirectory: true)
    }

    func observationsNDJSONURL(runID: String) -> URL {
        ndjsonDirectory(runID: runID).appendingPathComponent("observations.ndjson", isDirectory: false)
    }

    func manifestURL(runID: String) -> URL {
        runDirectory(runID: runID).appendingPathComponent("manifest.json", isDirectory: false)
    }

    func ndjsonFilesForManifest(runID: String) throws -> [String] {
        // Relative paths under the run directory (stable ordering).
        let paths = [
            "ndjson/observations.ndjson",
        ]

        let base = runDirectory(runID: runID)
        let existing = paths.filter { rel in
            FileManager.default.fileExists(atPath: base.appendingPathComponent(rel, isDirectory: false).path)
        }
        return existing.sorted()
    }

    func countNDJSONRows(url: URL) throws -> Int {
        guard FileManager.default.fileExists(atPath: url.path) else {
            return 0
        }
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }

        var count = 0
        while true {
            let chunk = try handle.read(upToCount: 64 * 1024) ?? Data()
            if chunk.isEmpty { break }
            count += chunk.reduce(0) { $0 + ($1 == 0x0A ? 1 : 0) }
        }
        return count
    }

    func ensureDirectories(runID: String) throws {
        try FileManager.default.createDirectory(at: ndjsonDirectory(runID: runID), withIntermediateDirectories: true)
    }
}
