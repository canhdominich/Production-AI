#!/usr/bin/env bash
set -euo pipefail

: "${APP_TAG:?APP_TAG is required}"
APP_DIR="${APP_DIR:-/srv/anhti-ai}"
RETRIES="${HEALTH_RETRIES:-30}"
DELAY="${HEALTH_DELAY:-2}"
cd "$APP_DIR"

previous=$(cat .release 2>/dev/null || echo "none")
export APP_TAG
docker compose -f compose.prod.yaml pull api worker
docker compose -f compose.prod.yaml up -d --remove-orphans

for i in $(seq 1 "$RETRIES"); do
  if curl -fsS http://127.0.0.1:8000/ready >/dev/null 2>&1; then
    echo "$APP_TAG" > .release
    echo "deployed $APP_TAG (previous $previous)"
    exit 0
  fi
  sleep "$DELAY"
done

echo "health check failed for $APP_TAG, rolling back to $previous" >&2
if [ "$previous" != "none" ]; then
  APP_TAG="$previous" docker compose -f compose.prod.yaml up -d
fi
exit 1
