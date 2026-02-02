from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DISCLAIMER = "Information-only risk flags for record review; not medical advice."


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _evidence(row: dict[str, Any], stream: str) -> dict[str, Any]:
    return {
        "stream": stream,
        "record_key": row.get("record_key"),
        "source_file": row.get("source_file"),
        "event_time": row.get("event_time"),
    }


def build_risk_flags(*, ndjson_dir: str) -> dict[str, Any]:
    root = Path(ndjson_dir)
    observations = _read_ndjson(root / "observations.ndjson")
    encounters = _read_ndjson(root / "encounters.ndjson")

    bp_hits: list[dict[str, Any]] = []
    tachy_hits: list[dict[str, Any]] = []
    for row in observations:
        value = _to_float(row.get("value"))
        hk_type = row.get("hk_type")
        codings = row.get("code_coding")
        loinc_codes = set()
        if isinstance(codings, list):
            for coding in codings:
                if isinstance(coding, dict) and coding.get("system") == "http://loinc.org" and isinstance(coding.get("code"), str):
                    loinc_codes.add(coding["code"])

        if value is not None:
            if "8480-6" in loinc_codes and value >= 140:
                bp_hits.append(row)
            if "8462-4" in loinc_codes and value >= 90:
                bp_hits.append(row)
            if "8867-4" in loinc_codes and value >= 100:
                tachy_hits.append(row)
            if hk_type == "HKQuantityTypeIdentifierHeartRate" and value >= 100:
                tachy_hits.append(row)

    encounter_times = sorted([_parse_time(row.get("event_time")) for row in encounters if _parse_time(row.get("event_time")) is not None])
    encounter_cluster = False
    if len(encounter_times) >= 2:
        for i in range(1, len(encounter_times)):
            delta_days = (encounter_times[i] - encounter_times[i - 1]).days
            if delta_days <= 30:
                encounter_cluster = True
                break

    flags: list[dict[str, Any]] = []
    if bp_hits:
        flags.append(
            {
                "flag_id": "high_blood_pressure",
                "category": "cardiovascular",
                "severity": "high",
                "title": "Elevated blood pressure reading observed",
                "rationale": "One or more blood pressure measurements exceeded rule thresholds.",
                "evidence": [_evidence(row, "observations") for row in bp_hits[:3]],
            }
        )
    if tachy_hits:
        flags.append(
            {
                "flag_id": "tachycardia_signal",
                "category": "cardiovascular",
                "severity": "medium",
                "title": "Elevated heart-rate signal observed",
                "rationale": "One or more heart-rate measurements met the tachycardia threshold.",
                "evidence": [_evidence(row, "observations") for row in tachy_hits[:3]],
            }
        )
    if encounter_cluster:
        flags.append(
            {
                "flag_id": "frequent_recent_encounters",
                "category": "utilization",
                "severity": "medium",
                "title": "Multiple encounters in a short interval",
                "rationale": "Encounter timestamps indicate repeated care visits within 30 days.",
                "evidence": [_evidence(row, "encounters") for row in encounters[:3]],
            }
        )

    flags.sort(key=lambda row: (str(row.get("severity")), str(row.get("flag_id"))))
    return {
        "disclaimer": DISCLAIMER,
        "flags": flags,
    }
