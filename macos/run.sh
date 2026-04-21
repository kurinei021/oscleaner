#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if [ "$#" -eq 0 ]; then
  exec python3 "$ROOT_DIR/oscleaner.py" audit
fi

exec python3 "$ROOT_DIR/oscleaner.py" "$@"
