#!/usr/bin/env sh

set -eu

if [ -n "${NEIS_API_KEY:-}" ]; then
  exit 0
fi

if STORED_KEY=$(azd env get-value NEIS_API_KEY 2>/dev/null) && [ -n "$STORED_KEY" ]; then
  exit 0
fi

if [ ! -t 0 ]; then
  echo "ERROR: NEIS_API_KEY is not set and no interactive terminal is available." >&2
  echo "Run: azd env set NEIS_API_KEY <your-key>" >&2
  exit 1
fi

restore_echo() {
  stty echo
}

printf "NEIS API key: "
trap restore_echo EXIT HUP INT TERM
stty -echo
IFS= read -r NEIS_API_KEY
stty echo
trap - EXIT HUP INT TERM
printf "\n"

if [ -z "$NEIS_API_KEY" ]; then
  echo "ERROR: NEIS API key cannot be empty." >&2
  exit 1
fi

azd env set NEIS_API_KEY "$NEIS_API_KEY"
unset NEIS_API_KEY
