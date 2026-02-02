import json
import tempfile
import unittest
from pathlib import Path

from healthdelta.qa import answer_question


def _write_ndjson(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


class TestQA(unittest.TestCase):
    def test_answer_question_returns_citations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_ndjson(
                root / "observations.ndjson",
                [
                    {
                        "record_key": "rk1",
                        "source_file": "source/clinical/obs_heart_rate.json",
                        "event_time": "2020-01-01T00:00:00Z",
                        "resource_type": "Observation",
                        "hk_type": "HKQuantityTypeIdentifierHeartRate",
                    }
                ],
            )
            out = answer_question(ndjson_dir=str(root), question="heart rate observation")
            self.assertFalse(out["abstained"])
            self.assertGreater(len(out["citations"]), 0)
            self.assertIn("not medical advice", out["disclaimer"])

    def test_answer_question_abstains_when_no_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_ndjson(
                root / "documents.ndjson",
                [
                    {
                        "record_key": "rk1",
                        "source_file": "source/clinical/doc_1.json",
                        "event_time": "2020-01-01T00:00:00Z",
                        "resource_type": "DocumentReference",
                    }
                ],
            )
            out = answer_question(ndjson_dir=str(root), question="glucose trend")
            self.assertTrue(out["abstained"])
            self.assertEqual(out["citations"], [])
            self.assertIn("Insufficient evidence", out["answer"])


if __name__ == "__main__":
    unittest.main()
