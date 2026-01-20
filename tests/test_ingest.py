import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Record type="HKQuantityTypeIdentifierStepCount" value="1" />
  <Record type="HKQuantityTypeIdentifierStepCount" value="2" />
</HealthData>
"""

CLINICAL_JSON = """{"resourceType":"Bundle","type":"collection"}"""


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_ingest(input_path: Path, staging_root: Path) -> Path:
    result = subprocess.run(
        [sys.executable, "-m", "healthdelta", "ingest", "--input", str(input_path), "--out", str(staging_root)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"ingest failed: rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}")
    run_dirs = [p for p in staging_root.iterdir() if p.is_dir()]
    if len(run_dirs) != 1:
        raise AssertionError(f"Expected exactly one run dir in {staging_root}, found {run_dirs}")
    return run_dirs[0]


def _make_unpacked_export(root: Path) -> Path:
    export_dir = root / "export_dir"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "export.xml").write_text(EXPORT_XML, encoding="utf-8")
    clinical_dir = export_dir / "clinical_records"
    clinical_dir.mkdir(parents=True, exist_ok=True)
    (clinical_dir / "record.json").write_text(CLINICAL_JSON, encoding="utf-8")
    return export_dir


def _make_export_zip(root: Path, unpacked_dir: Path) -> Path:
    zip_path = root / "export.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("apple_health_export/export.xml", (unpacked_dir / "export.xml").read_text(encoding="utf-8"))
        zf.writestr(
            "apple_health_export/clinical_records/record.json",
            (unpacked_dir / "clinical_records" / "record.json").read_text(encoding="utf-8"),
        )
    return zip_path


class TestIngest(unittest.TestCase):
    def test_zip_vs_unpacked_path_handling(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_dir = _make_unpacked_export(root)

            staging_root_dir = root / "staging_dir"
            run_dir = _run_ingest(export_dir, staging_root_dir)
            manifest = _read_json(run_dir / "manifest.json")
            layout = _read_json(run_dir / "layout.json")

            self.assertEqual(manifest["counts"]["xml_record_count_estimate"], 2)
            self.assertEqual(manifest["counts"]["clinical_json_file_count"], 1)
            self.assertTrue((run_dir / layout["export_xml"]).exists())
            self.assertEqual(len(layout["clinical_json"]), 1)
            self.assertTrue((run_dir / layout["clinical_json"][0]).exists())

            export_zip = _make_export_zip(root, export_dir)
            staging_root_zip = root / "staging_zip"
            run_zip = _run_ingest(export_zip, staging_root_zip)
            manifest_zip = _read_json(run_zip / "manifest.json")
            layout_zip = _read_json(run_zip / "layout.json")

            self.assertEqual(manifest_zip["counts"]["xml_record_count_estimate"], 2)
            self.assertEqual(manifest_zip["counts"]["clinical_json_file_count"], 1)
            self.assertTrue((run_zip / layout_zip["export_xml"]).exists())
            self.assertEqual(len(layout_zip["clinical_json"]), 1)
            self.assertTrue((run_zip / layout_zip["clinical_json"][0]).exists())

    def test_manifest_determinism_for_fixed_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2, tempfile.TemporaryDirectory() as staging:
            input_root_1 = Path(td1)
            input_root_2 = Path(td2)
            staging_root_1 = Path(staging) / "a"
            staging_root_2 = Path(staging) / "b"
            staging_root_1.mkdir(parents=True, exist_ok=True)
            staging_root_2.mkdir(parents=True, exist_ok=True)

            export_dir_1 = _make_unpacked_export(input_root_1)
            export_dir_2 = _make_unpacked_export(input_root_2)

            run_1 = _run_ingest(export_dir_1, staging_root_1)
            run_2 = _run_ingest(export_dir_2, staging_root_2)

            manifest_1 = _read_json(run_1 / "manifest.json")
            manifest_2 = _read_json(run_2 / "manifest.json")

            self.assertEqual(manifest_1["run_id"], manifest_2["run_id"])

            manifest_1.pop("timestamps", None)
            manifest_2.pop("timestamps", None)
            self.assertEqual(manifest_1, manifest_2)


if __name__ == "__main__":
    unittest.main()
