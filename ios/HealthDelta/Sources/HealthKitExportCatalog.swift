import Foundation
import HealthKit

struct HealthKitExportPlan {
    let key: String
    let type: HKSampleType
}

enum HealthKitExportCatalog {
    static func supportedPlans() -> [HealthKitExportPlan] {
        [
            quantity(key: "steps", identifier: .stepCount),
            quantity(key: "heart_rate", identifier: .heartRate),
            quantity(key: "resting_heart_rate", identifier: .restingHeartRate),
            quantity(key: "walking_heart_rate_average", identifier: .walkingHeartRateAverage),
            quantity(key: "heart_rate_variability_sdnn", identifier: .heartRateVariabilitySDNN),
            quantity(key: "respiratory_rate", identifier: .respiratoryRate),
            quantity(key: "oxygen_saturation", identifier: .oxygenSaturation),
            quantity(key: "active_energy_burned", identifier: .activeEnergyBurned),
            quantity(key: "basal_energy_burned", identifier: .basalEnergyBurned),
            quantity(key: "distance_walking_running", identifier: .distanceWalkingRunning),
            quantity(key: "body_mass", identifier: .bodyMass),
            quantity(key: "body_fat_percentage", identifier: .bodyFatPercentage),
            quantity(key: "body_mass_index", identifier: .bodyMassIndex),
            quantity(key: "height", identifier: .height),
            quantity(key: "body_temperature", identifier: .bodyTemperature),
            quantity(key: "blood_pressure_systolic", identifier: .bloodPressureSystolic),
            quantity(key: "blood_pressure_diastolic", identifier: .bloodPressureDiastolic),
            category(key: "sleep_analysis", identifier: .sleepAnalysis),
            workout(key: "workouts"),
        ]
        .compactMap { $0 }
    }

    static func preferredUnit(for sampleTypeIdentifier: String) -> (unit: HKUnit, label: String)? {
        switch sampleTypeIdentifier {
        case HKQuantityTypeIdentifier.stepCount.rawValue:
            return (.count(), "count")
        case HKQuantityTypeIdentifier.heartRate.rawValue,
             HKQuantityTypeIdentifier.restingHeartRate.rawValue,
             HKQuantityTypeIdentifier.walkingHeartRateAverage.rawValue,
             HKQuantityTypeIdentifier.respiratoryRate.rawValue:
            return (.count().unitDivided(by: .minute()), "count/min")
        case HKQuantityTypeIdentifier.heartRateVariabilitySDNN.rawValue:
            return (.secondUnit(with: .milli), "ms")
        case HKQuantityTypeIdentifier.oxygenSaturation.rawValue,
             HKQuantityTypeIdentifier.bodyFatPercentage.rawValue:
            return (.percent(), "%")
        case HKQuantityTypeIdentifier.activeEnergyBurned.rawValue,
             HKQuantityTypeIdentifier.basalEnergyBurned.rawValue:
            return (.kilocalorie(), "kcal")
        case HKQuantityTypeIdentifier.distanceWalkingRunning.rawValue,
             HKQuantityTypeIdentifier.height.rawValue:
            return (.meter(), "m")
        case HKQuantityTypeIdentifier.bodyMass.rawValue:
            return (.gramUnit(with: .kilo), "kg")
        case HKQuantityTypeIdentifier.bodyMassIndex.rawValue:
            return (.count(), "count")
        case HKQuantityTypeIdentifier.bodyTemperature.rawValue:
            return (.degreeCelsius(), "degC")
        case HKQuantityTypeIdentifier.bloodPressureSystolic.rawValue,
             HKQuantityTypeIdentifier.bloodPressureDiastolic.rawValue:
            return (.millimeterOfMercury(), "mmHg")
        default:
            return nil
        }
    }

    static func categoryValueLabel(for sampleTypeIdentifier: String, value: Int) -> String? {
        switch sampleTypeIdentifier {
        case HKCategoryTypeIdentifier.sleepAnalysis.rawValue:
            guard let sleepValue = HKCategoryValueSleepAnalysis(rawValue: value) else {
                return "unknown_sleep_state_\(value)"
            }
            switch sleepValue {
            case .inBed:
                return "in_bed"
            case .asleepUnspecified:
                return "asleep_unspecified"
            case .awake:
                return "awake"
            case .asleepCore:
                return "asleep_core"
            case .asleepDeep:
                return "asleep_deep"
            case .asleepREM:
                return "asleep_rem"
            @unknown default:
                return "unknown_sleep_state_\(value)"
            }
        default:
            return nil
        }
    }

    static func workoutActivityLabel(for activityType: HKWorkoutActivityType) -> String {
        switch activityType {
        case .running:
            return "running"
        case .walking:
            return "walking"
        case .cycling:
            return "cycling"
        case .hiking:
            return "hiking"
        case .traditionalStrengthTraining:
            return "traditional_strength_training"
        case .functionalStrengthTraining:
            return "functional_strength_training"
        case .mixedCardio:
            return "mixed_cardio"
        case .yoga:
            return "yoga"
        case .swimming:
            return "swimming"
        default:
            return "activity_\(activityType.rawValue)"
        }
    }

    private static func quantity(key: String, identifier: HKQuantityTypeIdentifier) -> HealthKitExportPlan? {
        guard let type = HKQuantityType.quantityType(forIdentifier: identifier) else {
            return nil
        }
        return HealthKitExportPlan(key: key, type: type)
    }

    private static func category(key: String, identifier: HKCategoryTypeIdentifier) -> HealthKitExportPlan? {
        guard let type = HKCategoryType.categoryType(forIdentifier: identifier) else {
            return nil
        }
        return HealthKitExportPlan(key: key, type: type)
    }

    private static func workout(key: String) -> HealthKitExportPlan {
        HealthKitExportPlan(key: key, type: HKObjectType.workoutType())
    }
}
