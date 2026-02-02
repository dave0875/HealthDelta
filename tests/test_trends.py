import json
import tempfile
import unittest
from pathlib import Path

from healthdelta.trends import build_trend_analysis


def _write_ndjson(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


class TestTrends(unittest.TestCase):
    def test_trend_analysis_reports_direction_and_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_ndjson(
                root / "observations.ndjson",
                [
                    {
                        "event_time": "2020-01-01T00:00:00Z",
                        "value": 70,
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                    },
                    {
                        "event_time": "2020-01-03T00:00:00Z",
                        "value": 72,
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                    },
                    {
                        "event_time": "2020-01-09T00:00:00Z",
                        "value": 90,
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                    },
                    {
                        "event_time": "2020-01-10T00:00:00Z",
                        "value": 95,
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                    },
                ],
            )
            out = build_trend_analysis(ndjson_dir=str(root))
            by_metric = {row["metric"]: row for row in out["trends"]}
            hr = by_metric["heart_rate"]
            self.assertEqual(hr["direction"], "up")
            self.assertIn(hr["confidence"], {"medium", "high"})
            self.assertIsNone(hr["insufficiency_reason"])

    def test_trend_analysis_reports_insufficient_for_sparse_data(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_ndjson(
                root / "observations.ndjson",
                [
                    {
                        "event_time": "2020-01-01T00:00:00Z",
                        "value": 70,
                        "code_coding": [{"system": "http://loinc.org", "code": "8480-6"}],
                    }
                ],
            )
            out = build_trend_analysis(ndjson_dir=str(root))
            for row in out["trends"]:
                self.assertEqual(row["direction"], "insufficient")
                self.assertEqual(row["confidence"], "insufficient")
                self.assertEqual(row["insufficiency_reason"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
