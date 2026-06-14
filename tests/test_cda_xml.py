from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


RECOVERABLE_CDA = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
 <component>
  <section>
   <code code="11450-4" displayName="Problem List"/>
   <title>Problems</title>
   <entry>
    <observation>
     <code code="75326-9" displayName="Problem"/>
     <value value="1"/>
    </observation>
   </entry>
  </section>
 </component>
</ClinicalDocument>
<component>
 <section>
  <code code="8716-3" displayName="Vital Signs"/>
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


TRUNCATED_CDA = """<?xml version="1.0"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
 <component>
  <section>
   <title>Vital Signs</title>
   <entry>
    <observation>
     <code code="8867-4" displayName="Heart rate"/>
"""


class TestCdaXml(unittest.TestCase):
    def test_repair_recoverable_cda_creates_well_formed_copy(self) -> None:
        from healthdelta.cda_xml import repair_cda_xml, parse_cda_xml

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "export_cda.xml"
            dst = root / "repaired.xml"
            src.write_text(RECOVERABLE_CDA, encoding="utf-8")

            summary = repair_cda_xml(src=src, dst=dst)

            self.assertTrue(summary.was_repaired)
            self.assertEqual(summary.premature_root_closes_removed, 1)
            self.assertEqual(summary.final_root_closes_appended, 1)
            tree = ET.parse(dst)
            self.assertEqual(tree.getroot().tag.split("}")[-1], "ClinicalDocument")

            ctx = parse_cda_xml(dst)
            self.assertEqual(len(ctx.sections), 2)
            self.assertEqual(len(ctx.observations), 2)

    def test_repair_truncated_cda_raises_resubmission_error(self) -> None:
        from healthdelta.cda_xml import CdaRepairError, repair_cda_xml

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "export_cda.xml"
            dst = root / "repaired.xml"
            src.write_text(TRUNCATED_CDA, encoding="utf-8")

            with self.assertRaises(CdaRepairError) as cm:
                repair_cda_xml(src=src, dst=dst)

            msg = str(cm.exception)
            self.assertIn("truncated", msg.lower())
            self.assertIn("dave0875@gmail.com", msg)


if __name__ == "__main__":
    unittest.main()
