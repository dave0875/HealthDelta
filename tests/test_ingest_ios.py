import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestIngestIOS(unittest.TestCase):
    def _make_ios_export_dir(self, root: Path) -> Path:
        run_dir = root / "ios_run"
        ndjson_dir = run_dir / "ndjson"
        ndjson_dir.mkdir(parents=True, exist_ok=True)

        # Tiny synthetic NDJSON (2 rows).
        (ndjson_dir / "observations.ndjson").write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")

        # iOS-side manifest (content doesn't matter for staging determinism, but required for validation).
        (run_dir / "manifest.json").write_text('{"run_id":"run_1","files":[],"row_counts":{"observations":2}}', encoding="utf-8")
        return run_dir

    def test_ingest_ios_writes_deterministic_staging_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            root1 = Path(td1)
            root2 = Path(td2)

            ios_dir_1 = self._make_ios_export_dir(root1)
            ios_dir_2 = self._make_ios_export_dir(root2)

            staging_root_1 = root1 / "staging"
            staging_root_2 = root2 / "staging"
            staging_root_1.mkdir(parents=True, exist_ok=True)
            staging_root_2.mkdir(parents=True, exist_ok=True)

            def run_ingest(input_dir: Path, out_root: Path) -> Path:
                result = subprocess.run(
                    [sys.executable, "-m", "healthdelta", "ingest", "ios", "--input", str(input_dir), "--out", str(out_root)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise AssertionError(f"ingest ios failed: rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}")
                run_dirs = [p for p in out_root.iterdir() if p.is_dir()]
                if len(run_dirs) != 1:
                    raise AssertionError(f"Expected exactly one run dir in {out_root}, found {run_dirs}")
                return run_dirs[0]

            run1 = run_ingest(ios_dir_1, staging_root_1)
            run2 = run_ingest(ios_dir_2, staging_root_2)

            manifest1 = _read_json(run1 / "manifest.json")
            manifest2 = _read_json(run2 / "manifest.json")
            self.assertEqual(manifest1, manifest2)

            self.assertTrue((run1 / "ndjson" / "observations.ndjson").exists())
            self.assertTrue((run1 / "source" / "ios" / "manifest.json").exists())

