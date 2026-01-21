import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestNdjsonValidate(unittest.TestCase):
    def test_validate_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "observations.ndjson",
                '{"canonical_person_id":"p1","source":"healthkit","source_file":"source/export.xml","event_time":"2020-01-01T00:00:00Z","run_id":"r1"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertEqual(r.stdout.strip(), "ok")

    def test_validate_fails_on_missing_required_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "observations.ndjson",
                '{"canonical_person_id":"p1","source":"healthkit","source_file":"source/export.xml","event_time":"2020-01-01T00:00:00Z"}\n',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("missing_required_key", r.stderr)
            self.assertIn("run_id", r.stderr)

    def test_validate_fails_on_banned_token_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "documents.ndjson",
                '{"canonical_person_id":"p1","source":"fhir","source_file":"John Doe export/clinical-records/doc.json","event_time":"2020-01-02T00:00:00Z","run_id":"r1"}\n',
            )

            r = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "healthdelta",
                    "export",
                    "validate",
                    "--input",
                    str(nd),
                    "--banned-token",
                    "John Doe",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("banned_token", r.stderr)

    def test_validate_fails_on_missing_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nd = root / "ndjson"
            nd.mkdir(parents=True, exist_ok=True)

            _write(
                nd / "conditions.ndjson",
                '{"canonical_person_id":"p1","source":"fhir","source_file":"x.json","event_time":"2020-01-01T00:00:00Z","run_id":"r1"}',
            )

            r = subprocess.run(
                [sys.executable, "-m", "healthdelta", "export", "validate", "--input", str(nd)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1, msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("missing_trailing_newline", r.stderr)


if __name__ == "__main__":
    unittest.main()

