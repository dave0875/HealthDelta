import Foundation

enum ORINInsightsFetchResult: Equatable {
    case cards([InsightCard])
    case noInsightsYet(String)
}

protocol ORINInsightsFetching {
    func fetchCurrentInsights(
        baseURLString: String,
        bearerToken: String,
        canonicalPersonID: String?,
        windowDays: Int?
    ) async throws -> ORINInsightsFetchResult
}

private struct ORINInsightsResponse: Decodable {
    let status: String
    let detail: String?
    let cards: [InsightCardPayload]
}

private struct InsightCardPayload: Decodable {
    let id: String
    let title: String
    let body: String
    let disclaimer: String
    let sourceLabel: String
    let freshnessLabel: String
}

private struct ORINInsightsErrorResponse: Decodable {
    let error: String?
    let detail: String?
}

final class ORINInsightsService: ORINInsightsFetching {
    private let session: URLSessionUploading

    init(session: URLSessionUploading) {
        self.session = session
    }

    static func live() -> ORINInsightsService {
        ORINInsightsService(session: URLSession.shared)
    }

    func fetchCurrentInsights(
        baseURLString: String,
        bearerToken: String,
        canonicalPersonID: String? = nil,
        windowDays: Int? = nil
    ) async throws -> ORINInsightsFetchResult {
        let trimmedURL = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let baseURL = URL(string: trimmedURL), let scheme = baseURL.scheme, scheme == "http" || scheme == "https" else {
            throw RunUploadError.invalidBaseURL
        }
        let token = bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            throw RunUploadError.missingToken
        }

        var components = URLComponents(url: baseURL.appendingPathComponent("insights/current"), resolvingAgainstBaseURL: false)
        var queryItems: [URLQueryItem] = []
        let trimmedPerson = canonicalPersonID?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !trimmedPerson.isEmpty {
            queryItems.append(URLQueryItem(name: "canonical_person_id", value: trimmedPerson))
        }
        if let windowDays, windowDays > 0 {
            queryItems.append(URLQueryItem(name: "window_days", value: String(windowDays)))
        }
        if !queryItems.isEmpty {
            components?.queryItems = queryItems
        }
        guard let requestURL = components?.url else {
            throw RunUploadError.invalidBaseURL
        }

        var request = URLRequest(url: requestURL)
        request.httpMethod = "GET"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw RunUploadError.invalidServerResponse
        }
        guard http.statusCode == 200 else {
            if let decoded = try? JSONDecoder().decode(ORINInsightsErrorResponse.self, from: data) {
                let detail = [decoded.error, decoded.detail].compactMap { $0 }.joined(separator: ": ")
                throw RunUploadError.uploadFailed(detail.isEmpty ? "HTTP \(http.statusCode)" : detail)
            }
            throw RunUploadError.uploadFailed("HTTP \(http.statusCode)")
        }

        let payload = try JSONDecoder().decode(ORINInsightsResponse.self, from: data)
        if payload.status == "no_insights_yet" {
            return .noInsightsYet(payload.detail ?? "ORIN does not have generated insights yet.")
        }
        return .cards(
            payload.cards.map {
                InsightCard(
                    id: $0.id,
                    title: $0.title,
                    body: $0.body,
                    disclaimer: $0.disclaimer,
                    sourceLabel: $0.sourceLabel,
                    freshnessLabel: $0.freshnessLabel
                )
            }
        )
    }
}
