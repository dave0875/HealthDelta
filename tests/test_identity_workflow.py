import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TestIdentityWorkflow(unittest.TestCase):
    def test_identity_review_is_deterministic_and_share_safe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            pii_name = "John Doe"
            pii_dob = "1980-01-02"

            identity_dir = root / "data" / "identity"
            identity_dir.mkdir(parents=True, exist_ok=True)

            # Create person_links.json with out-of-order links; review must sort deterministically.
            _write_json(
                identity_dir / "person_links.json",
                {
                    "schema_version": 1,
                    "run_id": "runX",
                    "links": [
                        {
                            "system_fingerprint": "b" * 64,
                            "source_patient_id": "2" * 64,
                            "person_key": "person-2",
                            "verification_state": "unverified",
                        },
                        {
                            "system_fingerprint": "a" * 64,
                            "source_patient_id": "1" * 64,
                            "person_key": "person-1",
                            "verification_state": "user_confirmed",
                        },
                        {
                            "system_fingerprint": "a" * 64,
                            "source_patient_id": "3" * 64,
                            "person_key": "person-3",
                            "verification_state": "unverified",
                        },
                    ],
                },
            )

            # Other identity artifacts may contain PII-like tokens; review must not read/print them.
            _write_json(identity_dir / "aliases.json", {"aliases": [{"name_raw": pii_name, "dob": pii_dob}]})

            r1 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "identity", "review", "--identity", str(identity_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, msg=f"stdout={r1.stdout}\nstderr={r1.stderr}")

            r2 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "identity", "review", "--identity", str(identity_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, msg=f"stdout={r2.stdout}\nstderr={r2.stderr}")
            self.assertEqual(r2.stdout, r1.stdout)

            # Share-safe: never print synthetic PII-like tokens.
            self.assertNotIn(pii_name, r1.stdout + r1.stderr)
            self.assertNotIn(pii_dob, r1.stdout + r1.stderr)

            lines = [ln for ln in r1.stdout.splitlines() if ln.strip()]
            # Expect exactly 2 unverified links printed.
            self.assertEqual(len(lines), 2)
            # Deterministic ordering: verify printed link_id order is sorted.
            link_ids = [ln.split(" ", 1)[0] for ln in lines]
            self.assertEqual(link_ids, sorted(link_ids))

    def test_identity_confirm_is_deterministic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity_dir = root / "data" / "identity"
            identity_dir.mkdir(parents=True, exist_ok=True)

            # One unverified link to confirm.
            _write_json(
                identity_dir / "person_links.json",
                {
                    "schema_version": 1,
                    "run_id": "runX",
                    "links": [
                        {
                            "system_fingerprint": "a" * 64,
                            "source_patient_id": "1" * 64,
                            "person_key": "person-1",
                            "verification_state": "unverified",
                        }
                    ],
                },
            )

            review = subprocess.run(
                [sys.executable, "-m", "healthdelta", "identity", "review", "--identity", str(identity_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(review.returncode, 0, msg=f"stdout={review.stdout}\nstderr={review.stderr}")
            link_id = review.stdout.strip().split(" ", 1)[0]
            self.assertTrue(link_id)

            confirm1 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "identity", "confirm", "--identity", str(identity_dir), "--link", link_id],
                capture_output=True,
                text=True,
            )
            self.assertEqual(confirm1.returncode, 0, msg=f"stdout={confirm1.stdout}\nstderr={confirm1.stderr}")

            after1 = (identity_dir / "person_links.json").read_bytes()

            confirm2 = subprocess.run(
                [sys.executable, "-m", "healthdelta", "identity", "confirm", "--identity", str(identity_dir), "--link", link_id],
                capture_output=True,
                text=True,
            )
            self.assertEqual(confirm2.returncode, 0, msg=f"stdout={confirm2.stdout}\nstderr={confirm2.stderr}")
            after2 = (identity_dir / "person_links.json").read_bytes()
            self.assertEqual(after2, after1)

            obj = json.loads(after2.decode("utf-8"))
            self.assertEqual(obj["links"][0]["verification_state"], "user_confirmed")


if __name__ == "__main__":
    unittest.main()

