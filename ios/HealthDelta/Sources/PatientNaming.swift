import Foundation

func suggestedLocalPatientAlias(fromDeviceName deviceName: String) -> String? {
    let trimmed = deviceName.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else {
        return nil
    }

    let apostropheRanges = ["'s ", "’s "]
    for token in apostropheRanges {
        if let range = trimmed.range(of: token) {
            let candidate = String(trimmed[..<range.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
            return candidate.isEmpty ? nil : candidate
        }
    }

    let words = trimmed.split(separator: " ").map(String.init)
    guard let first = words.first, !first.isEmpty else {
        return nil
    }
    return first
}

func unlabeledRemotePatientScopes(
    localCanonicalPersonID: String?,
    patientAliases: [String: String],
    remotePatientScopes: [ORINPatientScope]
) -> [ORINPatientScope] {
    remotePatientScopes.filter { scope in
        if scope.canonicalPersonID == localCanonicalPersonID {
            return false
        }
        let alias = patientAliases[scope.canonicalPersonID]?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return alias.isEmpty
    }
}
