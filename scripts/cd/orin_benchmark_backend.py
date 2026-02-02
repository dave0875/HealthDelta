#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any
from urllib.request import Request, urlopen


def _percentile(values: list[float], p: float) -> float:
    if not values:
        raise ValueError("cannot compute percentile of empty set")
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _post_json(base_url: str, path: str, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    req = Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urlopen(req) as resp:
        data = resp.read().decode("utf-8")
        status = resp.status
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    if status != 200:
        raise RuntimeError(f"{path} returned unexpected status: {status}")
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise RuntimeError(f"{path} payload was not a JSON object")
    return obj, elapsed_ms


def _validate_summary_shape(payload: dict[str, Any]) -> None:
    if not isinstance(payload.get("summary"), str):
        raise RuntimeError("summary endpoint missing string 'summary'")
    if not isinstance(payload.get("citations"), list) or not payload["citations"]:
        raise RuntimeError("summary endpoint missing non-empty 'citations'")
    if not isinstance(payload.get("risk_flags"), dict):
        raise RuntimeError("summary endpoint missing 'risk_flags'")


def _validate_qa_shape(payload: dict[str, Any]) -> None:
    qa = payload.get("qa")
    if not isinstance(qa, dict):
        raise RuntimeError("qa endpoint missing 'qa' object")
    if not isinstance(qa.get("citations"), list) or not qa["citations"]:
        raise RuntimeError("qa endpoint missing non-empty citations")
    disclaimer = qa.get("disclaimer")
    if not isinstance(disclaimer, str) or "not medical advice" not in disclaimer.lower():
        raise RuntimeError("qa endpoint missing required disclaimer")


def _stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "count": float(len(ordered)),
        "min": ordered[0],
        "max": ordered[-1],
        "p50": float(median(ordered)),
        "p95": float(_percentile(ordered, 0.95)),
    }


def _run_pipeline_once(input_path: str, out_dir: Path) -> float:
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "healthdelta.cli",
            "pipeline",
            "run",
            "--input",
            input_path,
            "--out",
            str(out_dir),
            "--mode",
            "share",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed_s = time.perf_counter() - start
    if proc.returncode != 0:
        raise RuntimeError(
            "pipeline run failed: " + (proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}")
        )
    return elapsed_s


def _write_markdown(path: Path, data: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# ORIN Backend Benchmark Report")
    lines.append("")
    lines.append(f"- timestamp_utc: `{data['timestamp_utc']}`")
    lines.append(f"- base_url: `{data['base_url']}`")
    lines.append(f"- summary_input_path: `{data['summary_input_path']}`")
    lines.append(f"- pipeline_input_path: `{data['pipeline_input_path']}`")
    lines.append("")
    lines.append("## Endpoint latency (ms)")
    for endpoint in ("summary", "qa"):
        s = data["metrics"][endpoint]
        lines.append(
            f"- {endpoint}: p50={s['p50_ms']:.2f}, p95={s['p95_ms']:.2f}, min={s['min_ms']:.2f}, max={s['max_ms']:.2f}, n={s['count']}"
        )
    lines.append("")
    lines.append("## Pipeline runtime (s)")
    ps = data["metrics"]["pipeline"]
    lines.append(
        f"- pipeline run: p50={ps['p50_s']:.2f}, p95={ps['p95_s']:.2f}, min={ps['min_s']:.2f}, max={ps['max_s']:.2f}, n={ps['count']}"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run ORIN backend benchmark and emit deterministic artifacts.")
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    p.add_argument("--summary-input-path", default="/app/deploy/fixtures/profile_export")
    p.add_argument("--pipeline-input-path", default="tests/fixtures/profile_export")
    p.add_argument("--iterations", type=int, default=5)
    p.add_argument("--pipeline-iterations", type=int, default=3)
    p.add_argument("--pipeline-out", default="artifacts/orin-benchmark/pipeline_runs")
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    return p.parse_args()


def main() -> int:
    args = _args()
    if args.iterations < 1 or args.pipeline_iterations < 1:
        raise SystemExit("iterations and pipeline-iterations must be >= 1")

    summary_latencies: list[float] = []
    qa_latencies: list[float] = []
    pipeline_times: list[float] = []

    for _ in range(args.iterations):
        summary_payload = {"input_path": args.summary_input_path, "citation_limit": 5}
        summary_obj, summary_ms = _post_json(args.base_url, "/summary", summary_payload)
        _validate_summary_shape(summary_obj)
        summary_latencies.append(summary_ms)

        qa_payload = {
            "input_path": args.summary_input_path,
            "question": "what observations exist?",
            "citation_limit": 5,
        }
        qa_obj, qa_ms = _post_json(args.base_url, "/qa", qa_payload)
        _validate_qa_shape(qa_obj)
        qa_latencies.append(qa_ms)

    pipeline_root = Path(args.pipeline_out)
    for i in range(args.pipeline_iterations):
        elapsed = _run_pipeline_once(args.pipeline_input_path, pipeline_root / f"run_{i + 1}")
        pipeline_times.append(elapsed)

    summary_stats = _stats(summary_latencies)
    qa_stats = _stats(qa_latencies)
    pipeline_stats = _stats(pipeline_times)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = {
        "timestamp_utc": now,
        "base_url": args.base_url,
        "summary_input_path": args.summary_input_path,
        "pipeline_input_path": args.pipeline_input_path,
        "metrics": {
            "summary": {
                "count": int(summary_stats["count"]),
                "min_ms": summary_stats["min"],
                "max_ms": summary_stats["max"],
                "p50_ms": summary_stats["p50"],
                "p95_ms": summary_stats["p95"],
            },
            "qa": {
                "count": int(qa_stats["count"]),
                "min_ms": qa_stats["min"],
                "max_ms": qa_stats["max"],
                "p50_ms": qa_stats["p50"],
                "p95_ms": qa_stats["p95"],
            },
            "pipeline": {
                "count": int(pipeline_stats["count"]),
                "min_s": pipeline_stats["min"],
                "max_s": pipeline_stats["max"],
                "p50_s": pipeline_stats["p50"],
                "p95_s": pipeline_stats["p95"],
            },
        },
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _write_markdown(Path(args.out_md), out)
    print(f"wrote benchmark results: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
