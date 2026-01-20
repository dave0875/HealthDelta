import argparse

from healthdelta.ingest import ingest_to_staging
from healthdelta.identity import build_identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="healthdelta")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Stage Apple Health export input deterministically")
    ingest.add_argument("--input", required=True, help="Path to export.zip or an unpacked export directory")
    ingest.add_argument("--out", default="data/staging", help="Staging root directory (default: data/staging)")

    identity = sub.add_parser("identity", help="Build canonical identity registry")
    identity_sub = identity.add_subparsers(dest="identity_command", required=True)

    identity_build = identity_sub.add_parser("build", help="Build canonical people + aliases from a staging run")
    identity_build.add_argument("--input", required=True, help="Path to data/staging/<run_id>")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        ingest_to_staging(input_path=args.input, staging_root=args.out)
        return 0

    if args.command == "identity" and args.identity_command == "build":
        build_identity(staging_run_dir=args.input)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")
