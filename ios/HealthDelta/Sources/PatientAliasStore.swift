import Foundation

final class PatientAliasStore {
    private let fileURL: URL

    init(fileURL: URL) {
        self.fileURL = fileURL
    }

    convenience init(directoryURL: URL) {
        self.init(fileURL: directoryURL.appendingPathComponent("patient_aliases.json", isDirectory: false))
    }

    static func defaultInAppSandbox() throws -> PatientAliasStore {
        let fm = FileManager.default
        guard let dir = fm.urls(for: .documentDirectory, in: .userDomainMask).first else {
            throw CocoaError(.fileNoSuchFile)
        }
        return PatientAliasStore(directoryURL: dir.appendingPathComponent("HealthDelta", isDirectory: true))
    }

    func loadAliases() throws -> [String: String] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            return [:]
        }
        let data = try Data(contentsOf: fileURL)
        let decoded = try JSONDecoder().decode([String: String].self, from: data)
        return decoded.reduce(into: [:]) { result, entry in
            let key = entry.key.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let value = entry.value.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !key.isEmpty, !value.isEmpty else {
                return
            }
            result[key] = value
        }
    }

    func saveAlias(_ alias: String, for canonicalPersonID: String) throws {
        let trimmedAlias = alias.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedID = canonicalPersonID.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !trimmedID.isEmpty else {
            throw CocoaError(.fileWriteUnknown)
        }

        var aliases = try loadAliases()
        if trimmedAlias.isEmpty {
            aliases.removeValue(forKey: trimmedID)
        } else {
            aliases[trimmedID] = trimmedAlias
        }
        try persist(aliases)
    }

    private func persist(_ aliases: [String: String]) throws {
        let fm = FileManager.default
        try fm.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        let sorted = Dictionary(uniqueKeysWithValues: aliases.sorted { $0.key < $1.key })
        let data = try JSONEncoder().encode(sorted)
        try data.write(to: fileURL, options: [.atomic])
    }
}
