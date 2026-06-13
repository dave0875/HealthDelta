from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def timestamp_slug(now: datetime | None = None) -> str:
    stamp = now or utc_now()
    return stamp.strftime("%Y%m%dT%H%M%SZ")


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def remote_fingerprint(remote: dict[str, Any]) -> dict[str, Any]:
    hashes = remote.get("Hashes")
    sha1 = hashes.get("sha1") if isinstance(hashes, dict) else None
    return {
        "id": remote.get("ID"),
        "name": remote.get("Name"),
        "path": remote.get("Path"),
        "size": remote.get("Size"),
        "mod_time": remote.get("ModTime"),
        "sha1": sha1,
    }


def needs_refresh(remote: dict[str, Any], state: dict[str, Any]) -> bool:
    current = remote_fingerprint(remote)
    previous = state.get("last_remote")
    return current != previous


def quote_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run_cmd(cmd: list[str], *, cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {quote_cmd(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc.stdout


def fetch_remote_metadata(source: str) -> dict[str, Any]:
    raw = run_cmd(["rclone", "lsjson", source, "--hash"])
    rows = json.loads(raw)
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"rclone lsjson returned no rows for source {source}")
    row = rows[0]
    if not isinstance(row, dict):
        raise RuntimeError(f"rclone lsjson returned malformed row for source {source}")
    return row


def download_remote_export(source: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run_cmd(["rclone", "copyto", source, str(destination)])


def verify_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"zip integrity failure in {path}: first bad member is {bad_member}")


def extract_export_zip(export_zip: Path, destination: Path, *, excluded_members: list[str]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {PurePosixPath(name).as_posix() for name in excluded_members}
    resolved_root = destination.resolve()
    with zipfile.ZipFile(export_zip, "r") as archive:
        for member in archive.infolist():
            rel = PurePosixPath(member.filename)
            if rel.as_posix() in excluded:
                continue
            target = (destination / Path(rel.as_posix())).resolve()
            if target != resolved_root and resolved_root not in target.parents:
                raise RuntimeError(f"unsafe zip member path: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def run_healthdelta_build(*, python_bin: str, repo_root: Path, input_dir: Path, out_root: Path) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    profile_dir = out_root / "profile"
    run_cmd(
        [python_bin, "-m", "healthdelta", "export", "profile", "--input", str(input_dir), "--out", str(profile_dir)],
        cwd=repo_root,
    )
    run_cmd(
        [python_bin, "-m", "healthdelta", "export", "coverage", "--input", str(input_dir), "--out", str(profile_dir)],
        cwd=repo_root,
    )
    run_cmd(
        [python_bin, "-m", "healthdelta", "run", "all", "--input", str(input_dir), "--out", str(out_root), "--mode", "share"],
        cwd=repo_root,
    )
    last_run = (out_root / "state" / "LAST_RUN").read_text(encoding="utf-8").strip()
    if not last_run:
        raise RuntimeError(f"healthdelta run all did not produce LAST_RUN under {out_root}")
    run_root = out_root / last_run
    run_cmd(
        [python_bin, "-m", "healthdelta", "export", "validate", "--input", str(run_root / "ndjson")],
        cwd=repo_root,
    )
    return run_root


def assemble_mail_dataset_bundle(*, export_zip: Path, run_root: Path, bundle_root: Path, dataset_name: str) -> Path:
    dataset_dir = bundle_root / dataset_name
    analysis_dir = dataset_dir / "analysis"
    (analysis_dir / "duckdb").mkdir(parents=True, exist_ok=True)
    (analysis_dir / "reports").mkdir(parents=True, exist_ok=True)
    (analysis_dir / "note").mkdir(parents=True, exist_ok=True)

    shutil.copy2(export_zip, dataset_dir / "export.zip")
    shutil.copy2(run_root / "duckdb" / "run.duckdb", analysis_dir / "duckdb" / "run.duckdb")
    shutil.copy2(run_root / "reports" / "summary.json", analysis_dir / "reports" / "summary.json")
    shutil.copy2(run_root / "reports" / "summary.md", analysis_dir / "reports" / "summary.md")
    shutil.copy2(run_root / "note" / "doctor_note.md", analysis_dir / "note" / "doctor_note.md")
    return dataset_dir


def build_mail_promotion_script(*, dataset_name: str, mail_data_root: str, verify_base_url: str) -> str:
    datasets_root = f"{mail_data_root.rstrip('/')}/datasets"
    current_link = f"{datasets_root}/current"
    current_txt = f"{datasets_root}/current.txt"
    return f"""set -euo pipefail
dataset_name={shlex.quote(dataset_name)}
datasets_root={shlex.quote(datasets_root)}
current_link={shlex.quote(current_link)}
current_txt={shlex.quote(current_txt)}
if [ -L "$current_link" ]; then
  rollback_dataset="$(readlink "$current_link")"
elif [ -f "$current_txt" ]; then
  rollback_dataset="$(cat "$current_txt")"
else
  rollback_dataset=""
fi
if [ ! -f "$datasets_root/$dataset_name/export.zip" ]; then
  echo "missing export.zip for dataset $dataset_name" >&2
  exit 1
fi
for required in \
  "$datasets_root/$dataset_name/analysis/duckdb/run.duckdb" \
  "$datasets_root/$dataset_name/analysis/reports/summary.json" \
  "$datasets_root/$dataset_name/analysis/reports/summary.md" \
  "$datasets_root/$dataset_name/analysis/note/doctor_note.md"
do
  if [ ! -f "$required" ]; then
    echo "missing required artifact: $required" >&2
    exit 1
  fi
done
rm -f "$current_link" "$current_txt"
ln -s "$dataset_name" "$current_link"
cd /opt/healthdelta
. ./.env
curl -fsS {shlex.quote(verify_base_url)}/healthz
echo
curl -fsS -H "authorization: Bearer $HEALTHDELTA_UPLOAD_TOKEN" {shlex.quote(verify_base_url)}/datasets/current
echo
curl -fsS -H "authorization: Bearer $HEALTHDELTA_UPLOAD_TOKEN" {shlex.quote(verify_base_url)}/patients/current
echo
curl -fsS -H "authorization: Bearer $HEALTHDELTA_UPLOAD_TOKEN" {shlex.quote(verify_base_url)}/insights/current
echo
printf 'rollback_dataset=%s\\n' "$rollback_dataset"
"""


def sync_bundle_to_mail(*, dataset_dir: Path, mail_host: str, mail_data_root: str) -> None:
    remote_path = f"{mail_host}:{mail_data_root.rstrip('/')}/datasets/{dataset_dir.name}/"
    run_cmd(["rsync", "-az", f"{dataset_dir}/", remote_path])


def promote_bundle_on_mail(*, dataset_name: str, mail_host: str, mail_data_root: str, verify_base_url: str) -> str:
    script = build_mail_promotion_script(
        dataset_name=dataset_name,
        mail_data_root=mail_data_root,
        verify_base_url=verify_base_url,
    )
    return run_cmd(["ssh", "-F", "/dev/null", mail_host, script])


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    work_root = Path(args.work_root).resolve()
    repo_root = Path(args.repo_root).resolve()
    state_path = Path(args.state_json).resolve()
    state = load_state(state_path)

    remote = fetch_remote_metadata(args.drive_source)
    if not needs_refresh(remote, state):
        return {
            "status": "no_changes",
            "remote": remote_fingerprint(remote),
            "last_dataset": state.get("last_dataset"),
        }

    fingerprint = remote_fingerprint(remote)
    build_slug = remote.get("ID") or remote.get("Name") or timestamp_slug()
    build_root = work_root / "builds" / build_slug
    download_dir = build_root / "download"
    derived_input_dir = build_root / "derived_input"
    out_root = build_root / "out"
    bundle_root = build_root / "bundle"
    download_zip = download_dir / "export.zip"

    download_remote_export(args.drive_source, download_zip)
    verify_zip(download_zip)
    extract_export_zip(download_zip, derived_input_dir, excluded_members=list(args.exclude_member))
    run_root = run_healthdelta_build(
        python_bin=args.python_bin,
        repo_root=repo_root,
        input_dir=derived_input_dir,
        out_root=out_root,
    )
    dataset_name = f"dataset_{timestamp_slug()}_apple_bootstrap"
    dataset_dir = assemble_mail_dataset_bundle(
        export_zip=download_zip,
        run_root=run_root,
        bundle_root=bundle_root,
        dataset_name=dataset_name,
    )
    sync_bundle_to_mail(dataset_dir=dataset_dir, mail_host=args.mail_host, mail_data_root=args.mail_data_root)
    promotion_output = promote_bundle_on_mail(
        dataset_name=dataset_name,
        mail_host=args.mail_host,
        mail_data_root=args.mail_data_root,
        verify_base_url=args.verify_base_url,
    )

    next_state = {
        "last_remote": fingerprint,
        "last_dataset": dataset_name,
        "last_run_root": str(run_root),
        "updated_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "promotion_output": promotion_output.strip(),
    }
    save_state(state_path, next_state)
    return {
        "status": "refreshed",
        "remote": fingerprint,
        "dataset": dataset_name,
        "run_root": str(run_root),
        "bundle_dir": str(dataset_dir),
        "promotion_output": promotion_output.strip(),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Refresh the mail baseline from a monitored Drive export.zip source.")
    p.add_argument("--drive-source", required=True, help="rclone source for the watched export.zip, e.g. drive:HEALTH/Exports/export.zip")
    p.add_argument("--work-root", required=True, help="Private working directory on GORF.")
    p.add_argument("--repo-root", default=".", help="HealthDelta repository root.")
    p.add_argument("--state-json", required=True, help="State file used to remember the last processed remote export.")
    p.add_argument("--python-bin", default=sys.executable, help="Python interpreter used to run `python -m healthdelta`.")
    p.add_argument("--mail-host", default="mail", help="SSH host for the target mail server.")
    p.add_argument("--mail-data-root", default="/opt/healthdelta/data", help="Data root on mail.")
    p.add_argument("--verify-base-url", default="http://127.0.0.1:8080", help="Base URL used on mail for post-promotion verification.")
    p.add_argument(
        "--exclude-member",
        action="append",
        default=[],
        help="Optional zip member path to exclude from the derived processing tree. May be passed multiple times.",
    )
    p.add_argument("--print-json", action="store_true", help="Print machine-readable summary JSON.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = run_once(args)
    if args.print_json:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        print(f"status={result['status']}")
        for key in ["dataset", "last_dataset", "run_root", "bundle_dir"]:
            value = result.get(key)
            if value:
                print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
