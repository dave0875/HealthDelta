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

    func ensureDirectories(runID: String) throws {
        try FileManager.default.createDirectory(at: ndjsonDirectory(runID: runID), withIntermediateDirectories: true)
    }
}

