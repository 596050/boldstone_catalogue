#!/bin/bash
# Ensure IQConnect (IQFeed) is running under Wine, auto-logged-in from .env.
# Mirrors ib_gateway_start.sh. IQFeed login is fully automatic (no GUI/2FA) via
# -login/-password/-autoconnect in the boot script. No-op if 9100 already up.
set -uo pipefail
IQFEED_UTIL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$IQFEED_UTIL_DIR/../.." && pwd)"
cd "$REPO"
# launchd callers get a minimal PATH without /opt/homebrew/bin, where wine64
# lives (2026-07-10 drill finding, same class as the IBC env gate).
export PATH="/opt/homebrew/bin:$PATH"
if nc -z -w2 127.0.0.1 9100 2>/dev/null; then
  echo "$(date -u +%FT%TZ) iqfeed_start: 9100 already listening, no action"; exit 0
fi
BROKER_ENV_FILE="${MARKETMAKER_ENV_FILE:-$REPO/.env}"
if [ -f "$BROKER_ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$BROKER_ENV_FILE"
  set +a
fi
export ROOT="$IQFEED_UTIL_DIR"
export WINEPREFIX="${WINEPREFIX:-${IQFEED_WINEPREFIX:-$REPO/.runtime/iqfeed/wineprefix}}"
export IQCONNECT_PATH="${IQCONNECT_PATH:-$WINEPREFIX/drive_c/Program Files/DTN/IQFeed/iqconnect.exe}"
export WINE_BINARY="${WINE_BINARY:-wine64}"
export IQFEED_LOG_DIR="${IQFEED_LOG_DIR:-$REPO/.runtime/iqfeed/logs}"
LOG="$IQFEED_LOG_DIR"; mkdir -p "$LOG"
echo "$(date -u +%FT%TZ) iqfeed_start: launching IQConnect under Wine" >> "$LOG/iqfeed_start.log"
# shellcheck disable=SC1091
source "$ROOT/lib/ensure_iqfeed_lookup.sh"
ensure_iqfeed_lookup >> "$LOG/iqfeed_start.log" 2>&1
