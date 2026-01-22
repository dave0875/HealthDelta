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


class TestDuckdbLoaderIOS(unittest.TestCase):
    @unittest.skipUnless(_duckdb_available(), "duckdb not installed in this environment")
    def test_duckdb_build_accepts_ios_export_dir_subset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ios_run = root / "ios_run"
            ndjson_dir = ios_run / "ndjson"
            ndjson_dir.mkdir(parents=True, exist_ok=True)

            # iOS run manifest (run_id applied to all loaded rows).
            _write_text(ios_run / "manifest.json", '{"run_id":"run-1","files":[],"row_counts":{"observations":2}}')

            # iOS observations NDJSON (subset schema).
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
            self.assertTrue(db_path.exists())

            q = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM observations ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q.returncode, 0, msg=f"stdout={q.stdout}\nstderr={q.stderr}")
            rows = list(csv.DictReader(q.stdout.splitlines()))
            self.assertEqual(rows[0]["n"], "2")

            # Append-safe rerun (no duplicates) without --replace.
            build2 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "duckdb", "build", "--input", str(ios_run), "--db", str(db_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build2.returncode, 0, msg=f"stdout={build2.stdout}\nstderr={build2.stderr}")

            q2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "duckdb",
                    "query",
                    "--db",
                    str(db_path),
                    "--sql",
                    "SELECT COUNT(*) AS n FROM observations ORDER BY n;",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(q2.returncode, 0, msg=f"stdout={q2.stdout}\nstderr={q2.stderr}")
            rows2 = list(csv.DictReader(q2.stdout.splitlines()))
            self.assertEqual(rows2[0]["n"], "2")

