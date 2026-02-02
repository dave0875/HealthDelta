#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from healthdelta.backend_server import make_server


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run backend /summary vertical-slice smoke request.")
    p.add_argument("--input", required=True, help="Synthetic fixture input directory")
    p.add_argument("--work", required=True, help="Working directory for slice outputs")
    p.add_argument("--response", required=True, help="Output JSON response path")
    p.add_argument("--log", required=True, help="Output smoke log path")
    args = p.parse_args(argv)

    server = make_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    status = 0
    detail = "ok"
    response_obj: dict[str, object] = {}
    try:
        req_body = json.dumps(
            {
                "input_path": str(Path(args.input).resolve()),
                "work_dir": str(Path(args.work).resolve()),
                "citation_limit": 10,
            },
            sort_keys=True,
        ).encode("utf-8")
        req = Request(base_url + "/summary", data=req_body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req) as resp:
            payload = resp.read().decode("utf-8")
            response_obj = json.loads(payload)
            if resp.status != 200:
                status = 1
                detail = f"unexpected status: {resp.status}"
            elif not isinstance(response_obj.get("citations"), list) or not response_obj.get("citations"):
                status = 1
                detail = "missing citations"
    except Exception as e:
        status = 1
        detail = str(e)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    _write(Path(args.response), json.dumps(response_obj, sort_keys=True, indent=2) + "\n")
    log_text = "\n".join(
        [
            f"status={status}",
            f"detail={detail}",
            f"response_path={args.response}",
            f"run_id={response_obj.get('run_id', '')}",
        ]
    )
    _write(Path(args.log), log_text + "\n")
    if status != 0:
        print(log_text)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
