import Foundation
import HealthKit

protocol SyncStatusLoading {
    func loadLatest() throws -> SyncStatusSnapshot
}

protocol InsightsLoading {
    func loadLatestCards() throws -> [InsightCard]
}

protocol ManualHealthExporting {
    @discardableResult
    func runManualExport() async throws -> String
}

protocol HealthKitAuthorizing {
    func requestReadAuthorization(for types: Set<HKObjectType>) async throws -> Bool
}

protocol IncrementalRunExporting {
    @discardableResult
    func runOnce(
        runID: String,
        layout: IOSExportLayout,
        plan: HealthKitExportPlan,
        predicate: NSPredicate?,
        limit: Int
    ) async throws -> Bool
}

enum ManualHealthExportError: LocalizedError, Equatable {
    case healthDataUnavailable
    case authorizationDenied
    case noSupportedTypesAvailable

    var errorDescription: String? {
        switch self {
        case .healthDataUnavailable:
            return "Health data is not available on this device."
        case .authorizationDenied:
            return "Health access was denied. Enable Health permissions and try again."
        case .noSupportedTypesAvailable:
            return "No supported Health data types are available on this device."
        }
    }
}

extension SyncStatusStore: SyncStatusLoading {}
extension InsightsStore: InsightsLoading {}
extension IncrementalNDJSONExporter: IncrementalRunExporting {}

final class HealthKitAuthorizationClient: HealthKitAuthorizing {
    private let store: HKHealthStore

    init(store: HKHealthStore) {
        self.store = store
    }

    func requestReadAuthorization(for types: Set<HKObjectType>) async throws -> Bool {
        try await withCheckedThrowingContinuation { continuation in
            store.requestAuthorization(toShare: [], read: types) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                continuation.resume(returning: success)
            }
        }
    }
}

final class ManualHealthExportService: ManualHealthExporting {
    private let healthDataAvailable: () -> Bool
    private let authorizationClient: HealthKitAuthorizing
    private let exporter: IncrementalRunExporting
    private let layoutProvider: () throws -> IOSExportLayout
    private let runIDProvider: () -> String
    private let samplePlansProvider: () -> [HealthKitExportPlan]

    init(
        healthDataAvailable: @escaping () -> Bool,
        authorizationClient: HealthKitAuthorizing,
        exporter: IncrementalRunExporting,
        layoutProvider: @escaping () throws -> IOSExportLayout,
        runIDProvider: @escaping () -> String,
        samplePlansProvider: @escaping () -> [HealthKitExportPlan]
    ) {
        self.healthDataAvailable = healthDataAvailable
        self.authorizationClient = authorizationClient
        self.exporter = exporter
        self.layoutProvider = layoutProvider
        self.runIDProvider = runIDProvider
        self.samplePlansProvider = samplePlansProvider
    }

    static func live() -> ManualHealthExportService {
        let store = HKHealthStore()
        return ManualHealthExportService(
            healthDataAvailable: { HKHealthStore.isHealthDataAvailable() },
            authorizationClient: HealthKitAuthorizationClient(store: store),
            exporter: IncrementalNDJSONExporter(
                anchorStore: AnchorStore(),
                queryClient: HealthKitAnchoredQueryClient(store: store)
            ),
            layoutProvider: { try IOSExportLayout.defaultInAppSandbox() },
            runIDProvider: { Self.defaultRunID() },
            samplePlansProvider: { HealthKitExportCatalog.supportedPlans() }
        )
    }

    @discardableResult
    func runManualExport() async throws -> String {
        guard healthDataAvailable() else {
            throw ManualHealthExportError.healthDataUnavailable
        }

        let plans = samplePlansProvider()
        guard !plans.isEmpty else {
            throw ManualHealthExportError.noSupportedTypesAvailable
        }

        let authorized = try await authorizationClient.requestReadAuthorization(for: Set(plans.map { $0.type as HKObjectType }))
        guard authorized else {
            throw ManualHealthExportError.authorizationDenied
        }

        let runID = runIDProvider()
        let layout = try layoutProvider()
        for plan in plans {
            _ = try await exporter.runOnce(
                runID: runID,
                layout: layout,
                plan: plan,
                predicate: nil,
                limit: HKObjectQueryNoLimit
            )
        }
        return runID
    }

    private static func defaultRunID() -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "'run_'yyyyMMdd_HHmmss"
        return formatter.string(from: Date())
    }
}
