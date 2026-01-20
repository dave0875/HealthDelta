from __future__ import annotations

import csv
import datetime as dt
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


def build_duckdb(*, input_dir: str, db_path: str, replace: bool = False) -> None:
    try:
        import duckdb
    except Exception as e:  # pragma: no cover
        raise RuntimeError("duckdb Python package is required (install dependency 'duckdb')") from e

    ndjson_root = Path(input_dir)
    db = Path(db_path)

    if db.exists():
        if not replace:
            raise FileExistsError(f"DB already exists (use --replace): {db}")
        db.unlink()

    db.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=str(db))
    try:
        con.execute("PRAGMA threads=1;")
        con.execute("PRAGMA enable_progress_bar=false;")

        con.execute(
            """
            CREATE TABLE observations (
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
            CREATE TABLE documents (
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

        con.execute(
            """
            INSERT INTO observations
            SELECT
              canonical_person_id::VARCHAR,
              source::VARCHAR,
              source_file::VARCHAR,
              try_cast(event_time as TIMESTAMP) as event_time,
              run_id::VARCHAR,
              event_key::VARCHAR,
              source_id::VARCHAR,
              hk_type::VARCHAR,
              resource_type::VARCHAR,
              code::VARCHAR,
              CASE WHEN value IS NULL THEN NULL ELSE value::VARCHAR END as value,
              try_cast(value as DOUBLE) as value_num,
              unit::VARCHAR,
              CASE WHEN code_coding IS NULL THEN NULL ELSE to_json(code_coding) END as code_coding_json,
              CASE WHEN type_coding IS NULL THEN NULL ELSE to_json(type_coding) END as type_coding_json,
              status::VARCHAR
            FROM read_json_auto(?, format='newline_delimited')
            ORDER BY event_time NULLS LAST, canonical_person_id, source, source_file, coalesce(source_id,''), event_key;
            """,
            [str(observations_path)],
        )

        con.execute(
            """
            INSERT INTO documents
            SELECT
              canonical_person_id::VARCHAR,
              source::VARCHAR,
              source_file::VARCHAR,
              try_cast(event_time as TIMESTAMP) as event_time,
              run_id::VARCHAR,
              event_key::VARCHAR,
              source_id::VARCHAR,
              resource_type::VARCHAR,
              status::VARCHAR,
              CASE WHEN type_coding IS NULL THEN NULL ELSE to_json(type_coding) END as type_coding_json
            FROM read_json_auto(?, format='newline_delimited')
            ORDER BY event_time NULLS LAST, canonical_person_id, source, source_file, coalesce(source_id,''), event_key;
            """,
            [str(documents_path)],
        )

        if medications_path.exists():
            con.execute(
                """
                CREATE TABLE medications (
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
            con.execute(
                """
                INSERT INTO medications
                SELECT
                  canonical_person_id::VARCHAR,
                  source::VARCHAR,
                  source_file::VARCHAR,
                  try_cast(event_time as TIMESTAMP) as event_time,
                  run_id::VARCHAR,
                  event_key::VARCHAR,
                  source_id::VARCHAR,
                  resource_type::VARCHAR,
                  status::VARCHAR
                FROM read_json_auto(?, format='newline_delimited')
                ORDER BY event_time NULLS LAST, canonical_person_id, source, source_file, coalesce(source_id,''), event_key;
                """,
                [str(medications_path)],
            )

        if conditions_path.exists():
            con.execute(
                """
                CREATE TABLE conditions (
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
            con.execute(
                """
                INSERT INTO conditions
                SELECT
                  canonical_person_id::VARCHAR,
                  source::VARCHAR,
                  source_file::VARCHAR,
                  try_cast(event_time as TIMESTAMP) as event_time,
                  run_id::VARCHAR,
                  event_key::VARCHAR,
                  source_id::VARCHAR,
                  resource_type::VARCHAR,
                  code::VARCHAR,
                  CASE WHEN code_coding IS NULL THEN NULL ELSE to_json(code_coding) END as code_coding_json
                FROM read_json_auto(?, format='newline_delimited')
                ORDER BY event_time NULLS LAST, canonical_person_id, source, source_file, coalesce(source_id,''), event_key;
                """,
                [str(conditions_path)],
            )

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

