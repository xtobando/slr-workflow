#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${SLR_PYTHON:-}" ]]; then
    exec "$SLR_PYTHON" "$script_dir/setup.py"
fi
for candidate in python3 python python3.14 python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info[:2] < (3, 11))' >/dev/null 2>&1; then
        exec "$candidate" "$script_dir/setup.py"
    fi
done
echo 'Python 3.11 or newer was not found. Install it or set SLR_PYTHON to its executable path. See docs/installation.md.' >&2
exit 1
