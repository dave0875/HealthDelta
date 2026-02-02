from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


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


def _metric_values(rows: list[dict[str, Any]], metric: str) -> list[tuple[datetime, float]]:
    out: list[tuple[datetime, float]] = []
    for row in rows:
        when = _parse_time(row.get("event_time"))
        if when is None:
            continue
        value = _to_float(row.get("value"))
        if value is None:
            continue
        hk_type = row.get("hk_type")
        codings = row.get("code_coding")
        loinc_codes = set()
        if isinstance(codings, list):
            for coding in codings:
                if isinstance(coding, dict) and coding.get("system") == "http://loinc.org" and isinstance(coding.get("code"), str):
                    loinc_codes.add(coding["code"])
        matches = False
        if metric == "heart_rate":
            matches = hk_type == "HKQuantityTypeIdentifierHeartRate" or "8867-4" in loinc_codes
        elif metric == "systolic_bp":
            matches = "8480-6" in loinc_codes
        elif metric == "diastolic_bp":
            matches = "8462-4" in loinc_codes
        if matches:
            out.append((when, value))
    out.sort(key=lambda item: item[0])
    return out


def _trend_for_metric(*, metric: str, values: list[tuple[datetime, float]]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "metric": metric,
        "window_days": 7,
        "direction": "insufficient",
        "confidence": "insufficient",
        "current_window_avg": None,
        "previous_window_avg": None,
        "delta": None,
        "insufficiency_reason": "insufficient_data",
    }
    if len(values) < 3:
        return base

    latest = values[-1][0]
    current_start = latest - timedelta(days=7)
    previous_start = latest - timedelta(days=14)

    current = [v for t, v in values if current_start <= t <= latest]
    previous = [v for t, v in values if previous_start <= t < current_start]
    if len(current) < 1 or len(previous) < 1:
        return base

    current_avg = sum(current) / len(current)
    prev_avg = sum(previous) / len(previous)
    delta = current_avg - prev_avg
    abs_delta = abs(delta)

    if abs_delta < 1.0:
        direction = "stable"
    elif delta > 0:
        direction = "up"
    else:
        direction = "down"

    sample_size = len(current) + len(previous)
    if sample_size >= 8 and abs_delta >= 3.0:
        confidence = "high"
    elif sample_size >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "metric": metric,
        "window_days": 7,
        "direction": direction,
        "confidence": confidence,
        "current_window_avg": round(current_avg, 2),
        "previous_window_avg": round(prev_avg, 2),
        "delta": round(delta, 2),
        "insufficiency_reason": None,
    }


def build_trend_analysis(*, ndjson_dir: str) -> dict[str, Any]:
    rows = _read_ndjson(Path(ndjson_dir) / "observations.ndjson")
    metrics = ["heart_rate", "systolic_bp", "diastolic_bp"]
    trends = []
    for metric in metrics:
        values = _metric_values(rows, metric)
        trends.append(_trend_for_metric(metric=metric, values=values))
    return {"trends": trends}
