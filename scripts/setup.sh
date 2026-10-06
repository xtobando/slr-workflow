#!/usr/bin/env bash
set -euo pipefail
if ! command -v python3.12 >/dev/null 2>&1; then
    echo 'Install Python 3.12 first; see the README platform instructions.' >&2
    exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3.12 "$script_dir/setup.py"
