import json
import tempfile
import unittest
from pathlib import Path

from healthdelta.risk_flags import build_risk_flags


def _write_ndjson(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


class TestRiskFlags(unittest.TestCase):
    def test_build_risk_flags_is_deterministic_with_evidence_and_disclaimer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_ndjson(
                root / "observations.ndjson",
                [
                    {
                        "record_key": "rk-bp",
                        "source_file": "source/clinical/obs_bp.json",
                        "event_time": "2020-01-01T00:00:00Z",
                        "value": 150,
                        "code_coding": [{"system": "http://loinc.org", "code": "8480-6"}],
                    },
                    {
                        "record_key": "rk-hr",
                        "source_file": "source/clinical/obs_hr.json",
                        "event_time": "2020-01-02T00:00:00Z",
                        "value": 110,
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                    },
                ],
            )
            _write_ndjson(
                root / "encounters.ndjson",
                [
                    {
                        "record_key": "rk-e1",
                        "source_file": "source/clinical/e1.json",
                        "event_time": "2020-01-10T00:00:00Z",
                    },
                    {
                        "record_key": "rk-e2",
                        "source_file": "source/clinical/e2.json",
                        "event_time": "2020-01-20T00:00:00Z",
                    },
                ],
            )

            out1 = build_risk_flags(ndjson_dir=str(root))
            out2 = build_risk_flags(ndjson_dir=str(root))
            self.assertEqual(out1, out2)
            self.assertIn("disclaimer", out1)
            self.assertIn("not medical advice", out1["disclaimer"])
            flags = out1["flags"]
            ids = {row["flag_id"] for row in flags}
            self.assertIn("high_blood_pressure", ids)
            self.assertIn("tachycardia_signal", ids)
            self.assertIn("frequent_recent_encounters", ids)
            for row in flags:
                self.assertIn("evidence", row)
                self.assertGreater(len(row["evidence"]), 0)
                for evidence in row["evidence"]:
                    self.assertIn("record_key", evidence)
                    self.assertIn("source_file", evidence)

    def test_build_risk_flags_no_matches_still_has_disclaimer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_ndjson(
                root / "observations.ndjson",
                [
                    {
                        "record_key": "rk-ok",
                        "source_file": "source/clinical/obs_ok.json",
                        "event_time": "2020-01-01T00:00:00Z",
                        "value": 70,
                        "code_coding": [{"system": "http://loinc.org", "code": "8867-4"}],
                    }
                ],
            )
            out = build_risk_flags(ndjson_dir=str(root))
            self.assertEqual(out["flags"], [])
            self.assertIn("not medical advice", out["disclaimer"])


if __name__ == "__main__":
    unittest.main()
