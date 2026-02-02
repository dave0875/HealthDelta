from __future__ import annotations

import argparse
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from healthdelta.deid import deidentify_run
from healthdelta.identity import build_identity
from healthdelta.ingest import ingest_to_staging
from healthdelta.ndjson_export import export_ndjson
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


def _run_vertical_slice(*, input_path: str, work_dir: str, citation_limit: int = 12) -> dict[str, Any]:
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

    summary, citations, counts = _build_summary_from_ndjson(ndjson_dir, citation_limit=citation_limit)
    tokens = _load_identity_tokens(identity_dir)
    scan_text = "\n".join([summary, json.dumps(citations, sort_keys=True), "\n".join(log_lines)])
    hits = _find_token_hits(scan_text, tokens)
    if hits:
        raise RuntimeError(f"policy failure: banned PHI tokens detected in output/logs: {', '.join(sorted(hits))}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "run_id": run_id,
        "summary": summary,
        "counts_by_stream": [{"stream": k, "count": counts[k]} for k in sorted(counts.keys())],
        "citations": citations,
        "policy": {"phi_tokens_checked": sorted(tokens), "phi_token_hits": []},
        "artifacts": {
            "run_dir": run_id,
            "slice_log": "slice.log",
            "ndjson_dir": "ndjson",
        },
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _send_json(self, status: int, obj: object) -> None:
        body = (json.dumps(obj, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send_json(200, healthz_payload())
            return
        if self.path == "/version":
            self._send_json(200, version_payload())
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/summary":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid_content_length"})
            return
        raw = self.rfile.read(max(content_length, 0))
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json(400, {"error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "invalid_payload"})
            return
        input_path = payload.get("input_path")
        if not isinstance(input_path, str) or not input_path.strip():
            self._send_json(400, {"error": "input_path_required"})
            return
        work_dir = payload.get("work_dir")
        if not isinstance(work_dir, str) or not work_dir.strip():
            work_dir = "data/backend_slice"
        citation_limit = payload.get("citation_limit")
        if not isinstance(citation_limit, int) or citation_limit <= 0:
            citation_limit = 12
        citation_limit = min(citation_limit, 50)
        try:
            obj = _run_vertical_slice(input_path=input_path, work_dir=work_dir, citation_limit=citation_limit)
        except FileNotFoundError as e:
            self._send_json(400, {"error": "input_not_found", "detail": str(e)})
            return
        except Exception as e:
            self._send_json(500, {"error": "summary_failed", "detail": str(e)})
            return
        self._send_json(200, obj)


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
