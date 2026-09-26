#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
PYTHON=${PYTHON:-python3}
if [[ -x .venv/bin/python ]]; then PYTHON=.venv/bin/python; fi
exec "$PYTHON" studio.py "$@"
