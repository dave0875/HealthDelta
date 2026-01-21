import argparse
from pathlib import Path

from healthdelta.ingest import ingest_to_staging
from healthdelta.deid import deidentify_run
from healthdelta.identity import build_identity
from healthdelta.duckdb_tools import build_duckdb, query_duckdb
from healthdelta.ndjson_export import export_ndjson
from healthdelta.pipeline import run_pipeline
from healthdelta.reporting import build_report, show_report
from healthdelta.operator import run_all as run_all_operator
from healthdelta.state import register_existing_run_dir


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
    pipeline_run.add_argument("--state", default=None, help="State directory (default: <base_out>/state)")
    pipeline_run.add_argument("--since", default="last", help="Parent run selector: 'last' (default) or an explicit run_id")
    pipeline_run.add_argument("--note", default=None, help="Optional run note (stored in run registry)")

    run_cmd = sub.add_parser("run", help="Run registry commands (stateful)")
    run_sub = run_cmd.add_subparsers(dest="run_command", required=True)

    run_register = run_sub.add_parser("register", help="Register an existing staging run in the run registry")
    run_register.add_argument("--run", required=True, help="Path to an existing run directory (e.g., data/staging/<run_id>)")
    run_register.add_argument("--state", default="data/state", help="State directory (default: data/state)")
    run_register.add_argument("--note", default=None, help="Optional note to store for the run")

    run_all = run_sub.add_parser("all", help="One-shot operator command (pipeline -> ndjson -> duckdb -> reports)")
    run_all.add_argument("--input", required=True, help="Path to export.zip or unpacked export directory")
    run_all.add_argument("--out", default="data", help="Base output directory (default: data)")
    run_all.add_argument("--state", default=None, help="State directory (default: <base_out>/state)")
    run_all.add_argument("--since", default="last", help="Parent run selector: 'last' (default) or an explicit run_id")
    run_all.add_argument("--mode", default="share", choices=["local", "share"], help="Run mode (default: share)")
    run_all.add_argument("--note", default=None, help="Optional run note (stored in run registry)")

    export = sub.add_parser("export", help="Export canonical, share-safe datasets")
    export_sub = export.add_subparsers(dest="export_command", required=True)

    export_nd = export_sub.add_parser("ndjson", help="Export canonical NDJSON streams")
    export_nd.add_argument("--input", required=True, help="Path to pipeline run dir (staging/<run_id> or deid/<run_id>)")
    export_nd.add_argument("--out", required=True, help="Output directory for NDJSON streams")
    export_nd.add_argument("--mode", default="local", choices=["local", "share"], help="Export mode (default: local)")

    duckdb_cmd = sub.add_parser("duckdb", help="DuckDB build + query commands for canonical NDJSON")
    duckdb_sub = duckdb_cmd.add_subparsers(dest="duckdb_command", required=True)

    duckdb_build = duckdb_sub.add_parser("build", help="Build a DuckDB database from NDJSON streams")
    duckdb_build.add_argument("--input", required=True, help="Directory containing canonical NDJSON streams")
    duckdb_build.add_argument("--db", required=True, help="Output DuckDB file path")
    duckdb_build.add_argument("--replace", action="store_true", help="Replace existing DB file")

    duckdb_query = duckdb_sub.add_parser("query", help="Run a SQL query against a DuckDB database")
    duckdb_query.add_argument("--db", required=True, help="DuckDB file path")
    duckdb_query.add_argument("--sql", required=True, help="SQL to execute")
    duckdb_query.add_argument("--out", default=None, help="Optional output CSV path (default: stdout)")

    report = sub.add_parser("report", help="Deterministic share-safe reports from DuckDB")
    report_sub = report.add_subparsers(dest="report_command", required=True)

    report_build = report_sub.add_parser("build", help="Generate share-safe report artifacts from a DuckDB database")
    report_build.add_argument("--db", required=True, help="DuckDB file path")
    report_build.add_argument("--out", required=True, help="Output directory for report artifacts")
    report_build.add_argument("--mode", default="local", choices=["local", "share"], help="Report mode (default: local)")

    report_show = report_sub.add_parser("show", help="Print a short deterministic report summary to stdout")
    report_show.add_argument("--db", required=True, help="DuckDB file path")

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
        state_dir = args.state or str(Path(args.out) / "state")
        return run_pipeline(
            input_path=args.input,
            base_dir=args.out,
            mode=args.mode,
            expected_run_id=args.run_id,
            skip_deid=args.skip_deid,
            state_dir=state_dir,
            since=args.since,
            note=args.note,
        )

    if args.command == "export" and args.export_command == "ndjson":
        export_ndjson(input_dir=args.input, out_dir=args.out, mode=args.mode)
        return 0

    if args.command == "duckdb" and args.duckdb_command == "build":
        build_duckdb(input_dir=args.input, db_path=args.db, replace=bool(args.replace))
        return 0

    if args.command == "duckdb" and args.duckdb_command == "query":
        query_duckdb(db_path=args.db, sql=args.sql, out_path=args.out)
        return 0

    if args.command == "report" and args.report_command == "build":
        build_report(db_path=args.db, out_dir=args.out, mode=args.mode)
        return 0

    if args.command == "report" and args.report_command == "show":
        show_report(db_path=args.db)
        return 0

    if args.command == "run" and args.run_command == "register":
        register_existing_run_dir(run_dir=Path(args.run), state_dir=args.state, note=args.note)
        return 0

    if args.command == "run" and args.run_command == "all":
        return run_all_operator(
            input_path=args.input,
            base_out=args.out,
            state_dir=args.state,
            since=args.since,
            mode=args.mode,
            note=args.note,
        )

    raise AssertionError(f"Unhandled command: {args.command}")
