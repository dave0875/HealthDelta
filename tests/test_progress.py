import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


class _NonTTY(io.StringIO):
    def isatty(self) -> bool:  # pragma: no cover
        return False


def _write_minimal_export_xml(path: Path, record_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        "<HealthData>\n",
    ]
    for i in range(record_count):
        rows.append(
            f'<Record type="HKQuantityTypeIdentifierStepCount" startDate="2020-01-01 00:00:00 -0500" endDate="2020-01-01 00:00:00 -0500" value="{i}" unit="count"/>\n'
        )
    rows.append("</HealthData>\n")
    path.write_text("".join(rows), encoding="utf-8")


class TestProgressOutput(unittest.TestCase):
    def test_progress_outputs_lines_in_non_tty_mode(self) -> None:
        from healthdelta.cli import main

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            run_dir = td_p / "run"
            export_xml = run_dir / "source" / "unpacked" / "export.xml"
            _write_minimal_export_xml(export_xml, record_count=2500)
            (run_dir / "layout.json").write_text(
                json.dumps({"run_id": "run-1", "export_xml": "source/unpacked/export.xml", "clinical_json": []}, indent=2) + "\n",
                encoding="utf-8",
            )

            out_dir = td_p / "out"
            stderr = _NonTTY()
            with redirect_stderr(stderr):
                rc = main(
                    [
                        "--progress",
                        "always",
                        "--log-progress-every",
                        "0",
                        "export",
                        "ndjson",
                        "--input",
                        str(run_dir),
                        "--out",
                        str(out_dir),
                        "--mode",
                        "local",
                    ]
                )

            self.assertEqual(rc, 0)
            text = stderr.getvalue()
            self.assertIn("progress task=", text)
            self.assertIn("phase start name=export: parse HealthKit", text)

    def test_progress_never_suppresses_progress_lines_but_prints_summary(self) -> None:
        from healthdelta.cli import main

        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            run_dir = td_p / "run"
            export_xml = run_dir / "source" / "unpacked" / "export.xml"
            _write_minimal_export_xml(export_xml, record_count=10)
            (run_dir / "layout.json").write_text(
                json.dumps({"run_id": "run-1", "export_xml": "source/unpacked/export.xml", "clinical_json": []}, indent=2) + "\n",
                encoding="utf-8",
            )

            out_dir = td_p / "out"
            stderr = _NonTTY()
            with redirect_stderr(stderr):
                rc = main(
                    [
                        "--progress",
                        "never",
                        "export",
                        "ndjson",
                        "--input",
                        str(run_dir),
                        "--out",
                        str(out_dir),
                        "--mode",
                        "local",
                    ]
                )

            self.assertEqual(rc, 0)
            text = stderr.getvalue()
            self.assertNotIn("progress task=", text)
            self.assertNotIn("phase start name=", text)
            self.assertIn("phase summary name=export:", text)


class TestProgressImportCost(unittest.TestCase):
    def test_progress_module_does_not_import_rich(self) -> None:
        import importlib
        import sys

        sys.modules.pop("healthdelta.progress", None)
        sys.modules.pop("rich", None)

        importlib.import_module("healthdelta.progress")
        self.assertNotIn("rich", sys.modules)


if __name__ == "__main__":
    unittest.main()
