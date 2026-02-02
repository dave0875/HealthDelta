#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from healthdelta.backend_server import make_server


BANNED_PATTERNS = [
    re.compile(r"\bJohn\b", re.IGNORECASE),
    re.compile(r"\bDoe\b", re.IGNORECASE),
    re.compile(r"\b1980-01-02\b"),
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json_post(url: str, payload: dict) -> dict:
    req = Request(
        url,
        data=json.dumps(payload, sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def _validate_summary(summary_obj: dict, errors: list[str]) -> None:
    if not isinstance(summary_obj.get("citations"), list) or not summary_obj.get("citations"):
        errors.append("summary.citations missing or empty")
    risk = summary_obj.get("risk_flags")
    if not isinstance(risk, dict):
        errors.append("summary.risk_flags missing")
    else:
        disclaimer = risk.get("disclaimer")
        if not isinstance(disclaimer, str) or "not medical advice" not in disclaimer.lower():
            errors.append("summary.risk_flags.disclaimer missing or invalid")
    trends = summary_obj.get("trends")
    if not isinstance(trends, dict) or not isinstance(trends.get("trends"), list):
        errors.append("summary.trends missing or invalid")


def _validate_qa(qa_obj: dict, errors: list[str]) -> None:
    qa = qa_obj.get("qa")
    if not isinstance(qa, dict):
        errors.append("qa.qa missing")
        return
    disclaimer = qa.get("disclaimer")
    if not isinstance(disclaimer, str) or "not medical advice" not in disclaimer.lower():
        errors.append("qa.disclaimer missing or invalid")
    citations = qa.get("citations")
    abstained = bool(qa.get("abstained"))
    if not isinstance(citations, list):
        errors.append("qa.citations missing")
    elif not citations and not abstained:
        errors.append("qa.citations empty without abstain")
    if abstained and "insufficient evidence" not in str(qa.get("answer", "")).lower():
        errors.append("qa.abstained without insufficiency message")


def _check_banned(text: str, errors: list[str]) -> None:
    for pat in BANNED_PATTERNS:
        if pat.search(text):
            errors.append(f"banned_pattern_detected:{pat.pattern}")


def run_safety_check(*, input_path: str, work_dir: str) -> dict:
    server = make_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    errors: list[str] = []
    summary_obj: dict = {}
    qa_obj: dict = {}
    try:
        summary_obj = _json_post(
            base_url + "/summary",
            {"input_path": str(Path(input_path).resolve()), "work_dir": str(Path(work_dir).resolve()), "citation_limit": 8},
        )
        qa_obj = _json_post(
            base_url + "/qa",
            {
                "input_path": str(Path(input_path).resolve()),
                "work_dir": str(Path(work_dir).resolve()),
                "question": "what observations exist?",
                "citation_limit": 8,
            },
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    _validate_summary(summary_obj, errors)
    _validate_qa(qa_obj, errors)
    summary_scan = "\n".join(
        [
            str(summary_obj.get("summary", "")),
            json.dumps(summary_obj.get("citations", []), sort_keys=True),
            json.dumps((summary_obj.get("risk_flags") or {}).get("flags", []), sort_keys=True),
            json.dumps((summary_obj.get("trends") or {}).get("trends", []), sort_keys=True),
        ]
    )
    qa_payload = qa_obj.get("qa") if isinstance(qa_obj.get("qa"), dict) else {}
    qa_scan = "\n".join(
        [
            str(qa_payload.get("answer", "")),
            str(qa_payload.get("disclaimer", "")),
            json.dumps(qa_payload.get("citations", []), sort_keys=True),
        ]
    )
    _check_banned(summary_scan, errors)
    _check_banned(qa_scan, errors)

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "summary": summary_obj,
        "qa": qa_obj,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate share-safe endpoint outputs and guardrails.")
    p.add_argument("--input", required=True, help="Synthetic fixture input directory")
    p.add_argument("--work", required=True, help="Working directory for generated artifacts")
    p.add_argument("--out-json", required=True, help="Machine-readable report output path")
    p.add_argument("--out-log", required=True, help="Human log output path")
    args = p.parse_args(argv)

    report = run_safety_check(input_path=args.input, work_dir=args.work)
    _write(Path(args.out_json), json.dumps(report, sort_keys=True, indent=2) + "\n")
    log_lines = [f"ok={str(report['ok']).lower()}"]
    for err in report["errors"]:
        log_lines.append(f"error={err}")
    if report["ok"]:
        log_lines.append("safety checks passed")
    _write(Path(args.out_log), "\n".join(log_lines) + "\n")

    if not report["ok"]:
        print("\n".join(log_lines))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
