import unittest
from datetime import timezone

from healthdelta.time_utils import UTC


class TestTimeUtils(unittest.TestCase):
    def test_utc_tzinfo_uses_standard_utc(self) -> None:
        self.assertEqual(UTC.utcoffset(None), timezone.utc.utcoffset(None))


if __name__ == "__main__":
    unittest.main()
