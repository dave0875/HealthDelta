from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from healthdelta.progress import progress


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
        return d.astimezone(dt.timezone.utc).replace(tzinfo=None, microsecond=0)
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


def _add_column_if_missing(con, table: str, column: str, col_type: str) -> None:
    cols = set(_table_columns(con, table))
    if column in cols:
        return
    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type};")


def _create_unique_index_if_possible(con, *, name: str, table: str, column: str) -> None:
    try:
        con.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table}({column});")
    except Exception:
        # Index creation isn't strictly required for correctness; schema checks + NOT EXISTS inserts still dedupe.
        pass


def _flush_batch(con, *, insert_prefix: str, rows: list[list[object]], task) -> None:
    if not rows:
        return
    width = len(rows[0])
    placeholder_group = "(" + ",".join(["?"] * width) + ")"
    sql = insert_prefix + ",".join([placeholder_group] * len(rows)) + ";"
    params: list[object] = []
    for row in rows:
        params.extend(row)
    con.execute(sql, params)
    task.advance(len(rows))
    rows.clear()


def build_duckdb(*, input_dir: str, db_path: str, replace: bool = False) -> None:
    try:
        import duckdb
    except Exception as e:  # pragma: no cover
        raise RuntimeError("duckdb Python package is required (install dependency 'duckdb')") from e

    with progress.phase("duckdb: detect input layout"):
        input_root = Path(input_dir)
        ios_mode = False
        ios_run_id: str | None = None
        ios_source_file: str | None = None

        ios_manifest_path = input_root / "manifest.json"
        ios_ndjson_dir = input_root / "ndjson"
        if ios_manifest_path.exists() and ios_ndjson_dir.is_dir():
            observations_hint = ios_ndjson_dir / "observations.ndjson"
            if observations_hint.exists():
                ios_mode = True
                ios_source_file = "ndjson/observations.ndjson"
                try:
                    obj = json.loads(ios_manifest_path.read_text(encoding="utf-8"))
                    if isinstance(obj, dict) and isinstance(obj.get("run_id"), str) and obj.get("run_id"):
                        ios_run_id = obj["run_id"]
                except Exception:
                    ios_run_id = None

        ndjson_root = ios_ndjson_dir if ios_mode else input_root
        db = Path(db_path)

        db_existed = db.exists()
        if db_existed and replace:
            db.unlink()

        db.parent.mkdir(parents=True, exist_ok=True)

    with progress.phase("duckdb: connect"):
        con = duckdb.connect(database=str(db))
    try:
        with progress.phase("duckdb: init transaction"):
            con.execute("PRAGMA threads=1;")
            con.execute("PRAGMA enable_progress_bar=false;")
            con.execute("BEGIN;")
            con.execute(
                """
                CREATE OR REPLACE MACRO parse_canonical_ts(value) AS (
                  TRY_CAST(regexp_replace(trim(value), 'Z$', '') AS TIMESTAMP)
                );
                """
            )

        with progress.phase("duckdb: ensure schema"):
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                  schema_version INTEGER,
                  record_key VARCHAR,
                  canonical_person_id VARCHAR,
                  source VARCHAR,
                  source_system VARCHAR,
                  source_file VARCHAR,
                  event_time TIMESTAMP,
                  run_id VARCHAR,
                  event_key VARCHAR,
                  source_id VARCHAR,
                  record_id VARCHAR,
                  record_type VARCHAR,
                  observation_id VARCHAR,
                  subject_reference VARCHAR,
                  encounter_id VARCHAR,
                  effective_start TIMESTAMP,
                  effective_end TIMESTAMP,
                  hk_type VARCHAR,
                  sample_kind VARCHAR,
                  resource_type VARCHAR,
                  code_system VARCHAR,
                  code VARCHAR,
                  display VARCHAR,
                  value VARCHAR,
                  value_num DOUBLE,
                  value_text VARCHAR,
                  category_value INTEGER,
                  activity_type VARCHAR,
                  duration_seconds DOUBLE,
                  total_energy_burned_num DOUBLE,
                  total_energy_burned_unit VARCHAR,
                  total_distance_num DOUBLE,
                  total_distance_unit VARCHAR,
                  unit VARCHAR,
                  section_code VARCHAR,
                  section_display VARCHAR,
                  section_title VARCHAR,
                  components_json VARCHAR,
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
                  source_system VARCHAR,
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
        encounters_path = ndjson_root / "encounters.ndjson"
        procedures_path = ndjson_root / "procedures.ndjson"
        diagnostic_reports_path = ndjson_root / "diagnostic_reports.ndjson"

        if not observations_path.exists():
            raise FileNotFoundError("Missing required NDJSON stream: observations.ndjson")
        if not documents_path.exists() and not ios_mode:
            raise FileNotFoundError("Missing required NDJSON stream: documents.ndjson")

        with progress.phase("duckdb: schema checks"):
            _require_columns(con, "observations", ["record_key"])
            _require_columns(con, "documents", ["record_key"])
            _add_column_if_missing(con, "observations", "source_system", "VARCHAR")
            _add_column_if_missing(con, "observations", "record_id", "VARCHAR")
            _add_column_if_missing(con, "observations", "record_type", "VARCHAR")
            _add_column_if_missing(con, "observations", "observation_id", "VARCHAR")
            _add_column_if_missing(con, "observations", "subject_reference", "VARCHAR")
            _add_column_if_missing(con, "observations", "encounter_id", "VARCHAR")
            _add_column_if_missing(con, "observations", "effective_start", "TIMESTAMP")
            _add_column_if_missing(con, "observations", "effective_end", "TIMESTAMP")
            _add_column_if_missing(con, "observations", "code_system", "VARCHAR")
            _add_column_if_missing(con, "observations", "display", "VARCHAR")
            _add_column_if_missing(con, "observations", "sample_kind", "VARCHAR")
            _add_column_if_missing(con, "observations", "value_text", "VARCHAR")
            _add_column_if_missing(con, "observations", "category_value", "INTEGER")
            _add_column_if_missing(con, "observations", "activity_type", "VARCHAR")
            _add_column_if_missing(con, "observations", "duration_seconds", "DOUBLE")
            _add_column_if_missing(con, "observations", "total_energy_burned_num", "DOUBLE")
            _add_column_if_missing(con, "observations", "total_energy_burned_unit", "VARCHAR")
            _add_column_if_missing(con, "observations", "total_distance_num", "DOUBLE")
            _add_column_if_missing(con, "observations", "total_distance_unit", "VARCHAR")
            _add_column_if_missing(con, "observations", "section_code", "VARCHAR")
            _add_column_if_missing(con, "observations", "section_display", "VARCHAR")
            _add_column_if_missing(con, "observations", "section_title", "VARCHAR")
            _add_column_if_missing(con, "observations", "components_json", "VARCHAR")
            _add_column_if_missing(con, "documents", "source_system", "VARCHAR")
            _create_unique_index_if_possible(
                con, name="observations_record_key_uq", table="observations", column="record_key"
            )
            _create_unique_index_if_possible(con, name="documents_record_key_uq", table="documents", column="record_key")

        with progress.phase("duckdb: load observations"):
            task = progress.task("duckdb: load observations", unit="rows")
            append_only = not db_existed or replace
            observation_columns = [
                "schema_version",
                "record_key",
                "canonical_person_id",
                "source",
                "source_system",
                "source_file",
                "event_time",
                "run_id",
                "event_key",
                "source_id",
                "record_id",
                "record_type",
                "observation_id",
                "subject_reference",
                "encounter_id",
                "effective_start",
                "effective_end",
                "hk_type",
                "sample_kind",
                "resource_type",
                "code_system",
                "code",
                "display",
                "value",
                "value_num",
                "value_text",
                "category_value",
                "activity_type",
                "duration_seconds",
                "total_energy_burned_num",
                "total_energy_burned_unit",
                "total_distance_num",
                "total_distance_unit",
                "unit",
                "section_code",
                "section_display",
                "section_title",
                "components_json",
                "code_coding_json",
                "type_coding_json",
                "status",
            ]
            observation_columns_sql = ",\n                      ".join(observation_columns)
            if ios_mode and append_only:
                con.execute(
                    """
                    WITH src AS (
                      SELECT
                        json AS payload,
                        COALESCE(
                          NULLIF(json_extract_string(json, '$.record_key'), ''),
                          NULLIF(json_extract_string(json, '$.event_key'), '')
                        ) AS resolved_record_key,
                        ROW_NUMBER() OVER (
                          PARTITION BY COALESCE(
                            NULLIF(json_extract_string(json, '$.record_key'), ''),
                            NULLIF(json_extract_string(json, '$.event_key'), '')
                          )
                          ORDER BY
                            COALESCE(
                              json_extract_string(json, '$.start_time'),
                              json_extract_string(json, '$.event_time')
                            ),
                            COALESCE(json_extract_string(json, '$.sample_type'), ''),
                            COALESCE(json_extract_string(json, '$.unit'), '')
                        ) AS resolved_record_key_rank
                      FROM read_ndjson_objects(?)
                    )
                    INSERT INTO observations (
                      """
                    + observation_columns_sql
                    + """
                    )
                    SELECT
                      TRY_CAST(json_extract_string(payload, '$.schema_version') AS INTEGER),
                      resolved_record_key,
                      json_extract_string(payload, '$.canonical_person_id'),
                      json_extract_string(payload, '$.source'),
                      NULL,
                      ?,
                      COALESCE(
                        parse_canonical_ts(json_extract_string(payload, '$.event_time')),
                        parse_canonical_ts(json_extract_string(payload, '$.start_time'))
                      ),
                      ?,
                      COALESCE(NULLIF(json_extract_string(payload, '$.event_key'), ''), resolved_record_key),
                      json_extract_string(payload, '$.source_id'),
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      json_extract_string(payload, '$.sample_type'),
                      json_extract_string(payload, '$.sample_kind'),
                      NULL,
                      NULL,
                      NULL,
                      COALESCE(
                        json_extract_string(payload, '$.display'),
                        json_extract_string(payload, '$.value_text'),
                        json_extract_string(payload, '$.activity_type')
                      ),
                      COALESCE(
                        json_extract_string(payload, '$.value'),
                        json_extract_string(payload, '$.value_text'),
                        json_extract_string(payload, '$.value_num')
                      ),
                      COALESCE(
                        TRY_CAST(json_extract_string(payload, '$.value_num') AS DOUBLE),
                        TRY_CAST(json_extract_string(payload, '$.value') AS DOUBLE)
                      ),
                      json_extract_string(payload, '$.value_text'),
                      TRY_CAST(json_extract_string(payload, '$.category_value') AS INTEGER),
                      json_extract_string(payload, '$.activity_type'),
                      TRY_CAST(json_extract_string(payload, '$.duration_seconds') AS DOUBLE),
                      TRY_CAST(json_extract_string(payload, '$.total_energy_burned_num') AS DOUBLE),
                      json_extract_string(payload, '$.total_energy_burned_unit'),
                      TRY_CAST(json_extract_string(payload, '$.total_distance_num') AS DOUBLE),
                      json_extract_string(payload, '$.total_distance_unit'),
                      json_extract_string(payload, '$.unit'),
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      NULL
                    FROM src
                    WHERE resolved_record_key IS NOT NULL
                      AND resolved_record_key <> ''
                      AND resolved_record_key_rank = 1;
                    """,
                    [str(observations_path), ios_source_file, ios_run_id],
                )
                inserted = con.execute("SELECT COUNT(*) FROM observations;").fetchone()
                task.advance(int(inserted[0]) if inserted and inserted[0] is not None else 0)
            elif append_only:
                with progress.phase("duckdb: bulk load canonical observations"):
                    con.execute(
                        """
                        WITH src AS (
                          SELECT
                            json AS payload,
                            COALESCE(
                              NULLIF(json_extract_string(json, '$.record_key'), ''),
                              NULLIF(json_extract_string(json, '$.event_key'), '')
                            ) AS resolved_record_key,
                            ROW_NUMBER() OVER (
                              PARTITION BY COALESCE(
                                NULLIF(json_extract_string(json, '$.record_key'), ''),
                                NULLIF(json_extract_string(json, '$.event_key'), '')
                              )
                              ORDER BY
                                COALESCE(json_extract_string(json, '$.event_time'), ''),
                                COALESCE(json_extract_string(json, '$.source'), ''),
                                COALESCE(json_extract_string(json, '$.source_file'), '')
                            ) AS resolved_record_key_rank
                          FROM read_ndjson_objects(?)
                        )
                        INSERT INTO observations (
                          """
                        + observation_columns_sql
                        + """
                        )
                        SELECT
                          TRY_CAST(json_extract_string(payload, '$.schema_version') AS INTEGER),
                          resolved_record_key,
                          json_extract_string(payload, '$.canonical_person_id'),
                          json_extract_string(payload, '$.source'),
                          json_extract_string(payload, '$.source_system'),
                          json_extract_string(payload, '$.source_file'),
                          parse_canonical_ts(json_extract_string(payload, '$.event_time')),
                          json_extract_string(payload, '$.run_id'),
                          COALESCE(NULLIF(json_extract_string(payload, '$.event_key'), ''), resolved_record_key),
                          json_extract_string(payload, '$.source_id'),
                          json_extract_string(payload, '$.record_id'),
                          json_extract_string(payload, '$.record_type'),
                          json_extract_string(payload, '$.observation_id'),
                          json_extract_string(payload, '$.subject_reference'),
                          json_extract_string(payload, '$.encounter_id'),
                          parse_canonical_ts(json_extract_string(payload, '$.effective_start')),
                          parse_canonical_ts(json_extract_string(payload, '$.effective_end')),
                          COALESCE(
                            json_extract_string(payload, '$.hk_type'),
                            json_extract_string(payload, '$.sample_type')
                          ),
                          json_extract_string(payload, '$.sample_kind'),
                          json_extract_string(payload, '$.resource_type'),
                          json_extract_string(payload, '$.code_system'),
                          json_extract_string(payload, '$.code'),
                          COALESCE(
                            json_extract_string(payload, '$.display'),
                            json_extract_string(payload, '$.value_text'),
                            json_extract_string(payload, '$.activity_type')
                          ),
                          COALESCE(
                            json_extract_string(payload, '$.value'),
                            json_extract_string(payload, '$.value_num')
                          ),
                          COALESCE(
                            TRY_CAST(json_extract_string(payload, '$.value_num') AS DOUBLE),
                            TRY_CAST(json_extract_string(payload, '$.value') AS DOUBLE)
                          ),
                          json_extract_string(payload, '$.value_text'),
                          TRY_CAST(json_extract_string(payload, '$.category_value') AS INTEGER),
                          json_extract_string(payload, '$.activity_type'),
                          TRY_CAST(json_extract_string(payload, '$.duration_seconds') AS DOUBLE),
                          TRY_CAST(json_extract_string(payload, '$.total_energy_burned_num') AS DOUBLE),
                          json_extract_string(payload, '$.total_energy_burned_unit'),
                          TRY_CAST(json_extract_string(payload, '$.total_distance_num') AS DOUBLE),
                          json_extract_string(payload, '$.total_distance_unit'),
                          json_extract_string(payload, '$.unit'),
                          json_extract_string(payload, '$.section_code'),
                          json_extract_string(payload, '$.section_display'),
                          json_extract_string(payload, '$.section_title'),
                          CAST(json_extract(payload, '$.components') AS VARCHAR),
                          CAST(json_extract(payload, '$.code_coding') AS VARCHAR),
                          CAST(json_extract(payload, '$.type_coding') AS VARCHAR),
                          json_extract_string(payload, '$.status')
                        FROM src
                        WHERE resolved_record_key IS NOT NULL
                          AND resolved_record_key <> ''
                          AND resolved_record_key_rank = 1;
                        """,
                        [str(observations_path)],
                    )
                    inserted = con.execute("SELECT COUNT(*) FROM observations;").fetchone()
                    task.advance(int(inserted[0]) if inserted and inserted[0] is not None else 0)
            else:
                batch_rows: list[list[object]] = []
                seen_record_keys: set[str] = set()
                insert_prefix = f"""
                    INSERT INTO observations (
                      {observation_columns_sql}
                    )
                    VALUES
                    """
                dedupe_sql = f"""
                    INSERT INTO observations (
                      {observation_columns_sql}
                    )
                    SELECT {",".join(["?"] * len(observation_columns))}
                    WHERE NOT EXISTS (SELECT 1 FROM observations WHERE record_key=?);
                    """
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
                    if value is None and isinstance(obj.get("value_num"), (int, float)):
                        value = obj.get("value_num")
                    value_str = str(value) if value is not None else None
                    value_num = None
                    if isinstance(value, (int, float)):
                        value_num = float(value)
                    elif isinstance(value, str):
                        try:
                            value_num = float(value)
                        except ValueError:
                            value_num = None

                    row = [
                        obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                        record_key,
                        obj.get("canonical_person_id"),
                        obj.get("source"),
                        obj.get("source_system") if isinstance(obj.get("source_system"), str) else None,
                        obj.get("source_file") or ios_source_file,
                        _parse_event_time(obj.get("event_time") or obj.get("start_time")),
                        obj.get("run_id") or ios_run_id,
                        event_key,
                        obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                        obj.get("record_id") if isinstance(obj.get("record_id"), str) else None,
                        obj.get("record_type") if isinstance(obj.get("record_type"), str) else None,
                        obj.get("observation_id") if isinstance(obj.get("observation_id"), str) else None,
                        obj.get("subject_reference") if isinstance(obj.get("subject_reference"), str) else None,
                        obj.get("encounter_id") if isinstance(obj.get("encounter_id"), str) else None,
                        _parse_event_time(obj.get("effective_start")),
                        _parse_event_time(obj.get("effective_end")),
                        (obj.get("hk_type") if isinstance(obj.get("hk_type"), str) else None)
                        or (obj.get("sample_type") if isinstance(obj.get("sample_type"), str) else None),
                        obj.get("sample_kind") if isinstance(obj.get("sample_kind"), str) else None,
                        obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                        obj.get("code_system") if isinstance(obj.get("code_system"), str) else None,
                        obj.get("code") if isinstance(obj.get("code"), str) else None,
                        (obj.get("display") if isinstance(obj.get("display"), str) else None)
                        or (obj.get("value_text") if isinstance(obj.get("value_text"), str) else None)
                        or (obj.get("activity_type") if isinstance(obj.get("activity_type"), str) else None),
                        value_str,
                        value_num,
                        obj.get("value_text") if isinstance(obj.get("value_text"), str) else None,
                        obj.get("category_value") if isinstance(obj.get("category_value"), int) else None,
                        obj.get("activity_type") if isinstance(obj.get("activity_type"), str) else None,
                        float(obj.get("duration_seconds")) if isinstance(obj.get("duration_seconds"), (int, float)) else None,
                        float(obj.get("total_energy_burned_num")) if isinstance(obj.get("total_energy_burned_num"), (int, float)) else None,
                        obj.get("total_energy_burned_unit") if isinstance(obj.get("total_energy_burned_unit"), str) else None,
                        float(obj.get("total_distance_num")) if isinstance(obj.get("total_distance_num"), (int, float)) else None,
                        obj.get("total_distance_unit") if isinstance(obj.get("total_distance_unit"), str) else None,
                        obj.get("unit") if isinstance(obj.get("unit"), str) else None,
                        obj.get("section_code") if isinstance(obj.get("section_code"), str) else None,
                        obj.get("section_display") if isinstance(obj.get("section_display"), str) else None,
                        obj.get("section_title") if isinstance(obj.get("section_title"), str) else None,
                        _stable_json(obj.get("components")),
                        _stable_json(obj.get("code_coding")),
                        _stable_json(obj.get("type_coding")),
                        obj.get("status") if isinstance(obj.get("status"), str) else None,
                    ]

                    if append_only:
                        if record_key in seen_record_keys:
                            continue
                        seen_record_keys.add(record_key)
                        batch_rows.append(row)
                        if len(batch_rows) >= 1000:
                            _flush_batch(con, insert_prefix=insert_prefix, rows=batch_rows, task=task)
                        continue

                    con.execute(dedupe_sql, row + [record_key])
                    task.advance(1)

                if append_only:
                    _flush_batch(con, insert_prefix=insert_prefix, rows=batch_rows, task=task)

        if documents_path.exists():
            with progress.phase("duckdb: load documents"):
                task = progress.task("duckdb: load documents", unit="rows")
                batch = 0
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
                        SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?
                        WHERE NOT EXISTS (SELECT 1 FROM documents WHERE record_key=?);
                        """,
                        [
                            obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                            record_key,
                            obj.get("canonical_person_id"),
                            obj.get("source"),
                            obj.get("source_system") if isinstance(obj.get("source_system"), str) else None,
                            obj.get("source_file") or ("ndjson/documents.ndjson" if ios_mode else None),
                            _parse_event_time(obj.get("event_time")),
                            obj.get("run_id") or ios_run_id,
                            event_key,
                            obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                            obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                            obj.get("status") if isinstance(obj.get("status"), str) else None,
                            _stable_json(obj.get("type_coding")),
                            record_key,
                        ],
                    )

                    batch += 1
                    if batch >= 1000:
                        task.advance(batch)
                        batch = 0
                if batch:
                    task.advance(batch)

        if medications_path.exists():
            with progress.phase("duckdb: ensure schema (medications)"):
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS medications (
                      schema_version INTEGER,
                      record_key VARCHAR,
                      canonical_person_id VARCHAR,
                      source VARCHAR,
                      source_system VARCHAR,
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
                _add_column_if_missing(con, "medications", "source_system", "VARCHAR")
                _create_unique_index_if_possible(
                    con, name="medications_record_key_uq", table="medications", column="record_key"
                )

            with progress.phase("duckdb: load medications"):
                task = progress.task("duckdb: load medications", unit="rows")
                batch = 0
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
                        SELECT ?,?,?,?,?,?,?,?,?,?,?,?
                        WHERE NOT EXISTS (SELECT 1 FROM medications WHERE record_key=?);
                        """,
                        [
                            obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                            record_key,
                            obj.get("canonical_person_id"),
                            obj.get("source"),
                            obj.get("source_system") if isinstance(obj.get("source_system"), str) else None,
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

                    batch += 1
                    if batch >= 1000:
                        task.advance(batch)
                        batch = 0
                if batch:
                    task.advance(batch)

        if conditions_path.exists():
            with progress.phase("duckdb: ensure schema (conditions)"):
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conditions (
                      schema_version INTEGER,
                      record_key VARCHAR,
                      canonical_person_id VARCHAR,
                      source VARCHAR,
                      source_system VARCHAR,
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
                _add_column_if_missing(con, "conditions", "source_system", "VARCHAR")
                _create_unique_index_if_possible(
                    con, name="conditions_record_key_uq", table="conditions", column="record_key"
                )

            with progress.phase("duckdb: load conditions"):
                task = progress.task("duckdb: load conditions", unit="rows")
                batch = 0
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
                        SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?
                        WHERE NOT EXISTS (SELECT 1 FROM conditions WHERE record_key=?);
                        """,
                        [
                            obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                            record_key,
                            obj.get("canonical_person_id"),
                            obj.get("source"),
                            obj.get("source_system") if isinstance(obj.get("source_system"), str) else None,
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

                    batch += 1
                    if batch >= 1000:
                        task.advance(batch)
                        batch = 0
                if batch:
                    task.advance(batch)

        if encounters_path.exists():
            with progress.phase("duckdb: ensure schema (encounters)"):
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS encounters (
                      schema_version INTEGER,
                      record_key VARCHAR,
                      canonical_person_id VARCHAR,
                      source VARCHAR,
                      source_system VARCHAR,
                      source_file VARCHAR,
                      event_time TIMESTAMP,
                      run_id VARCHAR,
                      event_key VARCHAR,
                      source_id VARCHAR,
                      record_id VARCHAR,
                      record_type VARCHAR,
                      encounter_id VARCHAR,
                      subject_reference VARCHAR,
                      period_start TIMESTAMP,
                      period_end TIMESTAMP,
                      resource_type VARCHAR,
                      status VARCHAR,
                      class_code VARCHAR,
                      class_system VARCHAR
                    );
                    """
                )
                _require_columns(con, "encounters", ["record_key"])
                _add_column_if_missing(con, "encounters", "source_system", "VARCHAR")
                _add_column_if_missing(con, "encounters", "record_id", "VARCHAR")
                _add_column_if_missing(con, "encounters", "record_type", "VARCHAR")
                _add_column_if_missing(con, "encounters", "encounter_id", "VARCHAR")
                _add_column_if_missing(con, "encounters", "subject_reference", "VARCHAR")
                _add_column_if_missing(con, "encounters", "period_start", "TIMESTAMP")
                _add_column_if_missing(con, "encounters", "period_end", "TIMESTAMP")
                _create_unique_index_if_possible(
                    con, name="encounters_record_key_uq", table="encounters", column="record_key"
                )
                _create_unique_index_if_possible(
                    con, name="encounters_encounter_id_uq", table="encounters", column="encounter_id"
                )

            with progress.phase("duckdb: load encounters"):
                task = progress.task("duckdb: load encounters", unit="rows")
                batch = 0
                for obj in _iter_ndjson(encounters_path):
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
                        INSERT INTO encounters
                        SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                        WHERE NOT EXISTS (SELECT 1 FROM encounters WHERE record_key=?);
                        """,
                        [
                            obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                            record_key,
                            obj.get("canonical_person_id"),
                            obj.get("source"),
                            obj.get("source_system") if isinstance(obj.get("source_system"), str) else None,
                            obj.get("source_file"),
                            _parse_event_time(obj.get("event_time")),
                            obj.get("run_id"),
                            event_key,
                            obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                            obj.get("record_id") if isinstance(obj.get("record_id"), str) else None,
                            obj.get("record_type") if isinstance(obj.get("record_type"), str) else None,
                            obj.get("encounter_id") if isinstance(obj.get("encounter_id"), str) else None,
                            obj.get("subject_reference") if isinstance(obj.get("subject_reference"), str) else None,
                            _parse_event_time(obj.get("period_start")),
                            _parse_event_time(obj.get("period_end")),
                            obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                            obj.get("status") if isinstance(obj.get("status"), str) else None,
                            obj.get("class_code") if isinstance(obj.get("class_code"), str) else None,
                            obj.get("class_system") if isinstance(obj.get("class_system"), str) else None,
                            record_key,
                        ],
                    )

                    batch += 1
                    if batch >= 1000:
                        task.advance(batch)
                        batch = 0
                if batch:
                    task.advance(batch)

        if procedures_path.exists():
            with progress.phase("duckdb: ensure schema (procedures)"):
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS procedures (
                      schema_version INTEGER,
                      record_key VARCHAR,
                      canonical_person_id VARCHAR,
                      source VARCHAR,
                      source_system VARCHAR,
                      source_file VARCHAR,
                      event_time TIMESTAMP,
                      run_id VARCHAR,
                      event_key VARCHAR,
                      source_id VARCHAR,
                      resource_type VARCHAR,
                      status VARCHAR,
                      code VARCHAR,
                      code_coding_json VARCHAR
                    );
                    """
                )
                _require_columns(con, "procedures", ["record_key"])
                _add_column_if_missing(con, "procedures", "source_system", "VARCHAR")
                _create_unique_index_if_possible(
                    con, name="procedures_record_key_uq", table="procedures", column="record_key"
                )

            with progress.phase("duckdb: load procedures"):
                task = progress.task("duckdb: load procedures", unit="rows")
                batch = 0
                for obj in _iter_ndjson(procedures_path):
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
                        INSERT INTO procedures
                        SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,?
                        WHERE NOT EXISTS (SELECT 1 FROM procedures WHERE record_key=?);
                        """,
                        [
                            obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                            record_key,
                            obj.get("canonical_person_id"),
                            obj.get("source"),
                            obj.get("source_system") if isinstance(obj.get("source_system"), str) else None,
                            obj.get("source_file"),
                            _parse_event_time(obj.get("event_time")),
                            obj.get("run_id"),
                            event_key,
                            obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                            obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                            obj.get("status") if isinstance(obj.get("status"), str) else None,
                            obj.get("code") if isinstance(obj.get("code"), str) else None,
                            _stable_json(obj.get("code_coding")),
                            record_key,
                        ],
                    )

                    batch += 1
                    if batch >= 1000:
                        task.advance(batch)
                        batch = 0
                if batch:
                    task.advance(batch)

        if diagnostic_reports_path.exists():
            with progress.phase("duckdb: ensure schema (diagnostic_reports)"):
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS diagnostic_reports (
                      schema_version INTEGER,
                      record_key VARCHAR,
                      canonical_person_id VARCHAR,
                      source VARCHAR,
                      source_system VARCHAR,
                      source_file VARCHAR,
                      event_time TIMESTAMP,
                      run_id VARCHAR,
                      event_key VARCHAR,
                      source_id VARCHAR,
                      resource_type VARCHAR,
                      status VARCHAR,
                      code VARCHAR,
                      code_coding_json VARCHAR,
                      result_observation_record_keys_json VARCHAR
                    );
                    """
                )
                _require_columns(con, "diagnostic_reports", ["record_key"])
                _add_column_if_missing(con, "diagnostic_reports", "source_system", "VARCHAR")
                _create_unique_index_if_possible(
                    con, name="diagnostic_reports_record_key_uq", table="diagnostic_reports", column="record_key"
                )

            with progress.phase("duckdb: load diagnostic_reports"):
                task = progress.task("duckdb: load diagnostic_reports", unit="rows")
                batch = 0
                for obj in _iter_ndjson(diagnostic_reports_path):
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
                        INSERT INTO diagnostic_reports
                        SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                        WHERE NOT EXISTS (SELECT 1 FROM diagnostic_reports WHERE record_key=?);
                        """,
                        [
                            obj.get("schema_version") if isinstance(obj.get("schema_version"), int) else None,
                            record_key,
                            obj.get("canonical_person_id"),
                            obj.get("source"),
                            obj.get("source_system") if isinstance(obj.get("source_system"), str) else None,
                            obj.get("source_file"),
                            _parse_event_time(obj.get("event_time")),
                            obj.get("run_id"),
                            event_key,
                            obj.get("source_id") if isinstance(obj.get("source_id"), str) else None,
                            obj.get("resource_type") if isinstance(obj.get("resource_type"), str) else None,
                            obj.get("status") if isinstance(obj.get("status"), str) else None,
                            obj.get("code") if isinstance(obj.get("code"), str) else None,
                            _stable_json(obj.get("code_coding")),
                            _stable_json(obj.get("result_observation_record_keys")),
                            record_key,
                        ],
                    )

                    batch += 1
                    if batch >= 1000:
                        task.advance(batch)
                        batch = 0
                if batch:
                    task.advance(batch)

        with progress.phase("duckdb: commit"):
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
        raise FileNotFoundError(f"Missing DB file: {db.name}")

    with progress.phase("duckdb: query"):
        con = duckdb.connect(database=str(db), read_only=True)
        try:
            con.execute("PRAGMA threads=1;")
            res = con.execute(sql)
            columns = [c[0] for c in (res.description or [])]
            rows = res.fetchall()
        finally:
            con.close()

    _write_csv(columns=columns, rows=rows, out_path=Path(out_path) if out_path else None)
