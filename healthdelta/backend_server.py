from __future__ import annotations

import argparse
import json
import os
import re
import time
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from healthdelta.deid import deidentify_run
from healthdelta.identity import build_identity
from healthdelta.ingest import ingest_to_staging
from healthdelta.ndjson_export import export_ndjson
from healthdelta.qa import answer_question
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


def _heuristic_insight_cards(*, run_id: str, freshness: str, stats: dict[str, Any]) -> list[dict[str, str]]:
    time_window = "Time window unavailable."
    first_time = stats.get("first_time")
    last_time = stats.get("last_time")
    if isinstance(first_time, datetime) and isinstance(last_time, datetime):
        time_window = (
            f"Time window: {first_time.strftime('%Y-%m-%d %H:%M')} UTC to "
            f"{last_time.strftime('%Y-%m-%d %H:%M')} UTC."
        )

    overview_body = _normalize_card_body(
        "\n".join(
            [
                f"Run {run_id} is active on ORIN.",
                f"Dataset size: {_bytes_label(int(stats.get('size_bytes') or 0))}.",
                f"Observation rows: {int(stats.get('observations_count') or 0):,}.",
                time_window,
            ]
        ),
        fallback="ORIN has the latest uploaded dataset ready.",
    )
    activity_body = _normalize_card_body(
        "\n".join(
            [
                f"Rows in latest upload: {int(stats.get('observations_count') or 0):,}.",
                f"Total recorded value_num across uploaded observations: {float(stats.get('total_value_num') or 0.0):,.0f}.",
                f"Distinct calendar days covered: {int(stats.get('active_days') or 0):,}.",
            ]
        ),
        fallback="ORIN has not generated an activity summary yet.",
    )
    return [
        {
            "id": f"{run_id}-orin-overview",
            "title": "ORIN Overview",
            "body": overview_body,
            "disclaimer": "For education only. This is not medical advice.",
            "sourceLabel": "orin/datasets/current",
            "freshnessLabel": freshness,
        },
        {
            "id": f"{run_id}-orin-activity",
            "title": "Activity Snapshot",
            "body": activity_body,
            "disclaimer": "For education only. This is not medical advice.",
            "sourceLabel": "orin/datasets/current",
            "freshnessLabel": freshness,
        },
    ]


def _coverage_caveat_card(*, run_id: str, freshness: str, stats: dict[str, Any]) -> dict[str, str]:
    observations_count = int(stats.get("observations_count") or 0)
    active_days = int(stats.get("active_days") or 0)
    body = _normalize_card_body(
        "\n".join(
            [
                f"This upload covers {observations_count:,} observations across {active_days:,} day(s).",
                "Trend confidence is limited when the active window is this small.",
                "If you expected a fuller picture, compare against an earlier baseline upload instead of treating this delta alone as the whole story.",
            ]
        ),
        fallback="This upload window is too small for strong trend conclusions.",
    )
    return {
        "id": f"{run_id}-orin-coverage-caveat",
        "title": "Coverage Caveat",
        "body": body,
        "disclaimer": "For education only. This is not medical advice.",
        "sourceLabel": "orin/datasets/current",
        "freshnessLabel": freshness,
    }


def _build_ollama_prompt(*, stats: dict[str, Any]) -> str:
    payload = {
        "run_id": stats.get("run_id"),
        "dataset": stats.get("dataset"),
        "observations_count": int(stats.get("observations_count") or 0),
        "size_bytes": int(stats.get("size_bytes") or 0),
        "size_label": _bytes_label(int(stats.get("size_bytes") or 0)),
        "active_days": int(stats.get("active_days") or 0),
        "total_value_num": round(float(stats.get("total_value_num") or 0.0), 2),
        "average_value_num_per_day": round(float(stats.get("average_value_num_per_day") or 0.0), 2),
        "best_day": stats.get("best_day"),
        "latest_day": stats.get("latest_day"),
        "first_time": stats.get("first_time").strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(stats.get("first_time"), datetime)
        else None,
        "last_time": stats.get("last_time").strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(stats.get("last_time"), datetime)
        else None,
        "daily_totals": _daily_totals_rows(stats.get("daily_totals") or {}),
    }
    return "\n".join(
        [
            "Return JSON only. No markdown. No preface. No code fences.",
            "Use only the aggregate facts below.",
            "Do not mention names, identifiers, diagnoses, disease labels, or treatment instructions.",
            "If the sample is sparse, say so plainly.",
            "Return exactly this shape with exactly 2 cards:",
            '{"cards":[{"title":"Interpretation","body":"One or two short sentences."},{"title":"Confidence","body":"One or two short sentences."}]}',
            "Facts:",
            json.dumps(payload, sort_keys=True),
        ]
    )


def _ollama_refined_insight_cards(*, run_id: str, freshness: str, stats: dict[str, Any]) -> list[dict[str, str]] | None:
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
                "prompt": _build_ollama_prompt(stats=stats),
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
            out.append(_coverage_caveat_card(run_id=run_id, freshness=freshness, stats=stats))
        return out
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def _read_current_dataset_insights(*, plane: UploadPlane) -> dict[str, Any]:
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

    observations_count = 0
    total_value_num = 0.0
    unique_days: set[str] = set()
    first_time: datetime | None = None
    last_time: datetime | None = None
    daily_totals: dict[str, float] = {}
    run_id = str(current.get("dataset") or "current")

    with zipfile.ZipFile(export_zip, "r") as archive:
        manifest_name = next((name for name in archive.namelist() if name.endswith("manifest.json")), None)
        observations_name = next(
            (name for name in archive.namelist() if name.endswith("observations.ndjson")),
            None,
        )
        if manifest_name is None or observations_name is None:
            raise ValueError("uploaded dataset is missing manifest.json or ndjson/observations.ndjson")

        manifest_obj = json.loads(archive.read(manifest_name).decode("utf-8"))
        if isinstance(manifest_obj, dict) and isinstance(manifest_obj.get("run_id"), str) and manifest_obj.get("run_id"):
            run_id = manifest_obj["run_id"]

        with archive.open(observations_name, "r") as handle:
            for raw_line in handle:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue
                observations_count += 1
                when = _parse_iso_utc(row.get("start_time")) or _parse_iso_utc(row.get("event_time")) or _parse_iso_utc(row.get("end_time"))
                if when is not None:
                    day_key = when.strftime("%Y-%m-%d")
                    unique_days.add(day_key)
                    first_time = when if first_time is None or when < first_time else first_time
                    last_time = when if last_time is None or when > last_time else last_time
                value_num = row.get("value_num")
                if isinstance(value_num, (int, float)):
                    total_value_num += float(value_num)
                    if when is not None:
                        daily_totals[day_key] = daily_totals.get(day_key, 0.0) + float(value_num)

    size_bytes = int(current.get("size_bytes") or 0)
    updated_at = str(current.get("updated_at") or datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    freshness = f"Updated {updated_at}"
    best_day = None
    if daily_totals:
        best_day_key, best_day_total = max(daily_totals.items(), key=lambda kv: (kv[1], kv[0]))
        best_day = {"day": best_day_key, "total_value_num": round(float(best_day_total), 2)}
    latest_day = None
    if daily_totals:
        latest_day_key = sorted(daily_totals.keys())[-1]
        latest_day = {"day": latest_day_key, "total_value_num": round(float(daily_totals[latest_day_key]), 2)}
    stats = {
        "run_id": run_id,
        "dataset": current.get("dataset"),
        "size_bytes": size_bytes,
        "observations_count": observations_count,
        "total_value_num": total_value_num,
        "active_days": len(unique_days),
        "average_value_num_per_day": (total_value_num / len(unique_days)) if unique_days else 0.0,
        "first_time": first_time,
        "last_time": last_time,
        "daily_totals": daily_totals,
        "best_day": best_day,
        "latest_day": latest_day,
    }
    cards = _ollama_refined_insight_cards(run_id=run_id, freshness=freshness, stats=stats)
    if cards is None:
        cards = _heuristic_insight_cards(run_id=run_id, freshness=freshness, stats=stats)

    return {
        "status": "ok",
        "dataset": current.get("dataset"),
        "cards": cards,
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
        if self.path == "/healthz":
            self._send_json(200, healthz_payload())
            self._log_event("request_succeeded", status=200)
            return
        if self.path == "/version":
            self._send_json(200, version_payload())
            self._log_event("request_succeeded", status=200)
            return
        if self.path == "/datasets/current":
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
        if self.path == "/insights/current":
            if not self._authorize_upload():
                return
            try:
                obj = _read_current_dataset_insights(plane=self._upload_plane())
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
        session_match = self._session_status_re.match(self.path)
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
