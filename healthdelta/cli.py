import argparse

from healthdelta.ingest import ingest_to_staging
from healthdelta.deid import deidentify_run
from healthdelta.identity import build_identity
from healthdelta.ndjson_export import export_ndjson
from healthdelta.pipeline import run_pipeline


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

    deid = sub.add_parser("deid", help="De-identify a staging run into a share-safe dataset")
    deid.add_argument("--input", required=True, help="Path to data/staging/<run_id>")
    deid.add_argument("--identity", required=True, help="Path to data/identity directory")
    deid.add_argument("--out", required=True, help="Output directory (e.g., data/deid/<run_id>/)")

    pipeline = sub.add_parser("pipeline", help="Orchestrate ingest -> identity -> deid")
    pipeline_sub = pipeline.add_subparsers(dest="pipeline_command", required=True)

    pipeline_run = pipeline_sub.add_parser("run", help="Run the HealthDelta pipeline")
    pipeline_run.add_argument("--input", required=True, help="Path to export.zip or unpacked export directory")
    pipeline_run.add_argument("--out", default="data", help="Base output directory (default: data)")
    pipeline_run.add_argument("--mode", default="local", choices=["local", "share"], help="Run mode (default: local)")
    pipeline_run.add_argument("--run-id", default=None, help="Expected run_id (must match computed run_id)")
    pipeline_run.add_argument("--skip-deid", action="store_true", help="Skip deid even in share mode (debugging)")

    export = sub.add_parser("export", help="Export canonical, share-safe datasets")
    export_sub = export.add_subparsers(dest="export_command", required=True)

    export_nd = export_sub.add_parser("ndjson", help="Export canonical NDJSON streams")
    export_nd.add_argument("--input", required=True, help="Path to pipeline run dir (staging/<run_id> or deid/<run_id>)")
    export_nd.add_argument("--out", required=True, help="Output directory for NDJSON streams")
    export_nd.add_argument("--mode", default="local", choices=["local", "share"], help="Export mode (default: local)")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        ingest_to_staging(input_path=args.input, staging_root=args.out)
        return 0

    if args.command == "identity" and args.identity_command == "build":
        build_identity(staging_run_dir=args.input)
        return 0

    if args.command == "deid":
        deidentify_run(staging_run_dir=args.input, identity_dir=args.identity, out_dir=args.out)
        return 0

    if args.command == "pipeline" and args.pipeline_command == "run":
        return run_pipeline(
            input_path=args.input,
            base_dir=args.out,
            mode=args.mode,
            expected_run_id=args.run_id,
            skip_deid=args.skip_deid,
        )

    if args.command == "export" and args.export_command == "ndjson":
        export_ndjson(input_dir=args.input, out_dir=args.out, mode=args.mode)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")
