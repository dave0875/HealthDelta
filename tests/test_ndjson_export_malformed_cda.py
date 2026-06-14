from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, obj: object) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_ndjson(path: Path) -> list[dict]:
    import json

    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestNdjsonMalformedCda(unittest.TestCase):
    def test_export_ndjson_repairs_recoverable_cda(self) -> None:
        malformed_cda = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
 <component>
  <section>
   <code code="11450-4" displayName="Problem List"/>
   <title>Problems</title>
  </section>
 </component>
</ClinicalDocument>
<component>
 <section>
  <code code="8716-3" displayName="Vital signs"/>
  <title>Vital Signs</title>
  <entry>
   <observation>
    <effectiveTime value="20200101112233"/>
    <code code="8867-4" displayName="Heart rate"/>
    <value value="72" unit="/min"/>
   </observation>
  </entry>
 </section>
</component>
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_dir = root / "staging" / "run-cda"
            cda_rel = "source/unpacked/export_cda.xml"
            (run_dir / "source" / "unpacked").mkdir(parents=True, exist_ok=True)
            (run_dir / cda_rel).write_text(malformed_cda, encoding="utf-8")
            _write_json(run_dir / "layout.json", {"run_id": "run-cda", "export_cda_xml": cda_rel, "clinical_json": []})

            out_local = root / "ndjson_local"
            from healthdelta.ndjson_export_repaired import export_ndjson

            export_ndjson(input_dir=str(run_dir), out_dir=str(out_local), mode="local")

            observations = _read_ndjson(out_local / "observations.ndjson")
            self.assertTrue(any(r.get("resource_type") == "CDASection" for r in observations))
            self.assertTrue(any(r.get("resource_type") == "CDAObservation" for r in observations))


if __name__ == "__main__":
    unittest.main()
