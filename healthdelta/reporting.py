from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

from healthdelta.progress import progress


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fmt_ts(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, dt.date) and not isinstance(v, dt.datetime):
        # For date buckets.
        return v.isoformat()
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


def _write_json(path: Path, obj: object) -> None:
    _write_text_atomic(path, json.dumps(obj, sort_keys=True, separators=(",", ":")))


def _write_csv(path: Path, *, header: list[str], rows: Iterable[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent), newline="") as tf:
        tmp = Path(tf.name)
        w = csv.writer(tf, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow([_fmt_ts(v) if isinstance(v, (dt.date, dt.datetime)) else ("" if v is None else str(v)) for v in row])
    tmp.replace(path)


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


def _scalar(con, sql: str, params: list[Any] | None = None) -> Any:
    res = con.execute(sql, params or []).fetchone()
    return res[0] if res else None


def _rows(con, sql: str, params: list[Any] | None = None) -> list[tuple]:
    return con.execute(sql, params or []).fetchall()


def _reference_type_label(*, stream: str, resource_type: str | None) -> str:
    if isinstance(resource_type, str) and resource_type.strip():
        rt = resource_type.strip()
        if rt == "Immunization":
            return "Immunization.patient"
        return f"{rt}.subject"

    defaults = {
        "observations": "Observation.subject",
        "documents": "DocumentReference.subject",
        "medications": "MedicationRequest.subject",
        "conditions": "Condition.subject",
        "encounters": "Encounter.subject",
        "procedures": "Procedure.subject",
    }
    return defaults.get(stream, f"{stream}.subject")


def _resource_type_rows(con, table: str) -> list[dict[str, object]]:
    rows = _rows(
        con,
        f"""
        SELECT COALESCE(resource_type, 'unknown') AS resource_type, COUNT(*) AS n
        FROM {table}
        GROUP BY 1
        ORDER BY n DESC, resource_type ASC;
        """,
    )
    return [{"resource_type": resource_type, "rows": int(n)} for resource_type, n in rows if isinstance(resource_type, str)]


def _cda_section_rows(con) -> list[dict[str, object]]:
    rows = _rows(
        con,
        """
        SELECT
          section_code,
          section_display,
          section_title,
          COUNT(*) AS n
        FROM observations
        WHERE source = 'cda'
          AND (section_code IS NOT NULL OR section_display IS NOT NULL OR section_title IS NOT NULL)
        GROUP BY 1, 2, 3
        ORDER BY n DESC, COALESCE(section_code, ''), COALESCE(section_display, ''), COALESCE(section_title, '');
        """,
    )
    out: list[dict[str, object]] = []
    for section_code, section_display, section_title, n in rows:
        out.append(
            {
                "section_code": section_code if isinstance(section_code, str) else None,
                "section_display": section_display if isinstance(section_display, str) else None,
                "section_title": section_title if isinstance(section_title, str) else None,
                "rows": int(n),
            }
        )
    return out


def build_report(*, db_path: str, out_dir: str, mode: str = "local") -> None:
    if mode not in {"local", "share"}:
        raise ValueError("--mode must be one of: local, share")

    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Missing DB file: {db.name}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with progress.phase("report: connect"):
        con = _connect_read_only(db)
    try:
        with progress.phase("report: scan tables"):
            present = _tables_present(con)
            streams = [
                t
                for t in [
                    "conditions",
                    "diagnostic_reports",
                    "documents",
                    "encounters",
                    "medications",
                    "observations",
                    "procedures",
                ]
                if t in present
            ]

        tables_summary: dict[str, dict[str, object]] = {}
        coverage_by_source_rows: list[tuple[str, str, int]] = []
        coverage_by_source_system_rows: list[tuple[str, str, int]] = []
        coverage_resource_types: dict[str, list[dict[str, object]]] = {
            "conditions": [],
            "diagnostic_reports": [],
            "documents": [],
            "encounters": [],
            "medications": [],
            "observations": [],
            "procedures": [],
        }
        cda_sections: list[dict[str, object]] = []

        source_bucket = "CASE WHEN source_file LIKE 'ndjson/%' THEN 'ios' ELSE source END"

        with progress.phase("report: summarize tables"):
            task = progress.task("report: summarize tables", total=len(streams), unit="tables")
            for table in streams:
                total_rows = int(_scalar(con, f"SELECT COUNT(*) FROM {table};") or 0)
                distinct_people = int(_scalar(con, f"SELECT COUNT(DISTINCT canonical_person_id) FROM {table};") or 0)
                min_et = _scalar(con, f"SELECT MIN(event_time) FROM {table} WHERE event_time IS NOT NULL;")
                max_et = _scalar(con, f"SELECT MAX(event_time) FROM {table} WHERE event_time IS NOT NULL;")

                by_source = _rows(con, f"SELECT {source_bucket} AS source, COUNT(*) AS n FROM {table} GROUP BY 1 ORDER BY 1;")
                by_source_map: dict[str, int] = {}
                for source, n in by_source:
                    if isinstance(source, str):
                        by_source_map[source] = int(n)
                        coverage_by_source_rows.append((table, source, int(n)))

                by_source_system = _rows(
                    con,
                    f"""
                    SELECT COALESCE(source_system, '') AS source_system, COUNT(*) AS n
                    FROM {table}
                    GROUP BY 1
                    ORDER BY 1;
                    """,
                )
                by_source_system_map: dict[str, int] = {}
                for source_system, n in by_source_system:
                    if isinstance(source_system, str):
                        key = source_system or "unknown"
                        by_source_system_map[key] = int(n)
                        coverage_by_source_system_rows.append((table, key, int(n)))

                tables_summary[table] = {
                    "total_rows": total_rows,
                    "distinct_canonical_person_id": distinct_people,
                    "min_event_time": _fmt_ts(min_et),
                    "max_event_time": _fmt_ts(max_et),
                    "rows_by_source": {k: by_source_map[k] for k in sorted(by_source_map)},
                    "rows_by_source_system": {k: by_source_system_map[k] for k in sorted(by_source_system_map)},
                }
                if table in coverage_resource_types:
                    coverage_resource_types[table] = _resource_type_rows(con, table)
                task.advance(1)

        with progress.phase("report: coverage artifacts"):
            if "observations" in streams:
                cda_sections = _cda_section_rows(con)

        # Per-person coverage across all available tables
        with progress.phase("report: per-person coverage"):
            if not streams:
                people: list[str] = []
            else:
                union = " UNION ".join([f"SELECT DISTINCT canonical_person_id FROM {t}" for t in streams])
                people = [p for (p,) in _rows(con, f"{union} ORDER BY canonical_person_id;") if isinstance(p, str)]

            rows_by_table: dict[str, dict[str, int]] = {t: {} for t in streams}
            task_rows = progress.task("report: count rows by table", total=len(streams), unit="tables")
            for t in streams:
                for person_id, n in _rows(
                    con,
                    f"SELECT canonical_person_id, COUNT(*) FROM {t} GROUP BY canonical_person_id ORDER BY canonical_person_id;",
                ):
                    if isinstance(person_id, str):
                        rows_by_table[t][person_id] = int(n)
                task_rows.advance(1)

            # Min/max event_time across all tables per person
            if streams:
                union_events = " UNION ALL ".join([f"SELECT canonical_person_id, event_time FROM {t}" for t in streams])
                per_person_times = _rows(
                    con,
                    f"""
                    SELECT canonical_person_id, MIN(event_time) AS min_et, MAX(event_time) AS max_et
                    FROM ({union_events})
                    WHERE event_time IS NOT NULL
                    GROUP BY canonical_person_id
                    ORDER BY canonical_person_id;
                    """,
                )
            else:
                per_person_times = []

        # Unresolved reference integrity by resource type
        unresolved_by_type: dict[str, int] = {}
        unresolved_clinical_by_resource_type: dict[str, dict[str, object]] = {}
        unresolved_total = 0
        with progress.phase("report: unresolved reference integrity"):
            task_ref = progress.task("report: unresolved reference scan", total=len(streams), unit="tables")
            for table in streams:
                for resource_type, n in _rows(
                    con,
                    f"""
                    SELECT resource_type, COUNT(*) AS n
                    FROM {table}
                    WHERE canonical_person_id = 'unresolved'
                    GROUP BY resource_type
                    ORDER BY resource_type;
                    """,
                ):
                    label = _reference_type_label(stream=table, resource_type=resource_type if isinstance(resource_type, str) else None)
                    unresolved_by_type[label] = int(unresolved_by_type.get(label, 0)) + int(n)
                    if isinstance(resource_type, str) and resource_type.strip():
                        unresolved_clinical_by_resource_type[resource_type] = {
                            "missing_reference_kind": label,
                            "rows": int(unresolved_clinical_by_resource_type.get(resource_type, {}).get("rows", 0)) + int(n),
                        }
                    unresolved_total += int(n)
                task_ref.advance(1)

        times_map: dict[str, tuple[object | None, object | None]] = {}
        for person_id, min_et, max_et in per_person_times:
            if isinstance(person_id, str):
                times_map[person_id] = (min_et, max_et)

        # Top-N record types per person (if type/code fields exist)
        top_n = 5
        type_rows: list[tuple[str, str, int]] = []
        if "observations" in streams:
            type_rows.extend(
                [
                    (pid, f"observations:{rt}", int(n))
                    for pid, rt, n in _rows(
                        con,
                        """
                        SELECT canonical_person_id,
                               COALESCE(hk_type, resource_type, code, 'unknown') AS record_type,
                               COUNT(*) AS n
                        FROM observations
                        GROUP BY canonical_person_id, record_type
                        ORDER BY canonical_person_id, n DESC, record_type ASC;
                        """,
                    )
                    if isinstance(pid, str) and isinstance(rt, str)
                ]
            )
        if "documents" in streams:
            type_rows.extend(
                [
                    (pid, f"documents:{rt}", int(n))
                    for pid, rt, n in _rows(
                        con,
                        """
                        SELECT canonical_person_id,
                               COALESCE(resource_type, 'unknown') AS record_type,
                               COUNT(*) AS n
                        FROM documents
                        GROUP BY canonical_person_id, record_type
                        ORDER BY canonical_person_id, n DESC, record_type ASC;
                        """,
                    )
                    if isinstance(pid, str) and isinstance(rt, str)
                ]
            )
        if "medications" in streams:
            type_rows.extend(
                [
                    (pid, f"medications:{rt}", int(n))
                    for pid, rt, n in _rows(
                        con,
                        """
                        SELECT canonical_person_id,
                               COALESCE(resource_type, 'unknown') AS record_type,
                               COUNT(*) AS n
                        FROM medications
                        GROUP BY canonical_person_id, record_type
                        ORDER BY canonical_person_id, n DESC, record_type ASC;
                        """,
                    )
                    if isinstance(pid, str) and isinstance(rt, str)
                ]
            )
        if "conditions" in streams:
            type_rows.extend(
                [
                    (pid, f"conditions:{rt}", int(n))
                    for pid, rt, n in _rows(
                        con,
                        """
                        SELECT canonical_person_id,
                               COALESCE(resource_type, code, 'unknown') AS record_type,
                               COUNT(*) AS n
                        FROM conditions
                        GROUP BY canonical_person_id, record_type
                        ORDER BY canonical_person_id, n DESC, record_type ASC;
                        """,
                    )
                    if isinstance(pid, str) and isinstance(rt, str)
                ]
            )
        if "encounters" in streams:
            type_rows.extend(
                [
                    (pid, f"encounters:{rt}", int(n))
                    for pid, rt, n in _rows(
                        con,
                        """
                        SELECT canonical_person_id,
                               COALESCE(resource_type, 'unknown') AS record_type,
                               COUNT(*) AS n
                        FROM encounters
                        GROUP BY canonical_person_id, record_type
                        ORDER BY canonical_person_id, n DESC, record_type ASC;
                        """,
                    )
                    if isinstance(pid, str) and isinstance(rt, str)
                ]
            )
        if "procedures" in streams:
            type_rows.extend(
                [
                    (pid, f"procedures:{rt}", int(n))
                    for pid, rt, n in _rows(
                        con,
                        """
                        SELECT canonical_person_id,
                               COALESCE(resource_type, code, 'unknown') AS record_type,
                               COUNT(*) AS n
                        FROM procedures
                        GROUP BY canonical_person_id, record_type
                        ORDER BY canonical_person_id, n DESC, record_type ASC;
                        """,
                    )
                    if isinstance(pid, str) and isinstance(rt, str)
                ]
            )
        if "diagnostic_reports" in streams:
            type_rows.extend(
                [
                    (pid, f"diagnostic_reports:{rt}", int(n))
                    for pid, rt, n in _rows(
                        con,
                        """
                        SELECT canonical_person_id,
                               COALESCE(resource_type, code, 'unknown') AS record_type,
                               COUNT(*) AS n
                        FROM diagnostic_reports
                        GROUP BY canonical_person_id, record_type
                        ORDER BY canonical_person_id, n DESC, record_type ASC;
                        """,
                    )
                    if isinstance(pid, str) and isinstance(rt, str)
                ]
            )

        types_by_person: dict[str, list[tuple[str, int]]] = {p: [] for p in people}
        for pid, type_key, n in type_rows:
            if pid in types_by_person:
                types_by_person[pid].append((type_key, n))

        with progress.phase("report: assemble per-person summary"):
            per_person: list[dict[str, object]] = []
            task_people = progress.task("report: assemble per-person", total=len(people), unit="people")
            batch = 0
            for person_id in people:
                by_table = {t: rows_by_table.get(t, {}).get(person_id, 0) for t in streams}
                min_et, max_et = times_map.get(person_id, (None, None))

                type_list = types_by_person.get(person_id, [])
                # Deterministic: already ordered by query (n desc, type asc) per table; merge then stable sort.
                type_list_sorted = sorted(type_list, key=lambda x: (-x[1], x[0]))
                top_types = [{"record_type": t, "rows": n} for t, n in type_list_sorted[:top_n]]

                per_person.append(
                    {
                        "canonical_person_id": person_id,
                        "rows_by_table": {k: int(by_table[k]) for k in sorted(by_table)},
                        "min_event_time": _fmt_ts(min_et),
                        "max_event_time": _fmt_ts(max_et),
                        "top_record_types": top_types,
                    }
                )

                batch += 1
                if batch >= 100:
                    task_people.advance(batch)
                    batch = 0
            if batch:
                task_people.advance(batch)

        with progress.phase("report: write artifacts"):
            task_write = progress.task("report: write artifacts", total=8, unit="files")

            # CSV: coverage_by_person.csv
            header = [
                "canonical_person_id",
                "observations_rows",
                "documents_rows",
                "medications_rows",
                "conditions_rows",
                "encounters_rows",
                "procedures_rows",
                "diagnostic_reports_rows",
                "min_event_time",
                "max_event_time",
            ]
            per_person_rows = []
            for p in per_person:
                rows_map = p.get("rows_by_table") if isinstance(p.get("rows_by_table"), dict) else {}
                per_person_rows.append(
                    [
                        p["canonical_person_id"],
                        int(rows_map.get("observations", 0)),
                        int(rows_map.get("documents", 0)),
                        int(rows_map.get("medications", 0)),
                        int(rows_map.get("conditions", 0)),
                        int(rows_map.get("encounters", 0)),
                        int(rows_map.get("procedures", 0)),
                        int(rows_map.get("diagnostic_reports", 0)),
                        p.get("min_event_time") or "",
                        p.get("max_event_time") or "",
                    ]
                )
            per_person_rows.sort(key=lambda r: str(r[0]))
            _write_csv(out / "coverage_by_person.csv", header=header, rows=per_person_rows)
            task_write.advance(1)

            # CSV: coverage_by_source.csv
            coverage_by_source_rows.sort(key=lambda r: (r[0], r[1]))
            _write_csv(
                out / "coverage_by_source.csv",
                header=["stream", "source", "rows"],
                rows=[[stream, source, n] for stream, source, n in coverage_by_source_rows],
            )
            task_write.advance(1)

            # CSV: coverage_by_source_system.csv
            coverage_by_source_system_rows.sort(key=lambda r: (r[0], r[1]))
            _write_csv(
                out / "coverage_by_source_system.csv",
                header=["stream", "source_system", "rows"],
                rows=[[stream, source_system, n] for stream, source_system, n in coverage_by_source_system_rows],
            )
            task_write.advance(1)

            # CSV: timeline_daily_counts.csv
            timeline_rows: list[tuple[str, str, str, int]] = []
            task_timeline = progress.task("report: timeline query", total=len(streams), unit="tables")
            for table in streams:
                for day, source, n in _rows(
                    con,
                    f"""
                    SELECT CAST(date_trunc('day', event_time) AS DATE) AS day, {source_bucket} AS source, COUNT(*) AS n
                    FROM {table}
                    WHERE event_time IS NOT NULL
                    GROUP BY 1, 2
                    ORDER BY 1, 2;
                    """,
                ):
                    if not isinstance(source, str):
                        continue
                    day_s = _fmt_ts(day)
                    if day_s is None:
                        continue
                    timeline_rows.append((day_s, table, source, int(n)))
                task_timeline.advance(1)
            timeline_rows.sort(key=lambda r: (r[0], r[1], r[2]))
            _write_csv(
                out / "timeline_daily_counts.csv",
                header=["day", "stream", "source", "rows"],
                rows=[[day, stream, source, n] for day, stream, source, n in timeline_rows],
            )
            task_write.advance(1)

            # CSV: unresolved reference integrity
            _write_csv(
                out / "reference_integrity_unresolved.csv",
                header=["reference_type", "rows"],
                rows=[[k, unresolved_by_type[k]] for k in sorted(unresolved_by_type)],
            )
            task_write.advance(1)

            coverage = {
                "schema_version": 1,
                "mode": mode,
                "resource_types": coverage_resource_types,
                "cda_sections": cda_sections,
                "notes": {
                    "privacy": "Share-safe: counts and structured labels only; no patient identifiers or free-text payloads.",
                    "determinism": "Stable ordering and formatting for identical DuckDB inputs.",
                },
            }
            _write_json(out / "coverage.json", coverage)
            task_write.advance(1)

            coverage_lines: list[str] = []
            coverage_lines.append("# Coverage Report")
            coverage_lines.append("")
            coverage_lines.append("## Resource Type Coverage")
            any_resource_rows = False
            for table in sorted(coverage_resource_types):
                coverage_lines.append(f"### {table}")
                rows_for_table = coverage_resource_types[table]
                if rows_for_table:
                    any_resource_rows = True
                    for row in rows_for_table:
                        coverage_lines.append(f"- {row['resource_type']}: {row['rows']}")
                else:
                    coverage_lines.append("- none")
                coverage_lines.append("")

            coverage_lines.append("## CDA Section Coverage")
            if cda_sections:
                for row in cda_sections:
                    label_parts = [row.get("section_title"), row.get("section_display"), row.get("section_code")]
                    label = " | ".join(part for part in label_parts if isinstance(part, str) and part)
                    coverage_lines.append(f"- {label}: {row['rows']}")
            else:
                coverage_lines.append("- none")
            coverage_lines.append("")

            if not any_resource_rows and not cda_sections:
                coverage_lines.append("No clinical record rows were present.")
                coverage_lines.append("")

            coverage_lines.append("## Privacy")
            coverage_lines.append("- Share-safe: only aggregate counts and structured resource/section labels are emitted.")
            coverage_lines.append("- No names, DOB, identifiers, timestamps, or note text are included.")
            _write_text_atomic(out / "coverage.md", "\n".join(coverage_lines) + "\n")
            task_write.advance(1)

        summary = {
            "schema_version": 1,
            "mode": mode,
            "db": {
                "path_redacted": True,
                "sha256": _sha256_file(db),
            },
            "tables": {k: tables_summary[k] for k in sorted(tables_summary)},
            "per_person": per_person,
            "reference_integrity": {
                "unresolved_reference_rows_total": unresolved_total,
                "rows_by_reference_type": {k: unresolved_by_type[k] for k in sorted(unresolved_by_type)},
                "clinical_rows_by_resource_type": {
                    k: unresolved_clinical_by_resource_type[k] for k in sorted(unresolved_clinical_by_resource_type)
                },
            },
            "notes": {
                "privacy": "Share-safe: no names/DOB/free-text patient identifiers. Reports key by canonical_person_id only.",
                "determinism": "No generated_at timestamps. Stable ordering and stable formatting for same DB bytes.",
            },
        }

        _write_json(out / "summary.json", summary)
        _write_text_atomic(out / "summary.md", _render_markdown(summary))
        task_write.advance(1)
    finally:
        con.close()


def _render_markdown(summary: dict[str, object]) -> str:
    tables = summary.get("tables")
    per_person = summary.get("per_person")
    if not isinstance(tables, dict):
        tables = {}
    if not isinstance(per_person, list):
        per_person = []
    reference_integrity = summary.get("reference_integrity")
    if not isinstance(reference_integrity, dict):
        reference_integrity = {}

    lines: list[str] = []
    lines.append("# HealthDelta Summary Report")
    lines.append("")
    lines.append("## Tables")
    for table_name in sorted(tables.keys()):
        info = tables.get(table_name)
        if not isinstance(info, dict):
            continue
        lines.append(f"### {table_name}")
        lines.append(f"- total_rows: {info.get('total_rows', 0)}")
        lines.append(f"- distinct_canonical_person_id: {info.get('distinct_canonical_person_id', 0)}")
        lines.append(f"- min_event_time: {info.get('min_event_time') or ''}")
        lines.append(f"- max_event_time: {info.get('max_event_time') or ''}")
        rbs = info.get("rows_by_source")
        if isinstance(rbs, dict):
            for source in sorted(rbs.keys()):
                lines.append(f"- rows_by_source.{source}: {rbs[source]}")
        lines.append("")

    lines.append("## Per Person")
    for p in sorted([x for x in per_person if isinstance(x, dict) and isinstance(x.get("canonical_person_id"), str)], key=lambda x: x["canonical_person_id"]):
        pid = p["canonical_person_id"]
        lines.append(f"### {pid}")
        rows_by_table = p.get("rows_by_table")
        if isinstance(rows_by_table, dict):
            for t in sorted(rows_by_table.keys()):
                lines.append(f"- rows.{t}: {rows_by_table[t]}")
        lines.append(f"- min_event_time: {p.get('min_event_time') or ''}")
        lines.append(f"- max_event_time: {p.get('max_event_time') or ''}")
        top = p.get("top_record_types")
        if isinstance(top, list) and top:
            lines.append("- top_record_types:")
            for item in top:
                if not isinstance(item, dict):
                    continue
                rt = item.get("record_type")
                n = item.get("rows")
                if isinstance(rt, str):
                    lines.append(f"  - {rt}: {n}")
    lines.append("")

    lines.append("## Reference Integrity")
    lines.append(f"- unresolved_reference_rows_total: {reference_integrity.get('unresolved_reference_rows_total', 0)}")
    by_type = reference_integrity.get("rows_by_reference_type")
    if isinstance(by_type, dict):
        for key in sorted(by_type.keys()):
            lines.append(f"- unresolved.{key}: {by_type[key]}")
    lines.append("")
    clinical_by_type = reference_integrity.get("clinical_rows_by_resource_type")
    if isinstance(clinical_by_type, dict) and clinical_by_type:
        lines.append("## Clinical Unresolved Reference Breakdown")
        for key in sorted(clinical_by_type.keys()):
            row = clinical_by_type.get(key)
            if not isinstance(row, dict):
                continue
            lines.append(f"- {key} -> {row.get('missing_reference_kind')}: {row.get('rows', 0)}")
        lines.append("")

    lines.append("## Notes")
    notes = summary.get("notes")
    if isinstance(notes, dict):
        for k in sorted(notes.keys()):
            lines.append(f"- {k}: {notes[k]}")
    return "\n".join(lines).rstrip() + "\n"


def show_report(*, db_path: str) -> None:
    db = Path(db_path)
    with progress.phase("report: show (connect)"):
        con = _connect_read_only(db)
    try:
        present = _tables_present(con)
        streams = [
            t
            for t in ["observations", "documents", "medications", "conditions", "encounters", "procedures", "diagnostic_reports"]
            if t in present
        ]
        print("HealthDelta Report (terminal)")
        print(f"tables={','.join(streams)}")
        for t in streams:
            n = int(_scalar(con, f"SELECT COUNT(*) FROM {t};") or 0)
            people = int(_scalar(con, f"SELECT COUNT(DISTINCT canonical_person_id) FROM {t};") or 0)
            print(f"{t}.rows={n}")
            print(f"{t}.distinct_people={people}")
    finally:
        con.close()
