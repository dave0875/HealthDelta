import XCTest

@testable import HealthDelta

final class LaunchAutomationTests: XCTestCase {
    func testAutoUploadConfigReturnsNilWhenDisabled() {
        XCTAssertNil(LaunchAutomation.autoUploadConfig(environment: [:], arguments: []))
    }

    func testAutoUploadConfigReturnsNilWhenRequiredValuesMissing() {
        XCTAssertNil(LaunchAutomation.autoUploadConfig(
            environment: [
                "HEALTHDELTA_AUTO_UPLOAD_ON_LAUNCH": "1",
                "HEALTHDELTA_AUTO_UPLOAD_BASE_URL": "http://192.168.1.223:8080",
            ],
            arguments: []
        ))
    }

    func testAutoUploadConfigTrimsValuesWhenEnabled() {
        let config = LaunchAutomation.autoUploadConfig(
            environment: [
                "HEALTHDELTA_AUTO_UPLOAD_ON_LAUNCH": "1",
                "HEALTHDELTA_AUTO_UPLOAD_BASE_URL": "  http://192.168.1.223:8080  ",
                "HEALTHDELTA_AUTO_UPLOAD_TOKEN": "  secret-token  ",
            ],
            arguments: []
        )

        XCTAssertEqual(
            config,
            LaunchAutomationConfig(
                baseURLString: "http://192.168.1.223:8080",
                bearerToken: "secret-token"
            )
        )
    }

    func testAutoUploadConfigParsesLaunchArguments() {
        let config = LaunchAutomation.autoUploadConfig(
            environment: [:],
            arguments: [
                "HealthDelta",
                "--healthdelta-auto-upload-on-launch",
                "--healthdelta-auto-upload-base-url", "http://192.168.1.223:8080",
                "--healthdelta-auto-upload-token", "secret-token",
            ]
        )

        XCTAssertEqual(
            config,
            LaunchAutomationConfig(
                baseURLString: "http://192.168.1.223:8080",
                bearerToken: "secret-token"
            )
        )
    }

    func testAutoUploadConfigParsesFileConfig() throws {
        let configURL = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: false)
            .appendingPathExtension("json")
        try Data(#"{"base_url":"http://192.168.1.223:8080","bearer_token":"secret-token"}"#.utf8)
            .write(to: configURL)
        defer { try? FileManager.default.removeItem(at: configURL) }

        let config = LaunchAutomation.autoUploadConfig(
            environment: [:],
            arguments: [],
            fileConfigProvider: .init(configURL: { configURL })
        )

        XCTAssertEqual(
            config,
            LaunchAutomationConfig(
                baseURLString: "http://192.168.1.223:8080",
                bearerToken: "secret-token"
            )
        )
    }
}
