from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import time
import zipfile
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import duckdb

from healthdelta.deid import deidentify_run
from healthdelta.duckdb_tools import build_duckdb
from healthdelta.identity import build_identity
from healthdelta.ingest import ingest_to_staging
from healthdelta.note import build_doctor_note
from healthdelta.ndjson_export import export_ndjson
from healthdelta.qa import answer_question
from healthdelta.reporting import build_report
from healthdelta.risk_flags import build_risk_flags
from healthdelta.time_utils import UTC
from healthdelta.trends import build_trend_analysis
from healthdelta.upload_plane import UploadPlane, UploadPlaneError
from healthdelta.version import get_build_info


def healthz_payload() -> dict[str, Any]:
    return {"ok": True}


def version_payload() -> dict[str, Any]:
    info = get_build_info()
    return {
        "version": info.get("version"),
        "git_sha": info.get("git_sha"),
    }


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_identity_tokens(identity_dir: Path) -> set[str]:
    people_path = identity_dir / "people.json"
    if not people_path.exists():
        return set()
    obj = _read_json(people_path)
    people = obj.get("people") if isinstance(obj, dict) else None
    if not isinstance(people, list):
        return set()
    out: set[str] = set()
    for row in people:
        if not isinstance(row, dict):
            continue
        first = row.get("first_norm")
        last = row.get("last_norm")
        if isinstance(first, str) and first.strip():
            out.add(first.strip().lower())
        if isinstance(last, str) and last.strip():
            out.add(last.strip().lower())
    return out


def _find_token_hits(text: str, tokens: set[str]) -> list[str]:
    hits: list[str] = []
    for token in sorted(tokens):
        if not token:
            continue
        pat = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
        if pat.search(text):
            hits.append(token)
    return hits


def _build_summary_from_ndjson(ndjson_dir: Path, *, citation_limit: int) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    counts: dict[str, int] = {}
    citations: list[dict[str, Any]] = []
    per_stream: dict[str, int] = {}
    total = 0

    for path in sorted(ndjson_dir.glob("*.ndjson"), key=lambda p: p.name):
        stream = path.stem
        stream_count = 0
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                stream_count += 1
                total += 1
                if len(citations) < citation_limit and per_stream.get(stream, 0) < 3:
                    citations.append(
                        {
                            "stream": stream,
                            "line": line_no,
                            "record_key": row.get("record_key"),
                            "source_file": row.get("source_file"),
                            "event_time": row.get("event_time"),
                        }
                    )
                    per_stream[stream] = per_stream.get(stream, 0) + 1
        if stream_count:
            counts[stream] = stream_count

    lines = ["HealthDelta Vertical Slice Summary", f"total_records={total}"]
    for stream, n in sorted(counts.items(), key=lambda kv: kv[0]):
        lines.append(f"records.{stream}={n}")
    lines.append("Share-safe mode enforced (de-id -> NDJSON).")
    return "\n".join(lines) + "\n", citations, counts


def _prepare_vertical_slice_assets(*, input_path: str, work_dir: str) -> dict[str, Any]:
    input_p = Path(input_path)
    if not input_p.exists():
        raise FileNotFoundError(f"input path not found: {input_p}")

    base = Path(work_dir)
    run_suffix = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    run_id = f"slice-{run_suffix}"
    run_root = base / run_id
    staging_root = run_root / "staging"
    identity_dir = run_root / "state" / "identity"
    deid_dir = run_root / "deid"
    ndjson_dir = run_root / "ndjson"
    log_path = run_root / "slice.log"

    run_root.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = [f"run_id={run_id}"]

    staged = ingest_to_staging(input_path=str(input_p), staging_root=str(staging_root), run_id_override=run_id)
    log_lines.append("step=ingest_to_staging status=ok")
    build_identity(staging_run_dir=str(staged), output_dir=str(identity_dir))
    log_lines.append("step=identity_build status=ok")
    deidentify_run(staging_run_dir=str(staged), identity_dir=str(identity_dir), out_dir=str(deid_dir))
    log_lines.append("step=deidentify_run status=ok")
    export_ndjson(input_dir=str(deid_dir), out_dir=str(ndjson_dir), mode="share")
    log_lines.append("step=export_ndjson status=ok")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return {
        "run_id": run_id,
        "run_root": run_root,
        "ndjson_dir": ndjson_dir,
        "slice_log": log_path,
        "identity_dir": identity_dir,
        "log_lines": log_lines,
    }


def _run_vertical_slice(*, input_path: str, work_dir: str, citation_limit: int = 12) -> dict[str, Any]:
    assets = _prepare_vertical_slice_assets(input_path=input_path, work_dir=work_dir)
    ndjson_dir = assets["ndjson_dir"]
    identity_dir = assets["identity_dir"]
    run_id = assets["run_id"]
    log_path = assets["slice_log"]
    log_lines = assets["log_lines"]

    summary, citations, counts = _build_summary_from_ndjson(ndjson_dir, citation_limit=citation_limit)
    risk_flags = build_risk_flags(ndjson_dir=str(ndjson_dir))
    trends = build_trend_analysis(ndjson_dir=str(ndjson_dir))
    tokens = _load_identity_tokens(identity_dir)
    scan_text = "\n".join(
        [summary, json.dumps(citations, sort_keys=True), json.dumps(risk_flags, sort_keys=True), json.dumps(trends, sort_keys=True), "\n".join(log_lines)]
    )
    hits = _find_token_hits(scan_text, tokens)
    if hits:
        raise RuntimeError(f"policy failure: banned PHI tokens detected in output/logs: {', '.join(sorted(hits))}")

    return {
        "ok": True,
        "run_id": run_id,
        "summary": summary,
        "counts_by_stream": [{"stream": k, "count": counts[k]} for k in sorted(counts.keys())],
        "citations": citations,
        "risk_flags": risk_flags,
        "trends": trends,
        "policy": {"phi_tokens_checked": sorted(tokens), "phi_token_hits": []},
        "artifacts": {
            "run_dir": run_id,
            "slice_log": "slice.log",
            "ndjson_dir": "ndjson",
        },
    }


def _run_grounded_qa(*, input_path: str, work_dir: str, question: str, citation_limit: int = 8) -> dict[str, Any]:
    assets = _prepare_vertical_slice_assets(input_path=input_path, work_dir=work_dir)
    ndjson_dir = assets["ndjson_dir"]
    identity_dir = assets["identity_dir"]
    run_id = assets["run_id"]
    log_lines = list(assets["log_lines"])
    qa = answer_question(ndjson_dir=str(ndjson_dir), question=question, citation_limit=citation_limit)
    log_lines.append(f"step=qa abstained={qa.get('abstained')}")
    tokens = _load_identity_tokens(identity_dir)
    hits = _find_token_hits("\n".join([json.dumps(qa, sort_keys=True), "\n".join(log_lines)]), tokens)
    if hits:
        raise RuntimeError(f"policy failure: banned PHI tokens detected in QA output/logs: {', '.join(sorted(hits))}")
    return {
        "ok": True,
        "run_id": run_id,
        "qa": qa,
        "policy": {"phi_tokens_checked": sorted(tokens), "phi_token_hits": []},
        "artifacts": {
            "run_dir": run_id,
            "slice_log": "slice.log",
            "ndjson_dir": "ndjson",
        },
    }


def _normalize_card_body(raw: str, *, fallback: str) -> str:
    cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip()).strip()
    return cleaned or fallback


def _parse_iso_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _bytes_label(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if size < 1024 or candidate == units[-1]:
            break
        size /= 1024.0
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


def _daily_totals_rows(daily_totals: dict[str, float]) -> list[dict[str, object]]:
    return [
        {"day": day, "total_value_num": round(float(daily_totals[day]), 2)}
        for day in sorted(daily_totals)
    ]


def _slug_card_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return token or "card"


def _analysis_paths(dataset_dir: Path) -> dict[str, Path]:
    analysis_root = dataset_dir / "analysis"
    return {
        "analysis_root": analysis_root,
        "extract_root": analysis_root / "input",
        "db_path": analysis_root / "duckdb" / "run.duckdb",
        "reports_dir": analysis_root / "reports",
        "note_dir": analysis_root / "note",
        "summary_json": analysis_root / "reports" / "summary.json",
        "summary_md": analysis_root / "reports" / "summary.md",
        "doctor_note_md": analysis_root / "note" / "doctor_note.md",
    }


def _safe_extract_zip(*, export_zip: Path, extract_root: Path) -> None:
    extract_root.mkdir(parents=True, exist_ok=True)
    resolved_root = extract_root.resolve()
    with zipfile.ZipFile(export_zip, "r") as archive:
        for member in archive.infolist():
            rel = Path(member.filename)
            target = (extract_root / rel).resolve()
            if target != resolved_root and resolved_root not in target.parents:
                raise ValueError(f"unsafe zip member path: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _find_extracted_run_dir(extract_root: Path) -> Path:
    candidates = sorted(
        {
            manifest.parent
            for manifest in extract_root.rglob("manifest.json")
            if manifest.is_file() and (manifest.parent / "ndjson" / "observations.ndjson").exists()
        },
        key=lambda p: p.as_posix(),
    )
    if not candidates:
        raise FileNotFoundError(f"no extracted iOS run directory found under {extract_root}")
    return candidates[0]


def _ensure_dataset_analysis(*, dataset_dir: Path, export_zip: Path) -> dict[str, Path]:
    paths = _analysis_paths(dataset_dir)
    if paths["summary_json"].exists() and paths["summary_md"].exists() and paths["doctor_note_md"].exists():
        return paths

    paths["analysis_root"].mkdir(parents=True, exist_ok=True)
    if not paths["extract_root"].exists():
        _safe_extract_zip(export_zip=export_zip, extract_root=paths["extract_root"])
    run_dir = _find_extracted_run_dir(paths["extract_root"])
    paths["db_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["reports_dir"].mkdir(parents=True, exist_ok=True)
    paths["note_dir"].mkdir(parents=True, exist_ok=True)
    build_duckdb(input_dir=str(run_dir), db_path=str(paths["db_path"]), replace=True)
    build_report(db_path=str(paths["db_path"]), out_dir=str(paths["reports_dir"]), mode="share")
    build_doctor_note(db_path=str(paths["db_path"]), out_dir=str(paths["note_dir"]), mode="share")
    return paths


def _read_json_or_empty(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _read_text_or_empty(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _parse_key_value_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _summary_table_info(summary_obj: dict[str, Any], table_name: str) -> dict[str, Any]:
    tables = summary_obj.get("tables")
    if not isinstance(tables, dict):
        return {}
    table = tables.get(table_name)
    return table if isinstance(table, dict) else {}


def _artifact_grounded_insight_cards(
    *,
    run_id: str,
    freshness: str,
    note_text: str,
    summary_obj: dict[str, Any],
) -> list[dict[str, str]]:
    note_fields = _parse_key_value_lines(note_text)
    observations = _summary_table_info(summary_obj, "observations")
    total_rows = int(observations.get("total_rows") or 0)
    min_event_time = str(observations.get("min_event_time") or note_fields.get("event_time_range", "").split("..")[0] or "").strip()
    max_event_time = str(observations.get("max_event_time") or (note_fields.get("event_time_range", "").split("..")[-1] if ".." in note_fields.get("event_time_range", "") else "") or "").strip()
    rows_by_source = observations.get("rows_by_source") if isinstance(observations.get("rows_by_source"), dict) else {}
    healthkit_rows = int(rows_by_source.get("healthkit") or note_fields.get("sources.healthkit") or 0)
    unresolved_total = 0
    reference_integrity = summary_obj.get("reference_integrity")
    if isinstance(reference_integrity, dict):
        unresolved_total = int(reference_integrity.get("unresolved_reference_rows_total") or 0)

    top_signal = note_fields.get("signals.top_observations", "")
    primary_signal = top_signal.split(";", 1)[0].split(":", 1)[0].replace("HKQuantityTypeIdentifier", "").strip() if top_signal else ""

    doctor_lines = []
    if total_rows:
        doctor_lines.append(f"ORIN analyzed {total_rows:,} observation rows from the latest uploaded run.")
    if min_event_time and max_event_time:
        doctor_lines.append(f"Observed window: {min_event_time} to {max_event_time}.")
    if primary_signal:
        doctor_lines.append(f"Primary observed signal in this upload: {primary_signal}.")
    if healthkit_rows:
        doctor_lines.append(f"HealthKit contributed {healthkit_rows:,} rows to the current analysis.")
    if not doctor_lines:
        doctor_lines.append("ORIN generated a deterministic doctor-note analysis for the latest uploaded run.")

    summary_lines = []
    if isinstance(reference_integrity, dict):
        summary_lines.append(f"Share-safe report unresolved clinical reference rows: {unresolved_total:,}.")
    if isinstance(rows_by_source, dict) and rows_by_source:
        source_parts = [f"{source}={int(rows_by_source[source]):,}" for source in sorted(rows_by_source)]
        summary_lines.append("Rows by source: " + ", ".join(source_parts) + ".")
    notes = summary_obj.get("notes")
    if isinstance(notes, dict) and isinstance(notes.get("privacy"), str):
        summary_lines.append(notes["privacy"])
    if not summary_lines:
        summary_lines.append("ORIN generated a share-safe summary report for the latest uploaded run.")

    return [
        {
            "id": f"{run_id}-orin-doctor-note",
            "title": "Doctor's Note",
            "body": _normalize_card_body("\n".join(doctor_lines), fallback="ORIN generated a doctor-note summary."),
            "disclaimer": "For education only. This is not medical advice.",
            "sourceLabel": "orin/analysis/note",
            "freshnessLabel": freshness,
        },
        {
            "id": f"{run_id}-orin-summary",
            "title": "Summary",
            "body": _normalize_card_body("\n".join(summary_lines), fallback="ORIN generated a summary report."),
            "disclaimer": "For education only. This is not medical advice.",
            "sourceLabel": "orin/analysis/reports",
            "freshnessLabel": freshness,
        },
    ]


def _filtered_observation_facts(
    *,
    db_path: Path,
    canonical_person_id: str | None,
    window_days: int | None,
) -> dict[str, Any] | None:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        clauses = ["1=1"]
        params: list[object] = []
        if canonical_person_id:
            clauses.append("canonical_person_id = ?")
            params.append(canonical_person_id)
        base_where = " AND ".join(clauses)
        max_event_time = con.execute(
            f"SELECT MAX(TRY_CAST(event_time AS TIMESTAMP)) FROM observations WHERE {base_where}",
            params,
        ).fetchone()[0]
        if max_event_time is None:
            return None

        filtered_clauses = list(clauses)
        filtered_params = list(params)
        if window_days is not None and window_days > 0:
            filtered_clauses.append("TRY_CAST(event_time AS TIMESTAMP) >= ?")
            filtered_params.append(max_event_time - timedelta(days=window_days))
        filtered_where = " AND ".join(filtered_clauses)

        row = con.execute(
            f"""
            SELECT
              COUNT(*) AS total_rows,
              MIN(TRY_CAST(event_time AS TIMESTAMP)) AS min_event_time,
              MAX(TRY_CAST(event_time AS TIMESTAMP)) AS max_event_time,
              COUNT(DISTINCT CAST(TRY_CAST(event_time AS DATE) AS VARCHAR)) AS active_days,
              COUNT(DISTINCT canonical_person_id) AS distinct_people
            FROM observations
            WHERE {filtered_where}
            """,
            filtered_params,
        ).fetchone()
        if row is None or int(row[0] or 0) == 0:
            return None

        rows_by_source = {
            str(source): int(count)
            for source, count in con.execute(
                f"""
                SELECT COALESCE(source, 'unknown') AS source, COUNT(*)
                FROM observations
                WHERE {filtered_where}
                GROUP BY 1
                ORDER BY 1
                """,
                filtered_params,
            ).fetchall()
        }
        top_signal_row = con.execute(
            f"""
            SELECT COALESCE(record_type, code, 'unknown') AS signal, COUNT(*) AS n
            FROM observations
            WHERE {filtered_where}
            GROUP BY 1
            ORDER BY n DESC, signal ASC
            LIMIT 1
            """,
            filtered_params,
        ).fetchone()

        return {
            "canonical_person_id": canonical_person_id,
            "window_days": window_days,
            "total_rows": int(row[0] or 0),
            "min_event_time": row[1].strftime("%Y-%m-%dT%H:%M:%SZ") if row[1] else None,
            "max_event_time": row[2].strftime("%Y-%m-%dT%H:%M:%SZ") if row[2] else None,
            "active_days": int(row[3] or 0),
            "distinct_people": int(row[4] or 0),
            "rows_by_source": rows_by_source,
            "top_signal": str(top_signal_row[0]) if top_signal_row else "",
        }
    finally:
        con.close()


def _filtered_note_text(*, facts: dict[str, Any]) -> str:
    lines = []
    if facts.get("canonical_person_id"):
        lines.append(f"canonical_person_id={facts['canonical_person_id']}")
    if facts.get("window_days") is not None:
        lines.append(f"window_days={facts['window_days']}")
    lines.append(f"total_rows={facts['total_rows']}")
    if facts.get("min_event_time") and facts.get("max_event_time"):
        lines.append(f"event_time_range={facts['min_event_time']}..{facts['max_event_time']}")
    if facts.get("top_signal"):
        lines.append(f"signals.top_observations={facts['top_signal']}")
    for source, count in sorted((facts.get("rows_by_source") or {}).items()):
        lines.append(f"sources.{source}={count}")
    return "\n".join(lines) + "\n"


def _filtered_insight_cards(*, run_id: str, freshness: str, facts: dict[str, Any]) -> list[dict[str, str]]:
    doctor_lines = [f"ORIN analyzed {int(facts['total_rows']):,} observation rows for the selected scope."]
    if facts.get("canonical_person_id"):
        doctor_lines.append("Filtered to the requested patient.")
    if facts.get("window_days") is not None:
        doctor_lines.append(f"Evaluation window: last {int(facts['window_days'])} days relative to the latest matching observation.")
    if facts.get("min_event_time") and facts.get("max_event_time"):
        doctor_lines.append(f"Observed window: {facts['min_event_time']} to {facts['max_event_time']}.")
    if facts.get("top_signal"):
        doctor_lines.append(f"Primary observed signal in this scope: {facts['top_signal']}.")

    summary_lines = [
        f"Active days in scope: {int(facts['active_days']):,}.",
        f"Distinct canonical people in scope: {int(facts['distinct_people']):,}.",
    ]
    rows_by_source = facts.get("rows_by_source") or {}
    if rows_by_source:
        source_parts = [f"{source}={int(rows_by_source[source]):,}" for source in sorted(rows_by_source)]
        summary_lines.append("Rows by source: " + ", ".join(source_parts) + ".")
    summary_lines.append("Share-safe: no names/DOB/free-text patient identifiers. Reports key by canonical_person_id only.")

    return [
        {
            "id": f"{run_id}-orin-filtered-doctor-note",
            "title": "Doctor's Note",
            "body": _normalize_card_body("\n".join(doctor_lines), fallback="ORIN generated a scoped doctor-note summary."),
            "disclaimer": "For education only. This is not medical advice.",
            "sourceLabel": "orin/analysis/note",
            "freshnessLabel": freshness,
        },
        {
            "id": f"{run_id}-orin-filtered-summary",
            "title": "Summary",
            "body": _normalize_card_body("\n".join(summary_lines), fallback="ORIN generated a scoped summary report."),
            "disclaimer": "For education only. This is not medical advice.",
            "sourceLabel": "orin/analysis/reports",
            "freshnessLabel": freshness,
        },
    ]


def _decode_json_object_from_text(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _build_ollama_prompt(
    *,
    run_id: str,
    note_text: str,
    summary_obj: dict[str, Any],
    fallback_cards: list[dict[str, str]],
) -> str:
    payload = {
        "run_id": run_id,
        "doctor_note": note_text,
        "summary_json": summary_obj,
        "fallback_cards": [{"title": card["title"], "body": card["body"]} for card in fallback_cards],
    }
    return "\n".join(
        [
            "Return JSON only. No markdown. No preface. No code fences.",
            "Use only the artifact-grounded facts below.",
            "Do not mention names, identifiers, diagnoses, disease labels, or treatment instructions.",
            "Do not invent tables, signals, or trends that are not present.",
            "Return exactly this shape with exactly 2 cards:",
            '{"cards":[{"title":"Card title","body":"One or two short sentences."},{"title":"Card title","body":"One or two short sentences."}]}',
            "Facts:",
            json.dumps(payload, sort_keys=True),
        ]
    )


def _ollama_refined_insight_cards(
    *,
    run_id: str,
    freshness: str,
    note_text: str,
    summary_obj: dict[str, Any],
    fallback_cards: list[dict[str, str]],
) -> list[dict[str, str]] | None:
    base_url = os.getenv("HEALTHDELTA_OLLAMA_BASE_URL", "").strip()
    if not base_url:
        return None
    model = os.getenv("HEALTHDELTA_OLLAMA_MODEL", "llama3.2:latest").strip() or "llama3.2:latest"
    timeout_s = float(os.getenv("HEALTHDELTA_OLLAMA_TIMEOUT_S", "20").strip() or "20")
    ollama_num_gpu = int(os.getenv("HEALTHDELTA_OLLAMA_NUM_GPU", "0").strip() or "0")
    try:
        endpoint = base_url.rstrip("/") + "/api/generate"
        body = json.dumps(
            {
                "model": model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2, "num_gpu": ollama_num_gpu},
                "prompt": _build_ollama_prompt(
                    run_id=run_id,
                    note_text=note_text,
                    summary_obj=summary_obj,
                    fallback_cards=fallback_cards,
                ),
            }
        ).encode("utf-8")
        req = Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=timeout_s) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        response_text = raw.get("response") if isinstance(raw, dict) else None
        if not isinstance(response_text, str) or not response_text.strip():
            return None
        decoded = _decode_json_object_from_text(response_text)
        cards = decoded.get("cards") if isinstance(decoded, dict) else None
        if not isinstance(cards, list):
            return None

        out: list[dict[str, str]] = []
        for idx, row in enumerate(cards[:3], start=1):
            if not isinstance(row, dict):
                continue
            title = row.get("title")
            body_text = row.get("body")
            if not isinstance(title, str) or not title.strip():
                continue
            if not isinstance(body_text, str) or not body_text.strip():
                continue
            out.append(
                {
                    "id": f"{run_id}-orin-ollama-{idx}-{_slug_card_token(title)}",
                    "title": title.strip(),
                    "body": _normalize_card_body(
                        body_text,
                        fallback="ORIN generated an empty insight response.",
                    ),
                    "disclaimer": "For education only. This is not medical advice.",
                    "sourceLabel": "orin/ollama",
                    "freshnessLabel": freshness,
                }
            )
        if not out:
            return None
        if len(out) == 1:
            out.append(fallback_cards[-1])
        return out
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def _read_current_dataset_insights(
    *,
    plane: UploadPlane,
    canonical_person_id: str | None = None,
    window_days: int | None = None,
) -> dict[str, Any]:
    try:
        current = plane.get_current_dataset()
    except UploadPlaneError as exc:
        if exc.code == "no_current_dataset":
            return {
                "status": "no_insights_yet",
                "detail": "Upload a completed run to ORIN before fetching insights.",
                "cards": [],
            }
        raise

    export_zip = Path(str(current["export_zip"]))
    if not export_zip.exists():
        raise FileNotFoundError(f"dataset export zip missing: {export_zip}")
    dataset_dir = Path(str(current["path"]))
    analysis = _ensure_dataset_analysis(dataset_dir=dataset_dir, export_zip=export_zip)
    summary_obj = _read_json_or_empty(analysis["summary_json"])
    note_text = _read_text_or_empty(analysis["doctor_note_md"])
    run_id = str(current.get("dataset") or "current")
    if note_text:
        note_fields = _parse_key_value_lines(note_text)
        if note_fields.get("run_id"):
            run_id = note_fields["run_id"]

    updated_at = str(current.get("updated_at") or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    freshness = f"Updated {updated_at}"
    if canonical_person_id or window_days is not None:
        facts = _filtered_observation_facts(
            db_path=analysis["db_path"],
            canonical_person_id=canonical_person_id,
            window_days=window_days,
        )
        if facts is None:
            detail_parts = ["The selected insights filter did not match any observation rows in the current dataset."]
            if canonical_person_id:
                detail_parts.append("Try a different canonical person ID or leave the field blank for all patients.")
            if window_days is not None:
                detail_parts.append("Try a longer evaluation window or choose All data.")
            return {
                "status": "no_insights_yet",
                "detail": " ".join(detail_parts),
                "cards": [],
            }

        filtered_summary_obj = {
            "filter_context": {
                "canonical_person_id": canonical_person_id,
                "window_days": window_days,
            },
            "filtered_facts": facts,
        }
        filtered_note_text = _filtered_note_text(facts=facts)
        fallback_cards = _filtered_insight_cards(
            run_id=run_id,
            freshness=freshness,
            facts=facts,
        )
        cards = _ollama_refined_insight_cards(
            run_id=run_id,
            freshness=freshness,
            note_text=filtered_note_text,
            summary_obj=filtered_summary_obj,
            fallback_cards=fallback_cards,
        )
        if cards is None:
            cards = fallback_cards
        return {
            "status": "ok",
            "dataset": current.get("dataset"),
            "cards": cards,
        }

    fallback_cards = _artifact_grounded_insight_cards(
        run_id=run_id,
        freshness=freshness,
        note_text=note_text,
        summary_obj=summary_obj,
    )
    cards = _ollama_refined_insight_cards(
        run_id=run_id,
        freshness=freshness,
        note_text=note_text,
        summary_obj=summary_obj,
        fallback_cards=fallback_cards,
    )
    if cards is None:
        cards = fallback_cards

    return {
        "status": "ok",
        "dataset": current.get("dataset"),
        "cards": cards,
    }


def _read_current_dataset_patients(*, plane: UploadPlane) -> dict[str, Any]:
    current = plane.get_current_dataset()
    export_zip = Path(str(current["export_zip"]))
    if not export_zip.exists():
        raise FileNotFoundError(f"dataset export zip missing: {export_zip}")
    dataset_dir = Path(str(current["path"]))
    analysis = _ensure_dataset_analysis(dataset_dir=dataset_dir, export_zip=export_zip)
    coverage_by_person = analysis["reports_dir"] / "coverage_by_person.csv"
    if not coverage_by_person.exists():
        return {"dataset": current.get("dataset"), "patients": []}

    patients: list[dict[str, Any]] = []
    with coverage_by_person.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        ranked_rows: list[dict[str, Any]] = []
        for row in reader:
            canonical_person_id = (row.get("canonical_person_id") or "").strip()
            if not canonical_person_id:
                continue
            row_count = 0
            for key, raw_value in row.items():
                if not key.endswith("_rows"):
                    continue
                try:
                    row_count += int((raw_value or "0").strip() or "0")
                except Exception:
                    continue
            if row_count <= 0:
                continue
            ranked_rows.append(
                {
                    "canonical_person_id": canonical_person_id,
                    "row_count": row_count,
                    "min_event_time": (row.get("min_event_time") or "").strip() or None,
                    "max_event_time": (row.get("max_event_time") or "").strip() or None,
                }
            )

    ranked_rows.sort(
        key=lambda row: (
            1 if row["canonical_person_id"] == "unresolved" else 0,
            -int(row["row_count"]),
            str(row["canonical_person_id"]),
        )
    )

    resolved_index = 0
    for row in ranked_rows:
        canonical_person_id = str(row["canonical_person_id"])
        if canonical_person_id == "unresolved":
            display_label = "Unresolved records"
        else:
            resolved_index += 1
            display_label = f"Patient {resolved_index}"
        patients.append(
            {
                "canonical_person_id": canonical_person_id,
                "display_label": display_label,
                "row_count": int(row["row_count"]),
                "min_event_time": row["min_event_time"],
                "max_event_time": row["max_event_time"],
            }
        )

    return {
        "dataset": current.get("dataset"),
        "patients": patients,
    }


class _Handler(BaseHTTPRequestHandler):
    _session_status_re = re.compile(r"^/upload-sessions/([A-Za-z0-9]+)$")
    _chunk_put_re = re.compile(r"^/upload-sessions/([A-Za-z0-9]+)/chunks/(\d+)$")
    _session_finalize_re = re.compile(r"^/upload-sessions/([A-Za-z0-9]+)/finalize$")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _log_event(self, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "ts": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            "method": self.command,
            "path": self.path,
            "remote": self.client_address[0] if self.client_address else "",
        }
        payload.update(fields)
        print(json.dumps(payload, sort_keys=True), flush=True)

    def _upload_plane(self) -> UploadPlane:
        data_root = Path(os.getenv("HEALTHDELTA_DATA_DIR", "/data"))
        return UploadPlane(data_root)

    def _authorize_upload(self) -> bool:
        token = os.getenv("HEALTHDELTA_UPLOAD_TOKEN", "").strip()
        if not token:
            self._send_json(
                503,
                {
                    "error": "upload_unavailable",
                    "detail": "upload endpoints are disabled; set HEALTHDELTA_UPLOAD_TOKEN to enable them",
                },
            )
            self._log_event("upload_auth_rejected", status=503, reason="token_unset")
            return False
        authz = self.headers.get("Authorization", "")
        if authz != f"Bearer {token}":
            self._send_json(401, {"error": "unauthorized", "detail": "expected Authorization: Bearer <token>"})
            self._log_event("upload_auth_rejected", status=401, reason="invalid_bearer")
            return False
        return True

    def _read_json_body(self) -> dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise UploadPlaneError(400, "invalid_content_length", "Content-Length must be a valid integer")
        if content_length < 0:
            raise UploadPlaneError(400, "invalid_content_length", "Content-Length must be >= 0")
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise UploadPlaneError(400, "invalid_json", f"request body is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise UploadPlaneError(400, "invalid_payload", "request JSON must be an object")
        return payload

    def _read_raw_body(self) -> bytes:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise UploadPlaneError(400, "invalid_content_length", "Content-Length must be a valid integer")
        if content_length <= 0:
            raise UploadPlaneError(400, "invalid_content_length", "Content-Length must be > 0 for chunk upload")
        return self.rfile.read(content_length)

    def _send_json(self, status: int, obj: object) -> None:
        body = (json.dumps(obj, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._log_event("request_received")
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)
        if route == "/healthz":
            self._send_json(200, healthz_payload())
            self._log_event("request_succeeded", status=200)
            return
        if route == "/version":
            self._send_json(200, version_payload())
            self._log_event("request_succeeded", status=200)
            return
        if route == "/datasets/current":
            if not self._authorize_upload():
                return
            try:
                obj = self._upload_plane().get_current_dataset()
                self._send_json(200, obj)
                self._log_event("request_succeeded", status=200, dataset=obj.get("dataset"))
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code)
            return
        if route == "/insights/current":
            if not self._authorize_upload():
                return
            try:
                canonical_person_id = (query.get("canonical_person_id", [""])[0] or "").strip() or None
                window_days = None
                window_days_raw = (query.get("window_days", [""])[0] or "").strip()
                if window_days_raw:
                    try:
                        window_days = int(window_days_raw)
                    except ValueError as exc:
                        raise UploadPlaneError(400, "invalid_window_days", "window_days must be a positive integer") from exc
                    if window_days <= 0:
                        raise UploadPlaneError(400, "invalid_window_days", "window_days must be a positive integer")
                obj = _read_current_dataset_insights(
                    plane=self._upload_plane(),
                    canonical_person_id=canonical_person_id,
                    window_days=window_days,
                )
                self._send_json(200, obj)
                self._log_event(
                    "request_succeeded",
                    status=200,
                    insight_status=obj.get("status"),
                    dataset=obj.get("dataset"),
                    card_count=len(obj.get("cards", [])) if isinstance(obj.get("cards"), list) else 0,
                )
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code)
            except Exception as exc:
                self._send_json(500, {"error": "insights_failed", "detail": str(exc)})
                self._log_event("request_failed", status=500, error="insights_failed")
            return
        if route == "/patients/current":
            if not self._authorize_upload():
                return
            try:
                obj = _read_current_dataset_patients(plane=self._upload_plane())
                self._send_json(200, obj)
                self._log_event(
                    "request_succeeded",
                    status=200,
                    dataset=obj.get("dataset"),
                    patient_count=len(obj.get("patients", [])) if isinstance(obj.get("patients"), list) else 0,
                )
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code)
            except Exception as exc:
                self._send_json(500, {"error": "patient_scope_failed", "detail": str(exc)})
                self._log_event("request_failed", status=500, error="patient_scope_failed")
            return
        if self.path == "/datasets/archives":
            if not self._authorize_upload():
                return
            try:
                archives = self._upload_plane().list_archives()
                self._send_json(200, {"archives": archives})
                self._log_event("request_succeeded", status=200, archive_count=len(archives))
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code)
            return
        session_match = self._session_status_re.match(route)
        if session_match:
            if not self._authorize_upload():
                return
            session_id = session_match.group(1)
            try:
                obj = self._upload_plane().get_session(session_id)
                self._send_json(200, obj)
                self._log_event("request_succeeded", status=200, session_id=session_id)
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code, session_id=session_id)
            return
        self._send_json(404, {"error": "not_found"})
        self._log_event("request_failed", status=404, error="not_found")

    def do_POST(self) -> None:  # noqa: N802
        self._log_event("request_received")
        if self.path in {"/summary", "/qa"}:
            try:
                payload = self._read_json_body()
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code)
                return
            input_path = payload.get("input_path")
            if not isinstance(input_path, str) or not input_path.strip():
                self._send_json(400, {"error": "input_path_required"})
                self._log_event("request_failed", status=400, error="input_path_required")
                return
            work_dir = payload.get("work_dir")
            if not isinstance(work_dir, str) or not work_dir.strip():
                work_dir = "data/backend_slice"
            citation_limit = payload.get("citation_limit")
            if not isinstance(citation_limit, int) or citation_limit <= 0:
                citation_limit = 12
            citation_limit = min(citation_limit, 50)
            try:
                if self.path == "/summary":
                    obj = _run_vertical_slice(input_path=input_path, work_dir=work_dir, citation_limit=citation_limit)
                else:
                    question = payload.get("question")
                    if not isinstance(question, str) or not question.strip():
                        self._send_json(400, {"error": "question_required"})
                        self._log_event("request_failed", status=400, error="question_required")
                        return
                    obj = _run_grounded_qa(
                        input_path=input_path,
                        work_dir=work_dir,
                        question=question,
                        citation_limit=min(citation_limit, 20),
                    )
            except FileNotFoundError as e:
                self._send_json(400, {"error": "input_not_found", "detail": str(e)})
                self._log_event("request_failed", status=400, error="input_not_found")
                return
            except Exception as e:
                self._send_json(500, {"error": "summary_failed", "detail": str(e)})
                self._log_event("request_failed", status=500, error="summary_failed")
                return
            self._send_json(200, obj)
            self._log_event("request_succeeded", status=200)
            return

        if self.path == "/upload-sessions":
            if not self._authorize_upload():
                return
            try:
                payload = self._read_json_body()
                total_size = payload.get("total_size")
                if not isinstance(total_size, int):
                    raise UploadPlaneError(400, "invalid_total_size", "total_size must be an integer")
                sha256 = payload.get("sha256")
                if sha256 is not None and not isinstance(sha256, str):
                    raise UploadPlaneError(400, "invalid_sha256", "sha256 must be a string when provided")
                obj = self._upload_plane().create_session(total_size=total_size, sha256=sha256)
                self._send_json(201, obj)
                self._log_event("upload_session_created", status=201, session_id=obj.get("id"), total_size=total_size)
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code)
            return

        if self.path == "/datasets/archive":
            if not self._authorize_upload():
                return
            try:
                obj = self._upload_plane().archive_current()
                self._send_json(200, obj)
                self._log_event("dataset_archived", status=200, archive=obj.get("archive"))
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code)
            return

        finalize_match = self._session_finalize_re.match(self.path)
        if finalize_match:
            if not self._authorize_upload():
                return
            session_id = finalize_match.group(1)
            try:
                obj = self._upload_plane().finalize_session(session_id)
                self._send_json(200, obj)
                self._log_event(
                    "upload_session_finalized",
                    status=200,
                    session_id=session_id,
                    dataset=obj.get("finalized_dataset"),
                )
            except UploadPlaneError as exc:
                self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
                self._log_event("request_failed", status=exc.status, error=exc.code, session_id=session_id)
            return

        self._send_json(404, {"error": "not_found"})
        self._log_event("request_failed", status=404, error="not_found")

    def do_PUT(self) -> None:  # noqa: N802
        self._log_event("request_received")
        match = self._chunk_put_re.match(self.path)
        if not match:
            self._send_json(404, {"error": "not_found"})
            self._log_event("request_failed", status=404, error="not_found")
            return
        if not self._authorize_upload():
            return

        session_id = match.group(1)
        chunk_index = int(match.group(2))
        try:
            content = self._read_raw_body()
            obj = self._upload_plane().put_chunk(session_id, chunk_index, content)
            self._send_json(
                200,
                {
                    "id": obj.get("id"),
                    "status": obj.get("status"),
                    "received_chunks": obj.get("received_chunks"),
                    "received_bytes": obj.get("received_bytes"),
                    "updated_at": obj.get("updated_at"),
                },
            )
            self._log_event(
                "upload_chunk_stored",
                status=200,
                session_id=session_id,
                chunk_index=chunk_index,
                bytes=len(content),
            )
        except UploadPlaneError as exc:
            self._send_json(exc.status, {"error": exc.code, "detail": exc.detail})
            self._log_event("request_failed", status=exc.status, error=exc.code, session_id=session_id, chunk_index=chunk_index)


def make_server(*, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _Handler)


def serve(*, host: str, port: int) -> None:
    srv = make_server(host=host, port=port)
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="healthdelta-backend")
    p.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    serve(host=str(args.host), port=int(args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
