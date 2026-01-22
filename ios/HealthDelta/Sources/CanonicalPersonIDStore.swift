import Foundation

final class CanonicalPersonIDStore {
    private let fileURL: URL

    init(fileURL: URL) {
        self.fileURL = fileURL
    }

    convenience init(directoryURL: URL) {
        self.init(fileURL: directoryURL.appendingPathComponent("canonical_person_id.txt", isDirectory: false))
    }

    static func defaultInAppSandbox() throws -> CanonicalPersonIDStore {
        let fm = FileManager.default
        guard let dir = fm.urls(for: .documentDirectory, in: .userDomainMask).first else {
            throw CocoaError(.fileNoSuchFile)
        }
        return CanonicalPersonIDStore(directoryURL: dir.appendingPathComponent("HealthDelta", isDirectory: true))
    }

    func getOrCreate() throws -> String {
        if let existing = try load() {
            return existing
        }

        let id = UUID().uuidString.lowercased()
        try save(id)
        return id
    }

    private func load() throws -> String? {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            return nil
        }
        let data = try Data(contentsOf: fileURL)
        guard var s = String(data: data, encoding: .utf8) else {
            return nil
        }
        s = s.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty else { return nil }
        return s.lowercased()
    }

    private func save(_ id: String) throws {
        let fm = FileManager.default
        try fm.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)

        guard let data = (id + "\n").data(using: .utf8) else {
            throw CocoaError(.fileWriteUnknown)
        }
        try data.write(to: fileURL, options: [.atomic])
    }
}

