#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

DEPLOY_DIR="${DEPLOY_DIR:-/opt/healthdelta}"
SERVICE_NAME="${SERVICE_NAME:-backend}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"

TAG="${TAG:?tag to deploy (e.g., v0.0.2)}"
VERSION="${VERSION:?expected version (e.g., 0.0.2)}"
GIT_SHA="${GIT_SHA:?expected git sha}"

if [ ! -d "$DEPLOY_DIR" ]; then
  echo "ERROR: deploy dir '$DEPLOY_DIR' is missing." >&2
  echo "Create it once before deploy (Option A):" >&2
  echo "  sudo mkdir -p $DEPLOY_DIR && sudo chown <runner-user>:<runner-user> $DEPLOY_DIR" >&2
  exit 2
fi

if [ ! -w "$DEPLOY_DIR" ]; then
  echo "ERROR: deploy dir '$DEPLOY_DIR' is not writable by user '$(id -un)'." >&2
  echo "Fix ownership once: sudo chown <runner-user>:<runner-user> $DEPLOY_DIR" >&2
  exit 2
fi

cp "$REPO_ROOT/deploy/orin/compose.yaml" "$DEPLOY_DIR/compose.yaml"
cat >"$DEPLOY_DIR/.env" <<EOF
HEALTHDELTA_BACKEND_IMAGE_TAG=$TAG
EOF

cd "$DEPLOY_DIR"

docker compose --env-file .env pull "$SERVICE_NAME"
docker compose --env-file .env up -d --remove-orphans

DEPLOY_DIR="$DEPLOY_DIR" SERVICE_NAME="$SERVICE_NAME" BASE_URL="$BASE_URL" \
  FIXTURE_INPUT_PATH="/app/deploy/fixtures/profile_export" \
  EXPECTED_TAG="$TAG" EXPECTED_VERSION="$VERSION" EXPECTED_SHA="$GIT_SHA" \
  bash "$REPO_ROOT/scripts/cd/orin_verify_backend.sh"
