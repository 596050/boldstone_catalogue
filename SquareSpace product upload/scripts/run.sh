#!/usr/bin/env bash
# Downloads every product photo from boldstonesculpture.com and writes correctly-sized
# JPEGs into each post folder.
#
#   cd "SquareSpace product upload/scripts"
#   ./run.sh                 (or:  bash run.sh)
#
# Creates a self-contained virtualenv in scripts/.venv so nothing touches your system
# Python — this is what Homebrew's PEP 668 "externally-managed-environment" error wants.
# Safe to re-run; it reuses the venv and skips images already downloaded.

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtualenv in scripts/.venv ..."
  python3 -m venv .venv
fi

echo "Installing requests + pillow into the venv ..."
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt

echo "Running the image pipeline ..."
exec ./.venv/bin/python fetch_and_resize.py "$@"
