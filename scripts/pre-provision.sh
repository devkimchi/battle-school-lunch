#!/usr/bin/env sh

set -eu

if [ -z "${NEIS_API_KEY:-}" ]; then
  echo "ERROR: NEIS_API_KEY is not set in the azd environment." >&2
  echo "Run: azd env set NEIS_API_KEY <your-key>" >&2
  exit 1
fi
