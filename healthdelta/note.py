from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path
from typing import Any

from healthdelta.progress import progress


def _fmt_ts(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=dt.timezone.utc)
        v = v.astimezone(dt.timezone.utc).replace(microsecond=0)
        return v.isoformat().replace("+00:00", "Z")
    return str(v)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tf:
        tmp = Path(tf.name)
        tf.write(text)
        if not text.endswith("\n"):
            tf.write("\n")
    tmp.replace(path)


def _humanize_signal_label(label: str) -> str:
    known = {
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
    }
    if label in known:
        return known[label]
    return label


def _connect_read_only(db_path: Path):
    try:
        import duckdb
    except Exception as e:  # pragma: no cover
        raise RuntimeError("duckdb Python package is required (install dependency 'duckdb')") from e

    con = duckdb.connect(database=str(db_path), read_only=True)
    con.execute("PRAGMA threads=1;")
    con.execute("PRAGMA enable_progress_bar=false;")
    return con


def _tables_present(con) -> set[str]:
    tables = set()
    for (name,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name;").fetchall():
        if isinstance(name, str):
            tables.add(name)
    return tables


def _rows(con, sql: str, params: list[Any] | None = None) -> list[tuple]:
    return con.execute(sql, params or []).fetchall()


def _scalar(con, sql: str, params: list[Any] | None = None) -> Any:
    r = con.execute(sql, params or []).fetchone()
    return r[0] if r else None


def build_doctor_note(*, db_path: str, out_dir: str, mode: str = "share") -> None:
    if mode not in {"local", "share"}:
        raise ValueError("--mode must be one of: local, share")

    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Missing DB file: {db.name}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with progress.phase("note: connect"):
        con = _connect_read_only(db)
    try:
        with progress.phase("note: scan tables"):
            present = _tables_present(con)
            tables = [t for t in ["observations", "documents", "medications", "conditions", "encounters", "procedures", "diagnostic_reports"] if t in present]

        def union_all(select_expr: str) -> str | None:
            if not tables:
                return None
            parts = [f"SELECT {select_expr} FROM {t}" for t in tables]
            return " UNION ALL ".join(parts)

        # run_id
        with progress.phase("note: compute run_id"):
            run_id_val = "unknown"
            union_run = union_all("run_id")
            if union_run is not None:
                run_ids = [
                    r
                    for (r,) in _rows(
                        con, f"SELECT DISTINCT run_id FROM ({union_run}) WHERE run_id IS NOT NULL ORDER BY run_id;"
                    )
                    if isinstance(r, str) and r
                ]
                if len(run_ids) == 1:
                    run_id_val = run_ids[0]
                elif len(run_ids) > 1:
                    run_id_val = f"multiple({len(run_ids)})"

        # event_time range + deterministic generated_at
        with progress.phase("note: compute event_time range"):
            min_et_s = None
            max_et_s = None
            active_days = 0
            union_et = union_all("event_time")
            if union_et is not None:
                min_et = _scalar(con, f"SELECT MIN(event_time) FROM ({union_et}) WHERE event_time IS NOT NULL;")
                max_et = _scalar(con, f"SELECT MAX(event_time) FROM ({union_et}) WHERE event_time IS NOT NULL;")
                active_days = int(
                    _scalar(
                        con,
                        f"SELECT COUNT(DISTINCT CAST(event_time AS DATE)) FROM ({union_et}) WHERE event_time IS NOT NULL;",
                    )
                    or 0
                )
                min_et_s = _fmt_ts(min_et)
                max_et_s = _fmt_ts(max_et)

        generated_at = max_et_s or "1970-01-01T00:00:00Z"

        # distinct people across all tables
        with progress.phase("note: compute people count"):
            people = 0
            union_people = union_all("canonical_person_id")
            if union_people is not None:
                people = int(
                    _scalar(
                        con,
                        f"SELECT COUNT(DISTINCT canonical_person_id) FROM ({union_people}) WHERE canonical_person_id IS NOT NULL;",
                    )
                    or 0
                )

        # totals per table (include even if missing)
        with progress.phase("note: compute totals"):
            totals: dict[str, int] = {}
            total_keys = ["observations", "documents", "medications", "conditions", "encounters", "procedures", "diagnostic_reports"]
            task = progress.task("note: compute totals", total=len(total_keys), unit="tables")
            for t in total_keys:
                if t in present:
                    totals[t] = int(_scalar(con, f"SELECT COUNT(*) FROM {t};") or 0)
                else:
                    totals[t] = 0
                task.advance(1)

        # counts by source across all tables
        with progress.phase("note: compute sources"):
            sources = {"healthkit": 0, "fhir": 0, "cda": 0}
            union_src = union_all("source")
            if union_src is not None:
                for src, n in _rows(
                    con, f"SELECT source, COUNT(*) AS n FROM ({union_src}) GROUP BY source ORDER BY source;"
                ):
                    if isinstance(src, str) and src in sources:
                        sources[src] = int(n)

        # signals: top-N observation types/codes (no free-text)
        with progress.phase("note: compute signals"):
            signals = ""
            top_signal_rows: list[tuple[str, int]] = []
            if "observations" in present and totals["observations"] > 0:
                raw = [
                    (label, int(n))
                    for label, n in _rows(
                        con,
                        """
                        SELECT COALESCE(hk_type, resource_type, code, 'unknown') AS label,
                               COUNT(*) AS n
                        FROM observations
                        GROUP BY label
                        ORDER BY n DESC, label ASC;
                        """,
                    )
                    if isinstance(label, str)
                ]
                raw.sort(key=lambda x: (-x[1], 0 if x[0].startswith("HK") else 1, x[0]))
                top_signal_rows = raw[:5]
                signals = ";".join([f"{k}:{v}" for k, v in top_signal_rows])

        clinical_table_counts = {
            key: totals[key]
            for key in ["documents", "medications", "conditions", "encounters", "procedures", "diagnostic_reports"]
            if totals[key] > 0
        }
        fitness_present = totals["observations"] > 0 and sources["healthkit"] > 0
        clinical_present = bool(clinical_table_counts) or sources["fhir"] > 0 or sources["cda"] > 0
        if fitness_present and clinical_present:
            domain_mix = "mixed"
        elif fitness_present:
            domain_mix = "fitness"
        elif clinical_present:
            domain_mix = "clinical"
        else:
            domain_mix = "limited"

        def _summary_signal_line() -> str:
            if not top_signal_rows:
                return "- No dominant observation signal was available in the current structured data."
            top_parts = [f"{_humanize_signal_label(label)} ({count} row{'s' if count != 1 else ''})" for label, count in top_signal_rows[:3]]
            return "- Most common observed signals: " + "; ".join(top_parts) + "."

        def _summary_clinical_line() -> str:
            if clinical_table_counts:
                parts = [f"{name} ({count} row{'s' if count != 1 else ''})" for name, count in clinical_table_counts.items()]
                return "- Clinical record coverage includes " + ", ".join(parts) + "."
            if clinical_present:
                return "- Structured clinical-source records are present in the current scope."
            return "- Structured clinical records are not present in the current scope."

        nonzero_sources = [(source, count) for source, count in sources.items() if count > 0]
        source_summary = ", ".join([f"{source} ({count} row{'s' if count != 1 else ''})" for source, count in nonzero_sources]) or "no structured sources"

        lines: list[str] = []
        lines.append("HealthDelta Doctor's Note")
        lines.append(f"run_id={run_id_val}")
        lines.append(f"generated_at={generated_at}")
        lines.append("")
        lines.append("Summary")
        if min_et_s and max_et_s:
            lines.append(f"- Scope covers {people} person{'s' if people != 1 else ''} from {min_et_s} to {max_et_s} across {active_days} active day{'s' if active_days != 1 else ''}.")
        else:
            lines.append(f"- Scope covers {people} person{'s' if people != 1 else ''}, but no event-time range was available in the current structured data.")
        if domain_mix == "mixed":
            lines.append("- Current data is mixed: fitness/wellness observations and structured clinical records are both present.")
        elif domain_mix == "fitness":
            lines.append("- Current data is fitness-led: Apple Health wellness observations are present, but structured clinical records are not.")
        elif domain_mix == "clinical":
            lines.append("- Current data is clinical-led: structured clinical records are present without Apple Health fitness observations.")
        else:
            lines.append("- Current data is limited and does not yet support a richer bedside summary.")
        lines.append(_summary_signal_line())
        lines.append(_summary_clinical_line())
        lines.append(f"- Source mix includes {source_summary}.")
        lines.append("- Share-safe note: no names, dates of birth, identifiers, or free-text clinical narratives are included.")
        lines.append("")
        lines.append("Facts")
        lines.append(f"people={people}")
        lines.append(f"active_days={active_days}")
        if min_et_s and max_et_s:
            lines.append(f"event_time_range={min_et_s}..{max_et_s}")
        else:
            lines.append("event_time_range=")
        lines.append(f"domain_mix={domain_mix}")
        lines.append(f"totals.observations={totals['observations']}")
        lines.append(f"totals.documents={totals['documents']}")
        lines.append(f"totals.medications={totals['medications']}")
        lines.append(f"totals.conditions={totals['conditions']}")
        lines.append(f"totals.encounters={totals['encounters']}")
        lines.append(f"totals.procedures={totals['procedures']}")
        lines.append(f"totals.diagnostic_reports={totals['diagnostic_reports']}")
        lines.append(f"sources.healthkit={sources['healthkit']}")
        lines.append(f"sources.fhir={sources['fhir']}")
        lines.append(f"sources.cda={sources['cda']}")
        if signals:
            lines.append(f"signals.top_observations={signals}")

        text = "\n".join(lines) + "\n"
        with progress.phase("note: write artifacts"):
            task = progress.task("note: write artifacts", total=2, unit="files")
            _write_text_atomic(out / "doctor_note.txt", text)
            task.advance(1)
            _write_text_atomic(out / "doctor_note.md", text)
            task.advance(1)
    finally:
        con.close()
