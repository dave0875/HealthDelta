#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

from healthdelta.version import ios_build_number_from_env, ios_marketing_version_from_ref


def main() -> int:
    ref = os.getenv("GITHUB_REF") or ""
    marketing = ios_marketing_version_from_ref(ref)
    build = ios_build_number_from_env()

    if "--json" in sys.argv:
        print(json.dumps({"MARKETING_VERSION": marketing, "CURRENT_PROJECT_VERSION": build}, sort_keys=True))
        return 0

    if marketing is not None:
        print(f"MARKETING_VERSION={marketing}")
    if build is not None:
        print(f"CURRENT_PROJECT_VERSION={build}")

    if marketing is None:
        print("ERROR: expected GITHUB_REF to be a tag like refs/tags/vX.Y.Z", file=sys.stderr)
        return 2
    if build is None:
        print("ERROR: expected GITHUB_RUN_NUMBER to be set (digits only)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

