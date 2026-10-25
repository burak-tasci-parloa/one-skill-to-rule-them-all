#!/usr/bin/env bash
# The same Python standard library already used by the upstream helpers.
set -u
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' '{"systemMessage":"Task Observer activation incomplete: python3 is unavailable; its startup hook did not run."}'
  exit 0
fi
exec python3 "$(cd -- "$(dirname -- "$0")" && pwd)/session-start.py" "$@"
