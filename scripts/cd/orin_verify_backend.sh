#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/healthdelta}"
SERVICE_NAME="${SERVICE_NAME:-backend}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
FIXTURE_INPUT_PATH="${FIXTURE_INPUT_PATH:-/app/tests/fixtures/profile_export}"

EXPECTED_TAG="${EXPECTED_TAG:?expected image tag (e.g., v0.0.2)}"
EXPECTED_VERSION="${EXPECTED_VERSION:?expected version (e.g., 0.0.2)}"
EXPECTED_SHA="${EXPECTED_SHA:?expected git sha}"

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

for i in $(seq 1 60); do
  if curl -fsS "$BASE_URL/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

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
