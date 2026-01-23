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
            tables = [t for t in ["observations", "documents", "medications", "conditions"] if t in present]

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
            union_et = union_all("event_time")
            if union_et is not None:
                min_et = _scalar(con, f"SELECT MIN(event_time) FROM ({union_et}) WHERE event_time IS NOT NULL;")
                max_et = _scalar(con, f"SELECT MAX(event_time) FROM ({union_et}) WHERE event_time IS NOT NULL;")
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
            task = progress.task("note: compute totals", total=4, unit="tables")
            for t in ["observations", "documents", "medications", "conditions"]:
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
                top = raw[:5]
                signals = ";".join([f"{k}:{v}" for k, v in top])

        # Build <= ~25 lines, deterministic order.
        lines: list[str] = []
        lines.append("HealthDelta Summary")
        lines.append(f"run_id={run_id_val}")
        lines.append(f"generated_at={generated_at}")
        lines.append(f"people={people}")
        if min_et_s and max_et_s:
            lines.append(f"event_time_range={min_et_s}..{max_et_s}")
        else:
            lines.append("event_time_range=")
        lines.append(f"totals.observations={totals['observations']}")
        lines.append(f"totals.documents={totals['documents']}")
        lines.append(f"totals.medications={totals['medications']}")
        lines.append(f"totals.conditions={totals['conditions']}")
        lines.append(f"sources.healthkit={sources['healthkit']}")
        lines.append(f"sources.fhir={sources['fhir']}")
        lines.append(f"sources.cda={sources['cda']}")
        if signals:
            lines.append(f"signals.top_observations={signals}")
        lines.append("No names, dates of birth, or identifying text included.")

        text = "\n".join(lines) + "\n"
        with progress.phase("note: write artifacts"):
            task = progress.task("note: write artifacts", total=2, unit="files")
            _write_text_atomic(out / "doctor_note.txt", text)
            task.advance(1)
            _write_text_atomic(out / "doctor_note.md", text)
            task.advance(1)
    finally:
        con.close()
