#!/usr/bin/env bash
# No dependencies are installed; no stdout is mixed into structured output.
if ! command -v python3 >/dev/null 2>&1; then
  if [ "${1-}" = capture ]; then exit 0; fi
  echo 'Task Observer needs an existing Python 3 interpreter; ordinary work is unaffected' >&2
  exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$(cd -- "$(dirname -- "$0")" && pwd)/observer.py" "$@"
