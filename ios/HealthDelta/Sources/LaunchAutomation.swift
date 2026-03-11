import Foundation

struct LaunchAutomationConfig: Equatable {
    let baseURLString: String
    let bearerToken: String
}

enum LaunchAutomation {
    struct FileConfigProvider {
        let configURL: () throws -> URL?

        static let live = FileConfigProvider {
            let layout = try IOSExportLayout.defaultInAppSandbox()
            return layout.baseDirectoryURL.appendingPathComponent("auto_upload.json", isDirectory: false)
        }
    }

    static func autoUploadConfig(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        arguments: [String] = ProcessInfo.processInfo.arguments,
        fileConfigProvider: FileConfigProvider = .live
    ) -> LaunchAutomationConfig? {
        if let config = autoUploadConfigFromEnvironment(environment) {
            return config
        }
        if let config = autoUploadConfigFromArguments(arguments) {
            return config
        }
        return autoUploadConfigFromFile(fileConfigProvider)
    }

    static func autoUploadConfig(
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) -> LaunchAutomationConfig? {
        autoUploadConfig(
            environment: environment,
            arguments: ProcessInfo.processInfo.arguments,
            fileConfigProvider: .live
        )
    }

    private static func autoUploadConfigFromEnvironment(
        _ environment: [String: String]
    ) -> LaunchAutomationConfig? {
        guard environment["HEALTHDELTA_AUTO_UPLOAD_ON_LAUNCH"] == "1" else {
            return nil
        }

        guard
            let rawBaseURL = environment["HEALTHDELTA_AUTO_UPLOAD_BASE_URL"]?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !rawBaseURL.isEmpty,
            let rawToken = environment["HEALTHDELTA_AUTO_UPLOAD_TOKEN"]?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !rawToken.isEmpty
        else {
            return nil
        }

        return LaunchAutomationConfig(baseURLString: rawBaseURL, bearerToken: rawToken)
    }

    private static func autoUploadConfigFromArguments(
        _ arguments: [String]
    ) -> LaunchAutomationConfig? {
        guard arguments.contains("--healthdelta-auto-upload-on-launch") else {
            return nil
        }

        guard
            let baseURL = value(for: "--healthdelta-auto-upload-base-url", in: arguments)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !baseURL.isEmpty,
            let token = value(for: "--healthdelta-auto-upload-token", in: arguments)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !token.isEmpty
        else {
            return nil
        }

        return LaunchAutomationConfig(baseURLString: baseURL, bearerToken: token)
    }

    private static func value(for flag: String, in arguments: [String]) -> String? {
        guard let index = arguments.firstIndex(of: flag) else {
            return nil
        }
        let valueIndex = arguments.index(after: index)
        guard valueIndex < arguments.endIndex else {
            return nil
        }
        return arguments[valueIndex]
    }

    private static func autoUploadConfigFromFile(
        _ fileConfigProvider: FileConfigProvider
    ) -> LaunchAutomationConfig? {
        let configURL: URL?
        do {
            configURL = try fileConfigProvider.configURL()
        } catch {
            return nil
        }
        guard let configURL else {
            return nil
        }
        guard let data = try? Data(contentsOf: configURL) else {
            return nil
        }

        guard
            let config = try? JSONDecoder().decode(LaunchAutomationFileConfig.self, from: data),
            !config.baseURLString.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
            !config.bearerToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else {
            return nil
        }

        return LaunchAutomationConfig(
            baseURLString: config.baseURLString.trimmingCharacters(in: .whitespacesAndNewlines),
            bearerToken: config.bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        )
    }
}

private struct LaunchAutomationFileConfig: Decodable {
    let baseURLString: String
    let bearerToken: String

    private enum CodingKeys: String, CodingKey {
        case baseURLString = "base_url"
        case bearerToken = "bearer_token"
    }
}
