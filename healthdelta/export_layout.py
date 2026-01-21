from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExportLayout:
    # Relative to the provided input directory.
    export_root_rel: str
    # Relative to export root.
    export_xml_rel: str
    export_cda_rel: str | None
    clinical_dir_rel: str | None


def _posix_rel(p: Path) -> str:
    if p.is_absolute():
        return p.name
    return p.as_posix()


def resolve_export_layout(input_dir: Path) -> ExportLayout:
    """
    Resolve a canonical unpacked Apple Health export layout deterministically.

    Share-safe constraints:
    - never returns absolute paths
    - uses only repo-relative (posix) paths within the input directory tree
    """
    if not input_dir.is_dir():
        raise ValueError("--input must be an unpacked export directory")

    candidates = [input_dir, input_dir / "apple_health_export"]
    export_root = next((c for c in candidates if (c / "export.xml").exists()), None)
    if export_root is None:
        raise ValueError("export.xml not found in input directory (expected export.xml or apple_health_export/export.xml)")

    export_root_rel = _posix_rel(export_root.relative_to(input_dir)) if export_root != input_dir else "."

    export_xml_rel = "export.xml"
    export_cda_rel = "export_cda.xml" if (export_root / "export_cda.xml").exists() else None

    clinical_dir_rel: str | None = None
    clinical_candidates = [export_root / "clinical-records", export_root / "clinical" / "clinical-records"]
    for c in clinical_candidates:
        if c.exists() and c.is_dir():
            clinical_dir_rel = _posix_rel(c.relative_to(export_root))
            break

    return ExportLayout(
        export_root_rel=export_root_rel,
        export_xml_rel=export_xml_rel,
        export_cda_rel=export_cda_rel,
        clinical_dir_rel=clinical_dir_rel,
    )

