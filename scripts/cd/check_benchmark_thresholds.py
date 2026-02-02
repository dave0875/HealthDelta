#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _extract_metric(results: dict[str, Any], key: str) -> float:
    root: Any = results
    for part in key.split("."):
        if not isinstance(root, dict) or part not in root:
            raise KeyError(key)
        root = root[part]
    if not isinstance(root, (int, float)):
        raise TypeError(f"{key} is not numeric")
    return float(root)


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate ORIN benchmark results against thresholds.")
    p.add_argument("--results", required=True, help="Path to benchmark results JSON")
    p.add_argument("--thresholds", required=True, help="Path to threshold JSON")
    return p.parse_args()


def main() -> int:
    args = _args()
    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    metrics = thresholds.get("metrics")
    if not isinstance(metrics, dict):
        raise SystemExit("thresholds missing object: metrics")

    failures: list[str] = []
    for key in sorted(metrics.keys()):
        policy = metrics[key]
        if not isinstance(policy, dict):
            failures.append(f"metric={key} threshold policy is not an object")
            continue
        try:
            observed = _extract_metric(results, f"metrics.{key}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"metric={key} missing in results ({exc})")
            continue

        max_value = policy.get("max")
        min_value = policy.get("min")
        if isinstance(max_value, (int, float)) and observed > float(max_value):
            failures.append(
                f"metric={key} threshold<= {float(max_value):.4f} observed= {observed:.4f} (regression above max)"
            )
        if isinstance(min_value, (int, float)) and observed < float(min_value):
            failures.append(
                f"metric={key} threshold>= {float(min_value):.4f} observed= {observed:.4f} (regression below min)"
            )

    if failures:
        print("policy failure: benchmark regression threshold check failed.")
        for line in failures:
            print(f"- {line}")
        print("how to fix: optimize runtime or adjust thresholds in deploy/orin/benchmark_thresholds.json with issue-backed rationale.")
        return 1

    print("benchmark threshold check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
