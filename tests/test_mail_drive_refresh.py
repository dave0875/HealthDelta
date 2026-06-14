from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "mail_drive_refresh.py"
    spec = importlib.util.spec_from_file_location("mail_drive_refresh", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestMailDriveRefresh(unittest.TestCase):
    def test_extract_export_zip_excludes_nested_member_by_basename(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_zip = root / "export.zip"
            with zipfile.ZipFile(export_zip, "w") as archive:
                archive.writestr("apple_health_export/export.xml", "<root />")
                archive.writestr("apple_health_export/export_cda.xml", "<bad />")

            derived = root / "derived"
            mod.extract_export_zip(export_zip, derived, excluded_members=["export_cda.xml"])

            self.assertTrue((derived / "apple_health_export" / "export.xml").exists())
            self.assertFalse((derived / "apple_health_export" / "export_cda.xml").exists())

    def test_select_latest_zip_prefers_newest_modtime(self) -> None:
        mod = _load_module()
        rows = [
            {"Name": "export.zip", "Path": "export.zip", "ModTime": "2026-05-30T21:09:49.539Z", "Size": 1, "ID": "old"},
            {"Name": "notes.txt", "Path": "notes.txt", "ModTime": "2026-06-13T21:16:21.178Z", "Size": 2, "ID": "ignore"},
            {"Name": "export 3.zip", "Path": "export 3.zip", "ModTime": "2026-06-13T21:16:21.178Z", "Size": 3, "ID": "new"},
        ]
        chosen = mod.select_latest_zip(rows)
        self.assertEqual(chosen["Name"], "export 3.zip")
        self.assertEqual(chosen["ID"], "new")

    def test_needs_refresh_uses_remote_identity_and_size(self) -> None:
        mod = _load_module()
        remote = {
            "ID": "file-123",
            "Name": "export.zip",
            "Size": 42,
            "ModTime": "2026-06-13T00:00:00Z",
            "Hashes": {"sha1": "abc"},
        }
        self.assertTrue(mod.needs_refresh(remote, {}))
        self.assertFalse(mod.needs_refresh(remote, {"last_remote": mod.remote_fingerprint(remote)}))
        changed = dict(remote)
        changed["Size"] = 43
        self.assertTrue(mod.needs_refresh(changed, {"last_remote": mod.remote_fingerprint(remote)}))

    def test_assemble_mail_dataset_bundle_copies_required_artifacts(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_zip = root / "export.zip"
            export_zip.write_bytes(b"zip-bytes")

            run_root = root / "run"
            (run_root / "duckdb").mkdir(parents=True)
            (run_root / "reports").mkdir(parents=True)
            (run_root / "note").mkdir(parents=True)
            (run_root / "duckdb" / "run.duckdb").write_bytes(b"duckdb")
            (run_root / "reports" / "summary.json").write_text("{}", encoding="utf-8")
            (run_root / "reports" / "summary.md").write_text("# summary\n", encoding="utf-8")
            (run_root / "note" / "doctor_note.md").write_text("# note\n", encoding="utf-8")

            bundle_root = root / "bundle"
            dataset_dir = mod.assemble_mail_dataset_bundle(
                export_zip=export_zip,
                run_root=run_root,
                bundle_root=bundle_root,
                dataset_name="dataset_20260613T000000Z_apple_bootstrap",
            )

            self.assertTrue((dataset_dir / "export.zip").exists())
            self.assertTrue((dataset_dir / "analysis" / "duckdb" / "run.duckdb").exists())
            self.assertTrue((dataset_dir / "analysis" / "reports" / "summary.json").exists())
            self.assertTrue((dataset_dir / "analysis" / "reports" / "summary.md").exists())
            self.assertTrue((dataset_dir / "analysis" / "note" / "doctor_note.md").exists())

    def test_build_mail_promotion_script_includes_verify_and_swap(self) -> None:
        mod = _load_module()
        script = mod.build_mail_promotion_script(
            dataset_name="dataset_20260613T000000Z_apple_bootstrap",
            mail_data_root="/opt/healthdelta/data",
            verify_base_url="http://127.0.0.1:8080",
        )
        self.assertIn("rollback_dataset", script)
        self.assertIn("/opt/healthdelta/data/datasets/current", script)
        self.assertIn("curl -fsS http://127.0.0.1:8080/healthz", script)
        self.assertIn("curl -fsS -H \"authorization: Bearer $HEALTHDELTA_UPLOAD_TOKEN\" http://127.0.0.1:8080/datasets/current", script)
        self.assertIn("ln -s \"$dataset_name\" \"$current_link\"", script)
        self.assertIn("/patients/current", script)
        self.assertIn("/insights/current", script)

    def test_state_round_trip_is_json_stable(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            state = {
                "last_remote": {"id": "file-1", "size": 10},
                "last_dataset": "dataset_20260613T000000Z_apple_bootstrap",
            }
            mod.save_state(path, state)
            loaded = mod.load_state(path)
            self.assertEqual(loaded, state)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(json.loads(text), state)


if __name__ == "__main__":
    unittest.main()
