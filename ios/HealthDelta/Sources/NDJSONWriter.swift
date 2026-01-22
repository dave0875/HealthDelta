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
        fm.createFile(atPath: url.path, contents: nil)

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

