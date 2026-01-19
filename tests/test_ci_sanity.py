import os
import unittest


class TestCISanity(unittest.TestCase):
    def test_required_bootstrap_files_exist(self) -> None:
        required_paths = [
            "AGENTS.md",
            "README.md",
            "TIME.csv",
            ".codex/README.md",
            "docs/runbook_xcode.md",
            ".github/workflows/ci.yml",
            ".github/workflows/device_smoke.yml",
        ]

        missing = [path for path in required_paths if not os.path.exists(path)]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()

