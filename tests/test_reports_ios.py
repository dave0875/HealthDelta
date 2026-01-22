import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401

        return True
    except Exception:
        return False


class TestReportsIOS(unittest.TestCase):
    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_reports_surface_ios_source_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            ios_run = root / "ios_run"
            ndjson_dir = ios_run / "ndjson"
            ndjson_dir.mkdir(parents=True, exist_ok=True)

            _write_text(ios_run / "manifest.json", '{"run_id":"run-1","files":[],"row_counts":{"observations":2}}')
            observations = "\n".join(
                [
                    '{"schema_version":1,"record_key":"rk1","canonical_person_id":"person-1","source":"healthkit","sample_type":"HKQuantityTypeIdentifierStepCount","start_time":"2020-01-01T00:00:00Z","end_time":"2020-01-01T00:00:00Z","value_num":1,"unit":"count"}',
                    '{"schema_version":1,"record_key":"rk2","canonical_person_id":"person-1","source":"healthkit","sample_type":"HKQuantityTypeIdentifierStepCount","start_time":"2020-01-02T00:00:00Z","end_time":"2020-01-02T00:00:00Z","value_num":2,"unit":"count"}',
                ]
            )
            _write_text(ndjson_dir / "observations.ndjson", observations + "\n")

            db_path = root / "out.duckdb"
            build = subprocess.run(
                [sys.executable, "-m", "healthdelta", "duckdb", "build", "--input", str(ios_run), "--db", str(db_path), "--replace"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, msg=f"stdout={build.stdout}\nstderr={build.stderr}")

            out_dir = root / "reports"
            report = subprocess.run(
                [sys.executable, "-m", "healthdelta", "report", "build", "--db", str(db_path), "--out", str(out_dir), "--mode", "share"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(report.returncode, 0, msg=f"stdout={report.stdout}\nstderr={report.stderr}")

            cov = out_dir / "coverage_by_source.csv"
            self.assertTrue(cov.exists())
            rows = list(csv.DictReader(cov.read_text(encoding="utf-8").splitlines()))
            self.assertTrue(any(r["stream"] == "observations" and r["source"] == "ios" and r["rows"] == "2" for r in rows))

