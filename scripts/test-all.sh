#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> AppHost"
(
  cd "$ROOT_DIR"
  npm ci
  npm run build
)

for service in api mcp agent; do
  echo "==> ${service}"
  (
    cd "$ROOT_DIR/src/$service"
    uv sync --all-groups --frozen
    uv run pytest
  )
done

echo "==> web"
(
  cd "$ROOT_DIR/src/web"
  npm ci
  npm run lint
  npm test
  npm run build
)

echo "==> e2e"
(
  cd "$ROOT_DIR/src/e2e"
  npm ci
  npx playwright install chromium
  npm test
)

echo "All validations passed."
