import io
import unittest
from contextlib import redirect_stdout


class TestVersionTruth(unittest.TestCase):
    def test_parse_tag_version_accepts_v_prefix(self) -> None:
        from healthdelta.version import parse_version_tag

        self.assertEqual(parse_version_tag("v1.2.3"), "1.2.3")

    def test_parse_tag_version_accepts_refs_tags(self) -> None:
        from healthdelta.version import parse_version_tag

        self.assertEqual(parse_version_tag("refs/tags/v2.3.4"), "2.3.4")

    def test_parse_tag_version_rejects_invalid(self) -> None:
        from healthdelta.version import parse_version_tag

        self.assertIsNone(parse_version_tag("1.2.3"))
        self.assertIsNone(parse_version_tag("v1.2"))
        self.assertIsNone(parse_version_tag("refs/heads/main"))

    def test_healthdelta_version_command_prints_version_line(self) -> None:
        from healthdelta.cli import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["version"])

        self.assertEqual(rc, 0)
        out = buf.getvalue().strip()
        self.assertTrue(out.startswith("healthdelta_version="), out)


if __name__ == "__main__":
    unittest.main()

