#!/bin/sh
# Auto-generated POSIX bootstrap for sealed job sim-5e00c1638c10
set -u
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
export PYTHONUTF8=1
export SEAL_JOB_ID='sim-5e00c1638c10'
SEAL_WORKDIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export SEAL_WORKDIR
cd "$SEAL_WORKDIR" || exit 74
printf '[bootstrap] starting runner at %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> bootstrap.log
'/opt/homebrew/opt/python@3.14/bin/python3.14' -u "$SEAL_WORKDIR/runner.py" "$SEAL_WORKDIR/manifest.json"
RUNNER_RC=$?
printf '[bootstrap] runner exited rc=%s at %s\n' "$RUNNER_RC" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> bootstrap.log
exit "$RUNNER_RC"
