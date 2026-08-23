#!/bin/sh

# Build the interim Python wheel used for package validation.  The native
# signed/notarized macOS application remains a separate release gate.
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin="$repo_root/.venv/bin/python"
output_dir="${1:-$repo_root/dist}"

if [ ! -x "$python_bin" ]; then
    echo "Missing canonical .venv; create it with Python 3.12.13 first." >&2
    exit 2
fi

if ! "$python_bin" -c 'import build' >/dev/null 2>&1; then
    echo "Missing build tools; install setuptools, wheel, and build in .venv." >&2
    exit 2
fi

if [ -e "$output_dir" ]; then
    echo "Refusing to overwrite existing output directory: $output_dir" >&2
    exit 2
fi

source_epoch="${SOURCE_DATE_EPOCH:-$(git -C "$repo_root" show -s --format=%ct HEAD)}"
mkdir -p "$output_dir"
SOURCE_DATE_EPOCH="$source_epoch" "$python_bin" -m build \
    --wheel --no-isolation --outdir "$output_dir" "$repo_root"
echo "Wheel written to $output_dir (SOURCE_DATE_EPOCH=$source_epoch)"
