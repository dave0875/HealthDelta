from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


SYNTH_EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Me name="John Doe" />
</HealthData>
"""


class TestDeidMalformedCda(unittest.TestCase):
    def test_deid_repairs_recoverable_cda_without_dom_parse(self) -> None:
        malformed_cda = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <recordTarget>
    <patientRole>
      <patient>
        <name>
          <given>John</given>
          <family>Doe</family>
        </name>
        <birthTime value="19800102"/>
      </patient>
    </patientRole>
  </recordTarget>
</ClinicalDocument>
<component>
  <section>
    <title>Vital Signs</title>
  </section>
</component>
"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity_dir = root / "data" / "identity"
            _write_json(
                identity_dir / "people.json",
                {
                    "people": [
                        {
                            "person_key": "00000000-0000-0000-0000-000000000001",
                            "first_norm": "john",
                            "last_norm": "doe",
                            "created_at": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
            )

            run_dir = root / "data" / "staging" / "run123"
            export_xml_rel = "source/unpacked/export.xml"
            cda_rel = "source/unpacked/export_cda.xml"
            (run_dir / "source" / "unpacked").mkdir(parents=True, exist_ok=True)
            (run_dir / export_xml_rel).write_text(SYNTH_EXPORT_XML, encoding="utf-8")
            (run_dir / cda_rel).write_text(malformed_cda, encoding="utf-8")
            _write_json(run_dir / "layout.json", {"run_id": "run123", "export_xml": export_xml_rel, "clinical_json": []})

            out_dir = root / "data" / "deid" / "run123"
            from healthdelta.deid import deidentify_run

            old_cwd = Path.cwd()
            try:
                os.chdir(root)
                deidentify_run(staging_run_dir=str(run_dir), identity_dir=str(identity_dir), out_dir=str(out_dir))
            finally:
                os.chdir(old_cwd)

            text = (out_dir / cda_rel).read_text(encoding="utf-8")
            self.assertNotIn("John", text)
            self.assertNotIn("Doe", text)
            self.assertIn("19000101", text)


if __name__ == "__main__":
    unittest.main()
