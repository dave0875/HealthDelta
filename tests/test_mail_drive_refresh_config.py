from __future__ import annotations

from pathlib import Path
import unittest


class TestMailDriveRefreshConfig(unittest.TestCase):
    def test_runbook_references_script_and_drive_source(self) -> None:
        text = Path("docs/runbook_mail_refresh.md").read_text(encoding="utf-8")
        self.assertIn("scripts/mail_drive_refresh.py", text)
        self.assertIn("gdrive:HEALTH/Exports/export.zip", text)
        self.assertIn("HEALTH/Exports/export.zip", text)
        self.assertIn("status=no_changes", text)
        self.assertIn("/datasets/current", text)
        self.assertIn("/patients/current", text)
        self.assertIn("/insights/current", text)

    def test_agents_references_mail_refresh_runbook(self) -> None:
        text = Path("AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/runbook_mail_refresh.md", text)

    def test_systemd_templates_exist(self) -> None:
        service = Path("deploy/gorf/healthdelta-mail-refresh.service").read_text(encoding="utf-8")
        timer = Path("deploy/gorf/healthdelta-mail-refresh.timer").read_text(encoding="utf-8")
        self.assertIn("gdrive:HEALTH/Exports/export.zip", service)
        self.assertIn("scripts/mail_drive_refresh.py", service)
        self.assertIn("OnUnitActiveSec=15m", timer)


if __name__ == "__main__":
    unittest.main()
