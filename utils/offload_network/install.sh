#!/bin/bash
# install.sh — set up the offload_orchestration package for development.
#
# pip 21.x (shipped with older macOS / Xcode CommandLineTools) cannot do
# editable installs from a pyproject-only project. This script upgrades pip
# and setuptools first, then runs `pip install -e .`. After it succeeds, the
# console scripts (fleet, remote-state-audit, processing-report,
# audit-external, clean-chunks) are on $PATH.
#
# Run from any directory:
#   bash utils/offload_network/install.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Installing fleet-offload-offload-orchestration from $HERE ..."

# Upgrade pip + setuptools first (needs PEP 660 support for editable installs)
python3 -m pip install --user --upgrade --quiet pip 'setuptools>=68' wheel
# Editable install
python3 -m pip install --user --quiet -e "$HERE"

# Surface where the console scripts ended up
USER_BASE="$(python3 -c 'import site; print(site.USER_BASE)')"
echo
echo "✓ install complete."
echo
echo "Console scripts installed under: $USER_BASE/bin"
echo "Add that to PATH if it isn't already:"
echo "  export PATH=\"$USER_BASE/bin:\$PATH\""
echo
echo "Then verify:"
echo "  fleet --help"
echo "  remote-state-audit --help"
echo "  audit-external --help"
echo "  clean-chunks --help"
