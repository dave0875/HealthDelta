from __future__ import annotations

import os
import subprocess
from typing import Any


def parse_version_tag(ref_or_tag: str) -> str | None:
    s = ref_or_tag.strip()
    if s.startswith("refs/tags/"):
        s = s[len("refs/tags/") :]

    if not s.startswith("v"):
        return None

    v = s[1:]
    parts = v.split(".")
    if len(parts) != 3:
        return None
    if any((not p.isdigit()) for p in parts):
        return None
    return v


def _run_git(args: list[str]) -> str | None:
    try:
        out = subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return None
    return out.strip() or None


def get_git_sha() -> str | None:
    for key in ("HEALTHDELTA_GIT_SHA", "GITHUB_SHA"):
        v = os.getenv(key)
        if v:
            return v
    return _run_git(["rev-parse", "HEAD"])


def get_version() -> str:
    env_v = os.getenv("HEALTHDELTA_VERSION")
    if env_v:
        return env_v

    try:
        from healthdelta._version import __version__ as v

        if v and v != "0.0.0+local":
            return v
    except Exception:
        pass

    try:
        from importlib.metadata import version as dist_version

        return dist_version("healthdelta")
    except Exception:
        pass

    tag_v = parse_version_tag(os.getenv("GITHUB_REF", "") or "")
    if tag_v:
        return tag_v

    return "0.0.0+local"


def ios_marketing_version_from_ref(ref: str) -> str | None:
    return parse_version_tag(ref)


def ios_build_number_from_env() -> str | None:
    run_number = os.getenv("GITHUB_RUN_NUMBER")
    if run_number and run_number.isdigit():
        return run_number
    return None


def get_build_info() -> dict[str, Any]:
    return {
        "version": get_version(),
        "git_sha": get_git_sha(),
        "github_ref": os.getenv("GITHUB_REF") or None,
        "github_run_id": os.getenv("GITHUB_RUN_ID") or None,
        "github_run_number": os.getenv("GITHUB_RUN_NUMBER") or None,
    }
