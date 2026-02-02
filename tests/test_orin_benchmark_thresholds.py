from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestOrinBenchmarkThresholds(unittest.TestCase):
    def _write_json(self, path: Path, obj: dict) -> None:
        path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def test_threshold_check_passes_when_within_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results.json"
            thresholds = root / "thresholds.json"
            self._write_json(
                results,
                {
                    "metrics": {
                        "summary": {"p95_ms": 9000.0, "p50_ms": 5000.0},
                        "qa": {"p95_ms": 10000.0, "p50_ms": 6000.0},
                        "pipeline": {"p95_s": 30.0},
                    }
                },
            )
            self._write_json(
                thresholds,
                {
                    "metrics": {
                        "summary.p95_ms": {"max": 12000.0},
                        "summary.p50_ms": {"max": 6000.0},
                        "qa.p95_ms": {"max": 12000.0},
                        "qa.p50_ms": {"max": 7000.0},
                        "pipeline.p95_s": {"max": 45.0},
                    }
                },
            )
            proc = subprocess.run(
                ["python3", "scripts/cd/check_benchmark_thresholds.py", "--results", str(results), "--thresholds", str(thresholds)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("benchmark threshold check passed", proc.stdout)

    def test_threshold_check_fails_with_explicit_metric_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / "results.json"
            thresholds = root / "thresholds.json"
            self._write_json(
                results,
                {
                    "metrics": {
                        "summary": {"p95_ms": 15000.0},
                        "qa": {"p95_ms": 10000.0},
                        "pipeline": {"p95_s": 30.0},
                    }
                },
            )
            self._write_json(thresholds, {"metrics": {"summary.p95_ms": {"max": 12000.0}}})
            proc = subprocess.run(
                ["python3", "scripts/cd/check_benchmark_thresholds.py", "--results", str(results), "--thresholds", str(thresholds)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("metric=summary.p95_ms", proc.stdout)
            self.assertIn("threshold<=", proc.stdout)
            self.assertIn("observed=", proc.stdout)


if __name__ == "__main__":
    unittest.main()
