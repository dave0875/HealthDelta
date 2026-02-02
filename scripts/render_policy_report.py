#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


POLICY_KEYS = [
    "POLICY_ISSUE_FOOTER",
    "POLICY_PR_ISSUE",
    "POLICY_AUDIT_ARTIFACTS",
    "POLICY_PROMPT_IMMUTABILITY",
    "POLICY_WORKTREE",
]


def _status(raw: str) -> str:
    x = (raw or "").strip().lower()
    if x in {"success", "failure", "cancelled", "skipped"}:
        return x
    if not x:
        return "unknown"
    return "unknown"


def build_report(env: dict[str, str]) -> dict:
    rows = []
    any_failure = False
    for key in POLICY_KEYS:
        value = _status(env.get(key, ""))
        rows.append({"check": key.lower(), "outcome": value})
        if value == "failure":
            any_failure = True
    return {
        "policy_checks": rows,
        "any_failure": any_failure,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render machine-readable policy outcome report.")
    p.add_argument("--out", required=True, help="Output JSON report path")
    args = p.parse_args(argv)
    report = build_report(dict(os.environ))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
