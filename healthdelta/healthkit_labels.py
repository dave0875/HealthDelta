from __future__ import annotations

import re


_KNOWN_LABELS: dict[str, str] = {
    "HKQuantityTypeIdentifierHeartRate": "Heart rate",
    "HKQuantityTypeIdentifierRestingHeartRate": "Resting heart rate",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": "Walking heart rate average",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "Heart rate variability (SDNN)",
    "HKQuantityTypeIdentifierStepCount": "Step count",
    "HKQuantityTypeIdentifierRespiratoryRate": "Respiratory rate",
    "HKQuantityTypeIdentifierOxygenSaturation": "Oxygen saturation",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "Active energy burned",
    "HKQuantityTypeIdentifierBasalEnergyBurned": "Basal energy burned",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "Walking/running distance",
    "HKQuantityTypeIdentifierBodyMass": "Body mass",
    "HKQuantityTypeIdentifierBodyFatPercentage": "Body fat percentage",
    "HKQuantityTypeIdentifierBodyMassIndex": "Body mass index",
    "HKQuantityTypeIdentifierHeight": "Height",
    "HKQuantityTypeIdentifierBodyTemperature": "Body temperature",
    "HKQuantityTypeIdentifierBloodPressureSystolic": "Systolic blood pressure",
    "HKQuantityTypeIdentifierBloodPressureDiastolic": "Diastolic blood pressure",
    "HKCategoryTypeIdentifierSleepAnalysis": "Sleep analysis",
    "HKWorkoutTypeIdentifier": "Workout",
}

_PREFIX_KIND_MAP: tuple[tuple[str, str], ...] = (
    ("HKQuantityTypeIdentifier", "quantity"),
    ("HKCategoryTypeIdentifier", "category"),
    ("HKCorrelationTypeIdentifier", "correlation"),
    ("HKCharacteristicTypeIdentifier", "characteristic"),
    ("HKWorkoutTypeIdentifier", "workout"),
)

_ACRONYM_FIXUPS: tuple[tuple[str, str], ...] = (
    ("Sdnn", "SDNN"),
    ("Bmi", "BMI"),
    ("Vo2 Max", "VO2 max"),
    ("Uv", "UV"),
)


def healthkit_display_label(identifier: str | None) -> str | None:
    if not isinstance(identifier, str):
        return None
    raw = identifier.strip()
    if not raw:
        return None
    if raw in _KNOWN_LABELS:
        return _KNOWN_LABELS[raw]

    stem = raw
    for prefix, _ in _PREFIX_KIND_MAP:
        if stem.startswith(prefix):
            stem = stem[len(prefix) :]
            break

    if not stem:
        return raw

    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", stem).replace("_", " ").split()
    if not parts:
        return raw
    label = " ".join(part.lower() for part in parts)
    label = label[:1].upper() + label[1:]
    for old, new in _ACRONYM_FIXUPS:
        label = label.replace(old, new)
    return label


def healthkit_sample_kind(identifier: str | None) -> str | None:
    if not isinstance(identifier, str):
        return None
    raw = identifier.strip()
    if not raw:
        return None
    for prefix, kind in _PREFIX_KIND_MAP:
        if raw.startswith(prefix):
            return kind
    return None
