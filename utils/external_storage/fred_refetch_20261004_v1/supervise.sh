#!/bin/sh
# Restart the fetcher on transient failure until it reports COMPLETE.
# The 19 September transfer died on a one-off SSH drop and then sat idle for
# two weeks; a multi-day fetch must not fail the same way.
HERE=$(cd "$(dirname "$0")" && pwd)
LOG="$HERE/RUN.log"
PY=/opt/homebrew/opt/python@3.14/bin/python3.14
for attempt in $(seq 1 500); do
  status=$("$PY" -c "import json;print(json.load(open('$HERE/STATE.json'))['status'])" 2>/dev/null || echo NONE)
  if [ "$status" = "COMPLETE" ]; then
    echo "{\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"complete\",\"attempts\":$attempt}" >> "$LOG"
    exit 0
  fi
  echo "{\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"attempt_start\",\"n\":$attempt}" >> "$LOG"
  if "$PY" -u "$HERE/fetch_fred.py" >> "$LOG" 2>&1; then
    continue
  fi
  echo "{\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"attempt_failed\",\"n\":$attempt,\"backoff_s\":120}" >> "$LOG"
  sleep 120
done
echo "{\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"gave_up\"}" >> "$LOG"
exit 1
