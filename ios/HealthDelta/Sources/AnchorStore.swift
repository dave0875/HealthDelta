import CryptoKit
import Foundation
import HealthKit

final class AnchorStore {
    enum StoreError: Error {
        case invalidKey
        case io(Error)
    }

    private static let magic = Data("HDANCHOR".utf8)
    private static let version: UInt8 = 1

    private let directoryURL: URL
    private let fileManager: FileManager

    init(directoryURL: URL? = nil, fileManager: FileManager = .default) {
        self.fileManager = fileManager

        if let directoryURL {
            self.directoryURL = directoryURL
            return
        }

        let base = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        self.directoryURL = base.appendingPathComponent("HealthDelta/anchors", isDirectory: true)
    }

    func save(anchor: HKQueryAnchor, forKey key: String) throws {
        guard !key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw StoreError.invalidKey }
        try ensureDirectory()

        let payload = try serialize(anchor: anchor)
        let url = fileURL(forKey: key)
        do {
            try payload.write(to: url, options: [.atomic])
        } catch {
            throw StoreError.io(error)
        }
    }

    func load(forKey key: String) -> HKQueryAnchor? {
        guard !key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
        let url = fileURL(forKey: key)
        guard fileManager.fileExists(atPath: url.path) else { return nil }
        guard let data = try? Data(contentsOf: url) else { return nil }
        return deserialize(data: data)
    }

    func delete(forKey key: String) {
        guard !key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        let url = fileURL(forKey: key)
        try? fileManager.removeItem(at: url)
    }

    func serialize(anchor: HKQueryAnchor) throws -> Data {
        let archived: Data
        do {
            archived = try NSKeyedArchiver.archivedData(withRootObject: anchor, requiringSecureCoding: true)
        } catch {
            throw StoreError.io(error)
        }

        var out = Data()
        out.append(Self.magic)
        out.append(Self.version)
        out.append(archived)
        return out
    }

    func deserialize(data: Data) -> HKQueryAnchor? {
        let headerLen = Self.magic.count + 1
        guard data.count >= headerLen else { return nil }
        guard data.prefix(Self.magic.count) == Self.magic else { return nil }
        guard data[Self.magic.count] == Self.version else { return nil }

        let archived = data.suffix(from: headerLen)
        return try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: archived)
    }

    func fileURL(forKey key: String) -> URL {
        let digest = SHA256.hash(data: Data(key.utf8))
        let hex = digest.map { String(format: "%02x", $0) }.joined()
        return directoryURL.appendingPathComponent("\(hex).bin", isDirectory: false)
    }

    private func ensureDirectory() throws {
        do {
            try fileManager.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        } catch {
            throw StoreError.io(error)
        }
    }
}

