#!/usr/bin/env bash

set -euo pipefail

workspace_dir="${CODESPACE_VSCODE_FOLDER:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "${workspace_dir}"

echo "Installing FastAPI dependencies..."
(
  cd src/api
  uv sync --all-groups --frozen
)

echo "Installing web dependencies..."
npm ci --prefix src/web

echo "Installing end-to-end test dependencies..."
npm ci --prefix src/e2e
(
  cd src/e2e
  npx playwright install --with-deps chromium
)

if [[ -z "${NEIS_API_KEY:-}" ]]; then
  echo "NEIS_API_KEY is not configured. Add it as a Codespaces secret for live API requests."
fi

echo "Codespaces environment is ready."
