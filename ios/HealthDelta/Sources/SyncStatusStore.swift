import Foundation

struct SyncStatusSnapshot: Equatable {
    let runID: String
    let generatedAt: Date?
    let deltaStart: Date?
    let deltaEnd: Date?
    let totalRows: Int
    let totalBytes: Int
    let fileCount: Int
    let anchorFiles: Int
    let rowCounts: [String: Int]
    let sourceFiles: [String]

    var hasData: Bool {
        totalRows > 0 || fileCount > 0
    }

    var lastSyncLabel: String {
        generatedAt.map { SyncStatusStore.displayDateString(from: $0) } ?? "Unknown"
    }

    var lastDeltaLabel: String {
        guard let deltaStart, let deltaEnd else { return "Not available yet" }
        return "\(SyncStatusStore.displayDateString(from: deltaStart)) -> \(SyncStatusStore.displayDateString(from: deltaEnd))"
    }

    func lastSyncLabel(timeZone: TimeZone, locale: Locale = .autoupdatingCurrent) -> String {
        guard let generatedAt else { return "Unknown" }
        return SyncStatusStore.displayDateString(from: generatedAt, timeZone: timeZone, locale: locale)
    }

    func lastDeltaLabel(timeZone: TimeZone, locale: Locale = .autoupdatingCurrent) -> String {
        guard let deltaStart, let deltaEnd else { return "Not available yet" }
        return "\(SyncStatusStore.displayDateString(from: deltaStart, timeZone: timeZone, locale: locale)) -> \(SyncStatusStore.displayDateString(from: deltaEnd, timeZone: timeZone, locale: locale))"
    }

    var anchorStatusLabel: String {
        if anchorFiles == 0 {
            return "No anchors saved yet"
        }
        let files = SyncStatusStore.numberFormatter.string(from: NSNumber(value: anchorFiles)) ?? "\(anchorFiles)"
        return "Anchors active (\(files) files)"
    }

    var totalRowsLabel: String {
        SyncStatusStore.numberFormatter.string(from: NSNumber(value: totalRows)) ?? "\(totalRows)"
    }

    var totalBytesLabel: String {
        ByteCountFormatter.string(fromByteCount: Int64(totalBytes), countStyle: .file)
    }
}

struct SyncStatusStore {
    enum LoadError: Error, Equatable {
        case noRunDirectory
        case malformedManifest
    }

    private let fileManager: FileManager
    private let appDocumentsURL: URL
    private let appSupportURL: URL

    init(
        fileManager: FileManager = .default,
        appDocumentsURL: URL? = nil,
        appSupportURL: URL? = nil
    ) {
        self.fileManager = fileManager
        self.appDocumentsURL = appDocumentsURL ?? fileManager.urls(for: .documentDirectory, in: .userDomainMask).first!
        self.appSupportURL = appSupportURL ?? fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
    }

    static let numberFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        return f
    }()

    static func makeDisplayDateFormatter(timeZone: TimeZone, locale: Locale = .autoupdatingCurrent) -> DateFormatter {
        let f = DateFormatter()
        f.dateStyle = .medium
        f.timeStyle = .short
        f.locale = locale
        f.timeZone = timeZone
        return f
    }

    static func displayDateString(
        from date: Date,
        timeZone: TimeZone = .autoupdatingCurrent,
        locale: Locale = .autoupdatingCurrent
    ) -> String {
        makeDisplayDateFormatter(timeZone: timeZone, locale: locale).string(from: date)
    }

    private static let iso8601WithFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let iso8601NoFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    func loadLatest() throws -> SyncStatusSnapshot {
        let healthDeltaRoot = appDocumentsURL.appendingPathComponent("HealthDelta", isDirectory: true)
        guard let runDirectory = try latestRunDirectory(root: healthDeltaRoot) else {
            throw LoadError.noRunDirectory
        }

        let manifestURL = runDirectory.appendingPathComponent("manifest.json", isDirectory: false)
        let data = try Data(contentsOf: manifestURL)
        let object = try JSONSerialization.jsonObject(with: data, options: [])
        guard let manifest = object as? [String: Any] else {
            throw LoadError.malformedManifest
        }

        let runID = (manifest["run_id"] as? String) ?? runDirectory.lastPathComponent
        let files = (manifest["files"] as? [[String: Any]]) ?? []
        let rowCounts = (manifest["row_counts"] as? [String: Any]) ?? [:]

        var totalBytes = 0
        var sourceFiles: [String] = []
        for file in files {
            if let x = file["size_bytes"] as? Int {
                totalBytes += x
            }
            if let p = file["path"] as? String {
                sourceFiles.append(p)
            }
        }

        var normalizedRowCounts: [String: Int] = [:]
        for (k, v) in rowCounts.sorted(by: { $0.key < $1.key }) {
            if let i = v as? Int {
                normalizedRowCounts[k] = i
            }
        }
        let totalRows = normalizedRowCounts.values.reduce(0, +)
        let (deltaStart, deltaEnd) = deltaWindow(runDirectory: runDirectory, files: files)

        let attrs = try? fileManager.attributesOfItem(atPath: manifestURL.path)
        let generatedAt = attrs?[.modificationDate] as? Date

        let anchorsDir = appSupportURL.appendingPathComponent("HealthDelta/anchors", isDirectory: true)
        let anchorFiles: Int
        if let list = try? fileManager.contentsOfDirectory(at: anchorsDir, includingPropertiesForKeys: nil) {
            anchorFiles = list.filter { !$0.hasDirectoryPath }.count
        } else {
            anchorFiles = 0
        }

        return SyncStatusSnapshot(
            runID: runID,
            generatedAt: generatedAt,
            deltaStart: deltaStart,
            deltaEnd: deltaEnd,
            totalRows: totalRows,
            totalBytes: totalBytes,
            fileCount: files.count,
            anchorFiles: anchorFiles,
            rowCounts: normalizedRowCounts,
            sourceFiles: sourceFiles.sorted()
        )
    }

    private func latestRunDirectory(root: URL) throws -> URL? {
        guard fileManager.fileExists(atPath: root.path) else {
            return nil
        }
        let candidates = try fileManager.contentsOfDirectory(
            at: root,
            includingPropertiesForKeys: [.contentModificationDateKey, .isDirectoryKey],
            options: [.skipsHiddenFiles]
        )
        let runDirs = candidates.filter { url in
            var isDir: ObjCBool = false
            guard fileManager.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue else {
                return false
            }
            return fileManager.fileExists(atPath: url.appendingPathComponent("manifest.json").path)
        }
        return runDirs.max { lhs, rhs in
            let la = (try? lhs.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let ra = (try? rhs.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return la < ra
        }
    }

    private func deltaWindow(runDirectory: URL, files: [[String: Any]]) -> (Date?, Date?) {
        var minStart: Date?
        var maxEnd: Date?

        for file in files {
            guard let path = file["path"] as? String, path.hasSuffix(".ndjson") else {
                continue
            }
            let ndjsonURL = runDirectory.appendingPathComponent(path, isDirectory: false)
            guard let text = try? String(contentsOf: ndjsonURL, encoding: .utf8) else {
                continue
            }

            for rawLine in text.split(separator: "\n") {
                let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !line.isEmpty, let data = line.data(using: .utf8) else {
                    continue
                }
                guard
                    let object = try? JSONSerialization.jsonObject(with: data, options: []),
                    let row = object as? [String: Any]
                else {
                    continue
                }

                if let value = row["start_time"] as? String, let parsed = parseISO8601(value) {
                    minStart = min(minStart ?? parsed, parsed)
                }
                if let value = row["end_time"] as? String, let parsed = parseISO8601(value) {
                    maxEnd = max(maxEnd ?? parsed, parsed)
                }
            }
        }

        return (minStart, maxEnd)
    }

    private func parseISO8601(_ value: String) -> Date? {
        if let d = Self.iso8601WithFractional.date(from: value) {
            return d
        }
        return Self.iso8601NoFractional.date(from: value)
    }
}
