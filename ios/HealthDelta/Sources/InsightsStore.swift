import Foundation

struct InsightCard: Identifiable, Equatable {
    let id: String
    let title: String
    let body: String
    let disclaimer: String
    let sourceLabel: String
    let freshnessLabel: String
}

struct InsightsStore {
    private let fileManager: FileManager
    private let appDocumentsURL: URL

    init(
        fileManager: FileManager = .default,
        appDocumentsURL: URL? = nil
    ) {
        self.fileManager = fileManager
        self.appDocumentsURL = appDocumentsURL ?? fileManager.urls(for: .documentDirectory, in: .userDomainMask).first!
    }

    func loadLatestCards() throws -> [InsightCard] {
        let root = appDocumentsURL.appendingPathComponent("HealthDelta", isDirectory: true)
        guard let runDirectory = try latestRunDirectory(root: root) else {
            return []
        }

        var cards: [InsightCard] = []
        let runID = runDirectory.lastPathComponent

        if let noteCard = loadCard(
            fileURL: runDirectory.appendingPathComponent("note/doctor_note.md", isDirectory: false),
            title: "Doctor's Note",
            sourceLabel: "note/doctor_note.md",
            fallbackBody: "Your next sync will generate a one-screen summary of trends and risk flags.",
            runID: runID
        ) {
            cards.append(noteCard)
        }

        if let reportCard = loadCard(
            fileURL: runDirectory.appendingPathComponent("reports/summary.md", isDirectory: false),
            title: "Summary",
            sourceLabel: "reports/summary.md",
            fallbackBody: "Summary data appears after a completed operator run.",
            runID: runID
        ) {
            cards.append(reportCard)
        }

        return cards
    }

    private func loadCard(
        fileURL: URL,
        title: String,
        sourceLabel: String,
        fallbackBody: String,
        runID: String
    ) -> InsightCard? {
        guard fileManager.fileExists(atPath: fileURL.path) else {
            return nil
        }

        let bodyText = (try? String(contentsOf: fileURL, encoding: .utf8))
            .map { normalizeBody($0, fallback: fallbackBody) }
            ?? fallbackBody
        let modified = (try? fileManager.attributesOfItem(atPath: fileURL.path)[.modificationDate]) as? Date
        let freshness = modified.map { SyncStatusStore.dateFormatter.string(from: $0) } ?? "Unknown"

        return InsightCard(
            id: "\(runID)-\(sourceLabel)",
            title: title,
            body: bodyText,
            disclaimer: "For education only. This is not medical advice.",
            sourceLabel: sourceLabel,
            freshnessLabel: "Updated \(freshness) UTC"
        )
    }

    private func normalizeBody(_ raw: String, fallback: String) -> String {
        let cleaned = raw
            .components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .joined(separator: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if cleaned.isEmpty {
            return fallback
        }
        return cleaned
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
}
