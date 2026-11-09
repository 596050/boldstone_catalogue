#!/usr/bin/env bash
# Capture the evaluator, then replay the frozen IG pair using Toshiba.
set -euo pipefail

mm_v2_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$mm_v2_root"
exec python3 -B research/utility/isolated_replay_v1/launch.py "$@"
