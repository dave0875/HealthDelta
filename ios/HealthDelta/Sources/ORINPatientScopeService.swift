import Foundation

struct ORINPatientScope: Decodable, Equatable {
    let canonicalPersonID: String
    let displayLabel: String
    let rowCount: Int
    let minEventTime: String?
    let maxEventTime: String?

    private enum CodingKeys: String, CodingKey {
        case canonicalPersonID = "canonical_person_id"
        case displayLabel = "display_label"
        case rowCount = "row_count"
        case minEventTime = "min_event_time"
        case maxEventTime = "max_event_time"
    }
}

protocol ORINPatientScopeFetching {
    func fetchCurrentPatients(
        baseURLString: String,
        bearerToken: String
    ) async throws -> [ORINPatientScope]
}

private struct ORINPatientScopeResponse: Decodable {
    let dataset: String?
    let patients: [ORINPatientScope]
}

private struct ORINPatientScopeErrorResponse: Decodable {
    let error: String?
    let detail: String?
}

final class ORINPatientScopeService: ORINPatientScopeFetching {
    private let session: URLSessionUploading

    init(session: URLSessionUploading) {
        self.session = session
    }

    static func live() -> ORINPatientScopeService {
        ORINPatientScopeService(session: URLSession.shared)
    }

    func fetchCurrentPatients(
        baseURLString: String,
        bearerToken: String
    ) async throws -> [ORINPatientScope] {
        let trimmedURL = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let baseURL = URL(string: trimmedURL), let scheme = baseURL.scheme, scheme == "http" || scheme == "https" else {
            throw RunUploadError.invalidBaseURL
        }
        let token = bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            throw RunUploadError.missingToken
        }

        var request = URLRequest(url: baseURL.appendingPathComponent("patients/current"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw RunUploadError.invalidServerResponse
        }
        guard http.statusCode == 200 else {
            if let decoded = try? JSONDecoder().decode(ORINPatientScopeErrorResponse.self, from: data) {
                let detail = [decoded.error, decoded.detail].compactMap { $0 }.joined(separator: ": ")
                throw RunUploadError.uploadFailed(detail.isEmpty ? "HTTP \(http.statusCode)" : detail)
            }
            throw RunUploadError.uploadFailed("HTTP \(http.statusCode)")
        }

        let payload = try JSONDecoder().decode(ORINPatientScopeResponse.self, from: data)
        return payload.patients
    }
}
