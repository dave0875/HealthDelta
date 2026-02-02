#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/healthdelta}"
DATA_DIR="${DATA_DIR:-$DEPLOY_DIR/data}"
SERVICE_NAME="${SERVICE_NAME:-backend}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
FIXTURE_INPUT_PATH="${FIXTURE_INPUT_PATH:-/app/tests/fixtures/profile_export}"

EXPECTED_TAG="${EXPECTED_TAG:?expected image tag (e.g., v0.0.2)}"
EXPECTED_VERSION="${EXPECTED_VERSION:?expected version (e.g., 0.0.2)}"
EXPECTED_SHA="${EXPECTED_SHA:?expected git sha}"
SENTINEL_NAME="${SENTINEL_NAME:-.healthdelta_sentinel}"
SENTINEL_PATH="/app/data/${SENTINEL_NAME}"

wait_for_healthz() {
  for i in $(seq 1 60); do
    if curl -fsS "$BASE_URL/healthz" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

cd "$DEPLOY_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found on runner" >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose not available on runner" >&2
  exit 2
fi

cid="$(docker compose ps -q "$SERVICE_NAME" || true)"
if [ -z "$cid" ]; then
  echo "ERROR: compose service '$SERVICE_NAME' container not found" >&2
  docker compose ps || true
  exit 2
fi

image="$(docker inspect --format '{{.Config.Image}}' "$cid" || true)"
echo "container_id=$cid"
echo "container_image=$image"

if [[ "$image" != *":${EXPECTED_TAG}"* ]]; then
  echo "ERROR: expected image tag ':${EXPECTED_TAG}' not found in '$image'" >&2
  exit 1
fi

if ! wait_for_healthz; then
  echo "ERROR: backend failed health check at $BASE_URL/healthz" >&2
  exit 1
fi

curl -fsS "$BASE_URL/healthz"
ver_json="$(curl -fsS "$BASE_URL/version")"
echo "$ver_json"

VER_JSON="$ver_json" EXPECTED_VERSION="$EXPECTED_VERSION" EXPECTED_SHA="$EXPECTED_SHA" python3 - <<'PY'
import json, os
obj = json.loads(os.environ["VER_JSON"])
expected_version = os.environ["EXPECTED_VERSION"]
expected_sha = os.environ["EXPECTED_SHA"]
if obj.get("version") != expected_version:
    raise SystemExit(f"version mismatch: got={obj.get('version')} expected={expected_version}")
if obj.get("git_sha") != expected_sha:
    raise SystemExit(f"git_sha mismatch: got={obj.get('git_sha')} expected={expected_sha}")
print("ok")
PY

if [ ! -d "$DATA_DIR" ]; then
  echo "ERROR: expected host data dir '$DATA_DIR' does not exist." >&2
  echo "how to fix: ensure deploy step creates '$DATA_DIR' and compose mounts it to /app/data." >&2
  exit 1
fi

if [ ! -w "$DATA_DIR" ]; then
  echo "ERROR: host data dir '$DATA_DIR' is not writable by user '$(id -un)'." >&2
  echo "how to fix: sudo chown <runner-user>:<runner-user> $DATA_DIR" >&2
  exit 1
fi

inspect_json="$(docker inspect "$cid")"
MOUNTS_JSON="$inspect_json" EXPECTED_SOURCE="$DATA_DIR" python3 - <<'PY'
import json, os
obj = json.loads(os.environ["MOUNTS_JSON"])
mounts = obj[0].get("Mounts") if obj else []
expected_source = os.environ["EXPECTED_SOURCE"]
matched = None
for m in mounts:
    if m.get("Destination") == "/app/data":
        matched = m
        break
if matched is None:
    raise SystemExit(
        "data-plane mismatch: container is missing mount for /app/data. "
        "Fix compose volumes: /opt/healthdelta/data:/app/data"
    )
source = matched.get("Source")
if source != expected_source:
    raise SystemExit(
        f"data-plane mismatch: /app/data mount source is '{source}', expected '{expected_source}'. "
        "Fix compose bind mount to use /opt/healthdelta/data."
    )
if not matched.get("RW", False):
    raise SystemExit("data-plane mismatch: /app/data mount is not writable (RW=false).")
print("data_plane_mount_ok")
PY

sentinel_value="healthdelta-sentinel:${EXPECTED_TAG}:${EXPECTED_SHA}"
docker exec "$cid" sh -lc "printf '%s\n' '$sentinel_value' > '$SENTINEL_PATH'" || {
  echo "ERROR: failed writing sentinel inside container at '$SENTINEL_PATH'." >&2
  echo "how to fix: verify /app/data is a writable bind mount and host dir ownership is correct." >&2
  exit 1
}
read_back="$(docker exec "$cid" sh -lc "cat '$SENTINEL_PATH'")"
if [ "$read_back" != "$sentinel_value" ]; then
  echo "ERROR: sentinel roundtrip inside container failed at '$SENTINEL_PATH'." >&2
  exit 1
fi

host_sentinel="$DATA_DIR/$SENTINEL_NAME"
if [ ! -f "$host_sentinel" ]; then
  echo "ERROR: sentinel file '$host_sentinel' not found on host after container write." >&2
  echo "how to fix: verify compose bind mount '/opt/healthdelta/data:/app/data' is applied." >&2
  exit 1
fi
host_read_back="$(cat "$host_sentinel")"
if [ "$host_read_back" != "$sentinel_value" ]; then
  echo "ERROR: host sentinel content mismatch after container write." >&2
  exit 1
fi

docker compose --env-file .env restart "$SERVICE_NAME" >/dev/null
new_cid="$(docker compose ps -q "$SERVICE_NAME" || true)"
if [ -z "$new_cid" ]; then
  echo "ERROR: service '$SERVICE_NAME' missing after restart." >&2
  exit 1
fi
if ! wait_for_healthz; then
  echo "ERROR: backend did not recover after restart for persistence check." >&2
  exit 1
fi
after_restart="$(docker exec "$new_cid" sh -lc "cat '$SENTINEL_PATH'")"
if [ "$after_restart" != "$sentinel_value" ]; then
  echo "ERROR: sentinel did not persist across restart/redeploy data-plane check." >&2
  echo "how to fix: verify host bind mount '/opt/healthdelta/data:/app/data' is configured and writable." >&2
  exit 1
fi
echo "data_plane_sentinel_ok"

summary_payload="$(python3 - <<'PY'
import json, os
payload = {"input_path": os.environ["FIXTURE_INPUT_PATH"], "citation_limit": 5}
print(json.dumps(payload, sort_keys=True))
PY
)"
summary_json="$(curl -fsS -X POST "$BASE_URL/summary" -H 'content-type: application/json' --data "$summary_payload")"
echo "$summary_json"
SUMMARY_JSON="$summary_json" python3 - <<'PY'
import json, os
obj = json.loads(os.environ["SUMMARY_JSON"])
if not isinstance(obj.get("summary"), str):
    raise SystemExit("summary shape invalid: missing summary")
if not isinstance(obj.get("citations"), list) or not obj.get("citations"):
    raise SystemExit("summary shape invalid: citations missing")
if not isinstance(obj.get("risk_flags"), dict) or "disclaimer" not in obj["risk_flags"]:
    raise SystemExit("summary shape invalid: risk_flags missing")
print("summary_ok")
PY

qa_payload="$(python3 - <<'PY'
import json, os
payload = {
    "input_path": os.environ["FIXTURE_INPUT_PATH"],
    "question": "what observations exist?",
    "citation_limit": 5,
}
print(json.dumps(payload, sort_keys=True))
PY
)"
qa_json="$(curl -fsS -X POST "$BASE_URL/qa" -H 'content-type: application/json' --data "$qa_payload")"
echo "$qa_json"
QA_JSON="$qa_json" python3 - <<'PY'
import json, os
obj = json.loads(os.environ["QA_JSON"])
qa = obj.get("qa")
if not isinstance(qa, dict):
    raise SystemExit("qa shape invalid: missing qa object")
if not isinstance(qa.get("citations"), list) or not qa["citations"]:
    raise SystemExit("qa shape invalid: citations missing")
if not isinstance(qa.get("disclaimer"), str) or "not medical advice" not in qa["disclaimer"].lower():
    raise SystemExit("qa shape invalid: disclaimer missing")
print("qa_ok")
PY

tail_logs="$(docker logs --tail 200 "$cid" 2>&1 || true)"
echo "$tail_logs" | grep -E "Traceback \\(most recent call last\\)|\\bFATAL\\b|\\bCRITICAL\\b" >/dev/null && {
  echo "ERROR: fatal indicator found in recent logs" >&2
  exit 1
}

echo "ok: verification passed"
