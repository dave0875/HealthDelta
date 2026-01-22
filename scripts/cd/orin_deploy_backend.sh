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
  if command -v sudo >/dev/null 2>&1; then
    sudo mkdir -p "$DEPLOY_DIR"
    sudo chown "$USER":"$USER" "$DEPLOY_DIR"
  else
    echo "ERROR: deploy dir '$DEPLOY_DIR' does not exist and sudo is unavailable" >&2
    exit 2
  fi
fi

cp "$REPO_ROOT/deploy/orin/compose.yaml" "$DEPLOY_DIR/compose.yaml"
cat >"$DEPLOY_DIR/.env" <<EOF
HEALTHDELTA_BACKEND_IMAGE_TAG=$TAG
EOF

cd "$DEPLOY_DIR"

docker compose --env-file .env pull "$SERVICE_NAME"
docker compose --env-file .env up -d --remove-orphans

DEPLOY_DIR="$DEPLOY_DIR" SERVICE_NAME="$SERVICE_NAME" BASE_URL="$BASE_URL" \
  EXPECTED_TAG="$TAG" EXPECTED_VERSION="$VERSION" EXPECTED_SHA="$GIT_SHA" \
  "$REPO_ROOT/scripts/cd/orin_verify_backend.sh"

