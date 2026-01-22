import Foundation

final class NDJSONWriter {
    enum WriteError: Error {
        case invalidJSONObject
        case io(Error)
    }

    func encodeLine(_ obj: Any) throws -> Data {
        guard JSONSerialization.isValidJSONObject(obj) else { throw WriteError.invalidJSONObject }
        do {
            var data = try JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys])
            data.append(0x0A) // newline
            return data
        } catch {
            throw WriteError.io(error)
        }
    }

    func appendLines(_ objects: [Any], to url: URL) throws {
        let fm = FileManager.default
        try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)

        // Best-effort atomic file creation on first write.
        if !fm.fileExists(atPath: url.path) {
            do {
                var data = Data()
                data.reserveCapacity(objects.count * 128)
                for obj in objects {
                    data.append(try encodeLine(obj))
                }
                try data.write(to: url, options: [.atomic])
                return
            } catch {
                throw WriteError.io(error)
            }
        }

        do {
            let handle = try FileHandle(forWritingTo: url)
            defer { try? handle.close() }
            try handle.seekToEnd()
            for obj in objects {
                let line = try encodeLine(obj)
                try handle.write(contentsOf: line)
            }
        } catch {
            throw WriteError.io(error)
        }
    }
}
