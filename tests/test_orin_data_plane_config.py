from __future__ import annotations

from pathlib import Path
import unittest


class TestOrinDataPlaneConfig(unittest.TestCase):
    def test_compose_binds_host_data_dir(self) -> None:
        text = Path("deploy/orin/compose.yaml").read_text(encoding="utf-8")
        self.assertIn("/opt/healthdelta/data:/app/data", text)

    def test_verify_script_enforces_mount_and_sentinel(self) -> None:
        text = Path("scripts/cd/orin_verify_backend.sh").read_text(encoding="utf-8")
        self.assertIn("data_plane_mount_ok", text)
        self.assertIn("data_plane_sentinel_ok", text)
        self.assertIn("SENTINEL_NAME", text)
        self.assertIn("/app/data", text)
        self.assertIn("restart", text)


if __name__ == "__main__":
    unittest.main()
