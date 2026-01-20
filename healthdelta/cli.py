import argparse

from healthdelta.ingest import ingest_to_staging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="healthdelta")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Stage Apple Health export input deterministically")
    ingest.add_argument("--input", required=True, help="Path to export.zip or an unpacked export directory")
    ingest.add_argument("--out", default="data/staging", help="Staging root directory (default: data/staging)")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        ingest_to_staging(input_path=args.input, staging_root=args.out)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")
