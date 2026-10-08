#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
    echo 'Run bash scripts/setup.sh first.' >&2
    exit 1
fi
exec "$project_dir/.venv/bin/python" "$project_dir/scripts/workbench.py" "$@"
