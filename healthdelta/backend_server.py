from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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
