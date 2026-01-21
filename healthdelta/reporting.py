from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable


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


def build_report(*, db_path: str, out_dir: str, mode: str = "local") -> None:
    if mode not in {"local", "share"}:
        raise ValueError("--mode must be one of: local, share")

    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Missing DB: {db}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    con = _connect_read_only(db)
    try:
        present = _tables_present(con)
        streams = [t for t in ["conditions", "documents", "medications", "observations"] if t in present]

        tables_summary: dict[str, dict[str, object]] = {}
        coverage_by_source_rows: list[tuple[str, str, int]] = []

        for table in streams:
            total_rows = int(_scalar(con, f"SELECT COUNT(*) FROM {table};") or 0)
            distinct_people = int(_scalar(con, f"SELECT COUNT(DISTINCT canonical_person_id) FROM {table};") or 0)
            min_et = _scalar(con, f"SELECT MIN(event_time) FROM {table} WHERE event_time IS NOT NULL;")
            max_et = _scalar(con, f"SELECT MAX(event_time) FROM {table} WHERE event_time IS NOT NULL;")

            by_source = _rows(con, f"SELECT source, COUNT(*) AS n FROM {table} GROUP BY source ORDER BY source;")
            by_source_map: dict[str, int] = {}
            for source, n in by_source:
                if isinstance(source, str):
                    by_source_map[source] = int(n)
                    coverage_by_source_rows.append((table, source, int(n)))

            tables_summary[table] = {
                "total_rows": total_rows,
                "distinct_canonical_person_id": distinct_people,
                "min_event_time": _fmt_ts(min_et),
                "max_event_time": _fmt_ts(max_et),
                "rows_by_source": {k: by_source_map[k] for k in sorted(by_source_map)},
            }

        # Per-person coverage across all available tables
        if not streams:
            people: list[str] = []
        else:
            union = " UNION ".join([f"SELECT DISTINCT canonical_person_id FROM {t}" for t in streams])
            people = [p for (p,) in _rows(con, f"{union} ORDER BY canonical_person_id;") if isinstance(p, str)]

        rows_by_table: dict[str, dict[str, int]] = {t: {} for t in streams}
        for t in streams:
            for person_id, n in _rows(con, f"SELECT canonical_person_id, COUNT(*) FROM {t} GROUP BY canonical_person_id ORDER BY canonical_person_id;"):
                if isinstance(person_id, str):
                    rows_by_table[t][person_id] = int(n)

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

        types_by_person: dict[str, list[tuple[str, int]]] = {p: [] for p in people}
        for pid, type_key, n in type_rows:
            if pid in types_by_person:
                types_by_person[pid].append((type_key, n))

        per_person: list[dict[str, object]] = []
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

        # CSV: coverage_by_person.csv
        header = [
            "canonical_person_id",
            "observations_rows",
            "documents_rows",
            "medications_rows",
            "conditions_rows",
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
                    p.get("min_event_time") or "",
                    p.get("max_event_time") or "",
                ]
            )
        per_person_rows.sort(key=lambda r: str(r[0]))
        _write_csv(out / "coverage_by_person.csv", header=header, rows=per_person_rows)

        # CSV: coverage_by_source.csv
        coverage_by_source_rows.sort(key=lambda r: (r[0], r[1]))
        _write_csv(
            out / "coverage_by_source.csv",
            header=["stream", "source", "rows"],
            rows=[[stream, source, n] for stream, source, n in coverage_by_source_rows],
        )

        # CSV: timeline_daily_counts.csv
        timeline_rows: list[tuple[str, str, str, int]] = []
        for table in streams:
            for day, source, n in _rows(
                con,
                f"""
                SELECT CAST(date_trunc('day', event_time) AS DATE) AS day, source, COUNT(*) AS n
                FROM {table}
                WHERE event_time IS NOT NULL
                GROUP BY day, source
                ORDER BY day, source;
                """,
            ):
                if not isinstance(source, str):
                    continue
                day_s = _fmt_ts(day)
                if day_s is None:
                    continue
                timeline_rows.append((day_s, table, source, int(n)))
        timeline_rows.sort(key=lambda r: (r[0], r[1], r[2]))
        _write_csv(
            out / "timeline_daily_counts.csv",
            header=["day", "stream", "source", "rows"],
            rows=[[day, stream, source, n] for day, stream, source, n in timeline_rows],
        )

        summary = {
            "schema_version": 1,
            "mode": mode,
            "db": {
                "path_redacted": True,
                "sha256": _sha256_file(db),
            },
            "tables": {k: tables_summary[k] for k in sorted(tables_summary)},
            "per_person": per_person,
            "notes": {
                "privacy": "Share-safe: no names/DOB/free-text patient identifiers. Reports key by canonical_person_id only.",
                "determinism": "No generated_at timestamps. Stable ordering and stable formatting for same DB bytes.",
            },
        }

        _write_json(out / "summary.json", summary)
        _write_text_atomic(out / "summary.md", _render_markdown(summary))
    finally:
        con.close()


def _render_markdown(summary: dict[str, object]) -> str:
    tables = summary.get("tables")
    per_person = summary.get("per_person")
    if not isinstance(tables, dict):
        tables = {}
    if not isinstance(per_person, list):
        per_person = []

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

    lines.append("## Notes")
    notes = summary.get("notes")
    if isinstance(notes, dict):
        for k in sorted(notes.keys()):
            lines.append(f"- {k}: {notes[k]}")
    return "\n".join(lines).rstrip() + "\n"


def show_report(*, db_path: str) -> None:
    db = Path(db_path)
    con = _connect_read_only(db)
    try:
        present = _tables_present(con)
        streams = [t for t in ["observations", "documents", "medications", "conditions"] if t in present]
        print("HealthDelta Report (terminal)")
        print(f"tables={','.join(streams)}")
        for t in streams:
            n = int(_scalar(con, f"SELECT COUNT(*) FROM {t};") or 0)
            people = int(_scalar(con, f"SELECT COUNT(DISTINCT canonical_person_id) FROM {t};") or 0)
            print(f"{t}.rows={n}")
            print(f"{t}.distinct_people={people}")
    finally:
        con.close()

