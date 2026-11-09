#!/bin/bash
# Auto-start IB Gateway (PAPER) via IBC, credentials sourced from .env at launch.
# The password is mapped OS-env -> IBC's TWSPASSWORD in this process only; it is
# never written to any file and never echoed. Wired into the supervisor via
# IB_GATEWAY_RESTART_CMD. A normal invocation refuses to launch if a gateway is
# already listening.  The supervisor may pass --recover-unhealthy after a full
# write-capable API handshake (not merely the TCP port) has failed.
set -euo pipefail
IBKR_UTIL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$IBKR_UTIL_DIR/../.." && pwd)"

RECOVER_UNHEALTHY=0
if [ "${1:-}" = "--recover-unhealthy" ]; then
  RECOVER_UNHEALTHY=1
  shift
fi
if [ "$#" -ne 0 ]; then
  echo "usage: $0 [--recover-unhealthy]" >&2
  exit 64
fi

# Serialise launches: a non-blocking flock means a concurrent invocation exits
# instead of starting a duplicate gateway (belt-and-suspenders with the singleton mgr).
# Lock and IBC logs must live on LOCAL disk: data/research is a symlink to an
# external volume, and a launchd agent has no TCC grant for removable volumes,
# so this failed with "Operation not permitted" and the agent could never launch.
mkdir -p "$REPO/.runtime" 2>/dev/null || true
exec 9>"$REPO/.runtime/ib_gateway_launch.lock"
if ! /usr/bin/env flock -n 9 2>/dev/null && ! flock -n 9 2>/dev/null; then
  # macOS lacks flock(1) by default; fall back to a pgrep guard
  if pgrep -f "gatewaystartmacos.sh -inline" >/dev/null 2>&1; then
    echo "$(date -u +%FT%TZ) ib_gateway_start: another launch in progress, exiting"; exit 0
  fi
fi

# Manual startup is opt-in. Automatic jobs were removed at the user's request.
# Set IBC_AUTOLOGIN_ENABLED=1 for an explicit invocation of this script.
if [ "${IBC_AUTOLOGIN_ENABLED:-0}" != "1" ]; then
  echo "$(date -u +%FT%TZ) ib_gateway_start: auto-login disabled (IBC_AUTOLOGIN_ENABLED!=1) -> alert-only"
  osascript -e 'display notification "IB Gateway down - manual login needed (IBC auto-login not yet enabled)" with title "marketmaker supervisor"' 2>/dev/null || true
  exit 0
fi

# This former supervisor flag must not recreate or restart a removed service.
if [ "$RECOVER_UNHEALTHY" = "1" ]; then
  echo "ib_gateway_start: automatic recovery was removed; stop the old process before an explicit manual start" >&2
  exit 69
fi

# already up? do nothing (never double-launch a live session)
if nc -z -w2 127.0.0.1 4002 2>/dev/null; then
  echo "$(date -u +%FT%TZ) ib_gateway_start: 4002 already listening, no action"; exit 0
fi

# 4002 is DOWN. If a gateway for this config is still running it is either
# (a) legitimately mid-startup (login takes ~1-2 min) -> leave it alone, or
# (b) hung/stuck (e.g. sitting on a failed-login or render-failed dialog) ->
# it must be cleared, because gatewaystartmacos.sh refuses to relaunch while any
# gateway process for this ini exists. Without this, a single transient login
# failure makes the outage self-sustaining (root cause of the 2026-07-18 outage:
# stuck "Unrecognized Username or Password" process blocked every 30-min retry).
# The age gate ensures we never kill a healthy in-progress login.
STUCK_AFTER_SECONDS="${IB_GATEWAY_STUCK_AFTER_SECONDS:-420}"
existing_pid="$(pgrep -f 'ibcalpha.ibc.IbcGateway' 2>/dev/null | head -1 || true)"
if [ -n "${existing_pid:-}" ]; then
  # macOS ps has elapsed-time (`etime`) but not Linux's elapsed-seconds
  # (`etimes`). Convert [[dd-]hh:]mm:ss to seconds.
  age="$(
    ps -o etime= -p "$existing_pid" 2>/dev/null |
      tr -d ' ' |
      awk -F'[-:]' '
        NF == 4 { print ($1 * 86400) + ($2 * 3600) + ($3 * 60) + $4; next }
        NF == 3 { print ($1 * 3600) + ($2 * 60) + $3; next }
        NF == 2 { print ($1 * 60) + $2; next }
      ' || true
  )"
  age="${age:-0}"
  if [ "$age" -lt "$STUCK_AFTER_SECONDS" ]; then
    echo "$(date -u +%FT%TZ) ib_gateway_start: gateway pid $existing_pid starting up (age ${age}s < ${STUCK_AFTER_SECONDS}s) and 4002 not up yet -> leaving it alone"
    exit 0
  fi
  echo "$(date -u +%FT%TZ) ib_gateway_start: gateway pid $existing_pid is STALE (age ${age}s, 4002 down) -> terminating before relaunch"
  pkill -TERM -f 'ibcalpha.ibc.IbcGateway'   2>/dev/null || true
  pkill -TERM -f 'gatewaystartmacos.sh'      2>/dev/null || true
  pkill -TERM -f 'displaybannerandlaunch.sh' 2>/dev/null || true
  for _ in $(seq 1 10); do
    pgrep -f 'ibcalpha.ibc.IbcGateway' >/dev/null 2>&1 || break
    sleep 1
  done
  # Never force-kill the process. If the named Gateway does not honour TERM,
  # alert and let an operator inspect it rather than risking unrelated runtime
  # processes.
  if pgrep -f 'ibcalpha.ibc.IbcGateway' >/dev/null 2>&1; then
    echo "$(date -u +%FT%TZ) ib_gateway_start: stale gateway did not exit on SIGTERM -> operator attention required"
    osascript -e 'display notification "Stale IB Gateway did not exit cleanly; manual attention required" with title "marketmaker supervisor"' 2>/dev/null || true
    exit 1
  fi
fi

# source credentials without echoing; export IBC's expected names
set -a; # shellcheck disable=SC1091
source "${MARKETMAKER_ENV_FILE:-$REPO/.env}"; set +a
export TWSUSERID="${IBKR_USERNAME:?IBKR_USERNAME missing in .env}"
export TWSPASSWORD="${IBKR_PASSWORD:?IBKR_PASSWORD missing in .env}"

export TWS_MAJOR_VRSN="10.45"
export IBC_PATH="${IBC_PATH:-$REPO/.runtime/ibkr/ibc}"
export TWS_PATH="$HOME/Applications"

# IBC requires the OFFLINE/standalone Gateway (has a jars/ folder). The installed
# auto-updating "IB Gateway.app" has no jars IBC can hook -> alert-only until the
# offline gateway is installed, so the supervisor never spam-launches a broken run.
if ! find "$HOME/Applications" "$HOME/Jts" -maxdepth 3 -type d -name jars 2>/dev/null | grep -q .; then
  echo "$(date -u +%FT%TZ) ib_gateway_start: OFFLINE gateway not installed (no jars/) -> alert-only, not launching IBC"
  osascript -e 'display notification "IB Gateway down; offline gateway not installed for IBC auto-login - manual login needed" with title "marketmaker supervisor"' 2>/dev/null || true
  exit 0
fi
export IBC_INI="${IBC_INI:-$IBC_PATH/config/marketmaker_paper.ini}"
export TWS_SETTINGS_PATH="$HOME/Jts"
export LOG_PATH="$REPO/.runtime/ibc_logs"
mkdir -p "$LOG_PATH"

echo "$(date -u +%FT%TZ) ib_gateway_start: launching IBC (paper, port 4002, user=${TWSUSERID:0:2}***)"
if [ "${IB_GATEWAY_FOREGROUND:-0}" = "1" ]; then
  # A LaunchAgent must own the long-running IBC process directly.  If this
  # script backgrounds IBC and exits, launchd may terminate the abandoned
  # process group even when nohup/disown were used.
  echo "$(date -u +%FT%TZ) ib_gateway_start: foreground mode; launchd owns IBC"
  exec "$IBC_PATH/gatewaystartmacos.sh" -inline
fi

# Daemonize: IBC must outlive short-lived callers. launchd singleton jobs exit
# within seconds and macOS kills abandoned process groups, so an exec'd/child
# IBC dies with its caller (2026-07-10 drill finding: every singleton
# "launched_gateway" attempt vanished instantly; manual runs only survived
# because the invoking shells were long-lived).
nohup "$IBC_PATH/gatewaystartmacos.sh" -inline >> "$LOG_PATH/ibc_start.log" 2>&1 < /dev/null &
IBC_PID=$!
disown "$IBC_PID" 2>/dev/null || true
echo "$(date -u +%FT%TZ) ib_gateway_start: IBC launched detached (pid $IBC_PID)"
