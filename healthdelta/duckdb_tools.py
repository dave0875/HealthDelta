from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable


def _format_cell(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=dt.timezone.utc)
        v = v.astimezone(dt.timezone.utc).replace(microsecond=0)
        return v.isoformat().replace("+00:00", "Z")
    if isinstance(v, dt.date):
        return v.isoformat()
    return str(v)


def _write_csv(*, columns: list[str], rows: Iterable[tuple], out_path: Path | None) -> None:
    out_f = open(out_path, "w", encoding="utf-8", newline="") if out_path else None
    try:
        w = csv.writer(out_f or os.sys.stdout, lineterminator="\n")
        w.writerow(columns)
        for row in rows:
            w.writerow([_format_cell(v) for v in row])
    finally:
        if out_f:
            out_f.close()


def _parse_event_time(s: object) -> dt.datetime | None:
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip()
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc).replace(microsecond=0)
    except ValueError:
        return None


def _stable_json(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _iter_ndjson(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                yield obj


def _table_columns(con, table: str) -> list[str]:
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='main' AND table_name=?
        ORDER BY ordinal_position;
        """,
        [table],
    ).fetchall()
    return [c for (c,) in rows if isinstance(c, str)]


def _require_columns(con, table: str, required: list[str]) -> None:
    cols = set(_table_columns(con, table))
    missing = [c for c in required if c not in cols]
    if missing:
        raise RuntimeError(f"DB schema for table '{table}' is missing columns {missing}; rerun with --replace")


def _create_unique_index_if_possible(con, *, name: str, table: str, column: str) -> None:
    try:
        con.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table}({column});")
    except Exception:
        # Index creation isn't strictly required for correctness; schema checks + NOT EXISTS inserts still dedupe.
        pass


def build_duckdb(*, input_dir: str, db_path: str, replace: bool = False) -> None:
    try:
        import duckdb
    except Exception as e:  # pragma: no cover
        raise RuntimeError("duckdb Python package is required (install dependency 'duckdb')") from e

    ndjson_root = Path(input_dir)
    db = Path(db_path)

    db_existed = db.exists()
    if db_existed and replace:
        db.unlink()

    db.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=str(db))
    try:
        con.execute("PRAGMA threads=1;")
        con.execute("PRAGMA enable_progress_bar=false;")
        con.execute("BEGIN;")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS observations (
              schema_version INTEGER,
              record_key VARCHAR,
              canonical_person_id VARCHAR,
              source VARCHAR,
              source_file VARCHAR,
              event_time TIMESTAMP,
              run_id VARCHAR,
              event_key VARCHAR,
              source_id VARCHAR,
              hk_type VARCHAR,
              resource_type VARCHAR,
              code VARCHAR,
              value VARCHAR,
              value_num DOUBLE,
              unit VARCHAR,
              code_coding_json VARCHAR,
              type_coding_json VARCHAR,
              status VARCHAR
            );
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
              schema_version INTEGER,
              record_key VARCHAR,
              canonical_person_id VARCHAR,
              source VARCHAR,
              source_file VARCHAR,
              event_time TIMESTAMP,
              run_id VARCHAR,
              event_key VARCHAR,
              source_id VARCHAR,
              resource_type VARCHAR,
              status VARCHAR,
              type_coding_json VARCHAR
            );
            """
        )

        # Optional streams: created only if the stream exists.

        observations_path = ndjson_root / "observations.ndjson"
        documents_path = ndjson_root / "documents.ndjson"
        medications_path = ndjson_root / "medications.ndjson"
        conditions_path = ndjson_root / "conditions.ndjson"

        if not observations_path.exists():
            raise FileNotFoundError(f"Missing observations.ndjson: {observations_path}")
        if not documents_path.exists():
            raise FileNotFoundError(f"Missing documents.ndjson: {documents_path}")

        _require_columns(con, "observations", ["record_key"])
        _require_columns(con, "documents", ["record_key"])
        _create_unique_index_if_possible(con, name="observations_record_key_uq", table="observations", column="record_key")
        _create_unique_index_if_possible(con, name="documents_record_key_uq", table="documents", column="record_key")

        for obj in _iter_ndjson(observations_path):
            record_key = obj.get("record_key")
            if not isinstance(record_key, str) or not record_key:
                record_key = obj.get("event_key")
            if not isinstance(record_key, str) or not record_key:
                record_key = _sha256_text(_stable_json(obj) or "")

            event_key = obj.get("event_key")
            if not isinstance(event_key, str) or not event_key:
                event_key = record_key

            value = obj.get("value")
            value_str = str(value) if value is not None else None
            value_num = None
            if isinstance(value, (int, float)):
                value_num = float(value)
            elif isinstance(value, str):
                try:
                    value_num = float(value)
                except ValueError:
                    value_num = None

            con.execute(
                """
                INSERT INTO observations
                SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                WHERE NOT EXISTS (SELECT 1 FROM observations WHERE record_key=?);
                """,
                [
                    obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                    record_key,
                    obj.get("canonical_person_id"),
                    obj.get("source"),
                    obj.get("source_file"),
                    _parse_event_time(obj.get("event_time")),
                    obj.get("run_id"),
                    event_key,
                    obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                    obj.get("hk_type") if isinstance(obj.get("hk_type"), str) else None,
                    obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                    obj.get("code") if isinstance(obj.get("code"), str) else None,
                    value_str,
                    value_num,
                    obj.get("unit") if isinstance(obj.get("unit"), str) else None,
                    _stable_json(obj.get("code_coding")),
                    _stable_json(obj.get("type_coding")),
                    obj.get("status") if isinstance(obj.get("status"), str) else None,
                    record_key,
                ],
            )

        for obj in _iter_ndjson(documents_path):
            record_key = obj.get("record_key")
            if not isinstance(record_key, str) or not record_key:
                record_key = obj.get("event_key")
            if not isinstance(record_key, str) or not record_key:
                record_key = _sha256_text(_stable_json(obj) or "")

            event_key = obj.get("event_key")
            if not isinstance(event_key, str) or not event_key:
                event_key = record_key

            con.execute(
                """
                INSERT INTO documents
                SELECT ?,?,?,?,?,?,?,?,?,?,?,?
                WHERE NOT EXISTS (SELECT 1 FROM documents WHERE record_key=?);
                """,
                [
                    obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                    record_key,
                    obj.get("canonical_person_id"),
                    obj.get("source"),
                    obj.get("source_file"),
                    _parse_event_time(obj.get("event_time")),
                    obj.get("run_id"),
                    event_key,
                    obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                    obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                    obj.get("status") if isinstance(obj.get("status"), str) else None,
                    _stable_json(obj.get("type_coding")),
                    record_key,
                ],
            )

        if medications_path.exists():
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS medications (
                  schema_version INTEGER,
                  record_key VARCHAR,
                  canonical_person_id VARCHAR,
                  source VARCHAR,
                  source_file VARCHAR,
                  event_time TIMESTAMP,
                  run_id VARCHAR,
                  event_key VARCHAR,
                  source_id VARCHAR,
                  resource_type VARCHAR,
                  status VARCHAR
                );
                """
            )
            _require_columns(con, "medications", ["record_key"])
            _create_unique_index_if_possible(con, name="medications_record_key_uq", table="medications", column="record_key")
            for obj in _iter_ndjson(medications_path):
                record_key = obj.get("record_key")
                if not isinstance(record_key, str) or not record_key:
                    record_key = obj.get("event_key")
                if not isinstance(record_key, str) or not record_key:
                    record_key = _sha256_text(_stable_json(obj) or "")

                event_key = obj.get("event_key")
                if not isinstance(event_key, str) or not event_key:
                    event_key = record_key

                con.execute(
                    """
                    INSERT INTO medications
                    SELECT ?,?,?,?,?,?,?,?,?,?,?
                    WHERE NOT EXISTS (SELECT 1 FROM medications WHERE record_key=?);
                    """,
                    [
                        obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                        record_key,
                        obj.get("canonical_person_id"),
                        obj.get("source"),
                        obj.get("source_file"),
                        _parse_event_time(obj.get("event_time")),
                        obj.get("run_id"),
                        event_key,
                        obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                        obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                        obj.get("status") if isinstance(obj.get("status"), str) else None,
                        record_key,
                    ],
                )

        if conditions_path.exists():
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS conditions (
                  schema_version INTEGER,
                  record_key VARCHAR,
                  canonical_person_id VARCHAR,
                  source VARCHAR,
                  source_file VARCHAR,
                  event_time TIMESTAMP,
                  run_id VARCHAR,
                  event_key VARCHAR,
                  source_id VARCHAR,
                  resource_type VARCHAR,
                  code VARCHAR,
                  code_coding_json VARCHAR
                );
                """
            )
            _require_columns(con, "conditions", ["record_key"])
            _create_unique_index_if_possible(con, name="conditions_record_key_uq", table="conditions", column="record_key")
            for obj in _iter_ndjson(conditions_path):
                record_key = obj.get("record_key")
                if not isinstance(record_key, str) or not record_key:
                    record_key = obj.get("event_key")
                if not isinstance(record_key, str) or not record_key:
                    record_key = _sha256_text(_stable_json(obj) or "")

                event_key = obj.get("event_key")
                if not isinstance(event_key, str) or not event_key:
                    event_key = record_key

                con.execute(
                    """
                    INSERT INTO conditions
                    SELECT ?,?,?,?,?,?,?,?,?,?,?,?
                    WHERE NOT EXISTS (SELECT 1 FROM conditions WHERE record_key=?);
                    """,
                    [
                        obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                        record_key,
                        obj.get("canonical_person_id"),
                        obj.get("source"),
                        obj.get("source_file"),
                        _parse_event_time(obj.get("event_time")),
                        obj.get("run_id"),
                        event_key,
                        obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                        obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                        obj.get("code") if isinstance(obj.get("code"), str) else None,
                        _stable_json(obj.get("code_coding")),
                        record_key,
                    ],
                )

        con.execute("COMMIT;")
        con.execute("CHECKPOINT;")
    finally:
        con.close()


def query_duckdb(*, db_path: str, sql: str, out_path: str | None = None) -> None:
    try:
        import duckdb
    except Exception as e:  # pragma: no cover
        raise RuntimeError("duckdb Python package is required (install dependency 'duckdb')") from e

    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Missing DB: {db}")

    con = duckdb.connect(database=str(db), read_only=True)
    try:
        con.execute("PRAGMA threads=1;")
        res = con.execute(sql)
        columns = [c[0] for c in (res.description or [])]
        rows = res.fetchall()
    finally:
        con.close()

    _write_csv(columns=columns, rows=rows, out_path=Path(out_path) if out_path else None)
