# Shared helpers for the Mac/Linux IQFeed bash wrappers.
# Source this from each wrapper after defining $ROOT (the iq_feed directory).
#
# Provides:
#   load_env                — source ./.env if present
#   iqfeed_port_open        — return 0 if 127.0.0.1:9100 accepts a connection
#   ensure_iqfeed_lookup    — launch IQConnect under Wine if the port is closed
#   cleanup_iqfeed_wine     — stop Wine processes for this IQFeed WINEPREFIX

set -euo pipefail

: "${IQFEED_HOST:=127.0.0.1}"
: "${IQFEED_PORT:=9100}"
# Apple Silicon Game Porting Toolkit ships wine64 only.
: "${WINE_BINARY:=wine64}"
: "${WINEPREFIX:=${ROOT:-$PWD}/wineprefix}"
: "${IQCONNECT_PATH:=$WINEPREFIX/drive_c/Program Files/DTN/IQFeed/iqconnect.exe}"
: "${IQFEED_WAIT_SECONDS:=180}"
: "${IQFEED_VERSION:=1.0}"
export WINEPREFIX

load_env() {
    local env_file="${1:-${ROOT:-.}/.env}"
    if [ -f "$env_file" ]; then
        # Read KEY=VALUE lines, ignore comments, export each.
        while IFS= read -r line || [ -n "$line" ]; do
            case "$line" in
                ''|\#*) continue ;;
            esac
            if [[ "$line" != *=* ]]; then
                continue
            fi
            local key="${line%%=*}"
            local val="${line#*=}"
            key="${key## }"; key="${key%% }"
            val="${val## }"; val="${val%% }"
            val="${val%\"}"; val="${val#\"}"
            val="${val%\'}"; val="${val#\'}"
            [ -n "$key" ] || continue
            export "$key=$val"
        done < "$env_file"
    fi
}

iqfeed_port_open() {
    if command -v nc >/dev/null 2>&1; then
        nc -z -G 2 "$IQFEED_HOST" "$IQFEED_PORT" >/dev/null 2>&1
    else
        # /dev/tcp fallback (bash-only).
        (exec 3<>"/dev/tcp/$IQFEED_HOST/$IQFEED_PORT") >/dev/null 2>&1 && exec 3>&- 3<&-
    fi
}

_iqfeed_wineserver() {
    local wine_path
    wine_path="$(command -v "$WINE_BINARY" 2>/dev/null || true)"
    if [ -z "$wine_path" ] && [ -x "$WINE_BINARY" ]; then
        wine_path="$WINE_BINARY"
    fi
    if [ -n "$wine_path" ] && [ -x "$(dirname "$wine_path")/wineserver" ]; then
        printf '%s\n' "$(dirname "$wine_path")/wineserver"
        return 0
    fi
    if command -v wineserver >/dev/null 2>&1; then
        command -v wineserver
        return 0
    fi
    return 1
}

_kill_iqfeed_prefix_processes() {
    local signal="$1"
    ps -ax -o pid=,command= \
        | grep -Ei 'wine64-preloader|wine-preloader|wineserver|iqconnect' \
        | grep -v grep \
        | while read -r pid cmd; do
            [ -n "$pid" ] || continue
            # Match by command line first (wine processes carry the prefix's
            # iqconnect.exe path); fall back to lsof open-file matching for
            # wineserver/winedevice whose argv has no path.
            if printf '%s' "$cmd" | grep -F "$WINEPREFIX" >/dev/null 2>&1 \
               || printf '%s' "$cmd" | grep -qi 'iqconnect' \
               || { command -v lsof >/dev/null 2>&1 \
                    && lsof -p "$pid" 2>/dev/null | grep -F "$WINEPREFIX" >/dev/null 2>&1; }; then
                kill "-$signal" "$pid" >/dev/null 2>&1 || true
            fi
        done
}

cleanup_iqfeed_wine() {
    if [ "${IQFEED_KEEP_WINE:-0}" = "1" ]; then
        echo "Leaving IQFeed Wine processes running because IQFEED_KEEP_WINE=1." >&2
        return 0
    fi

    local server
    if server="$(_iqfeed_wineserver)"; then
        echo "Cleaning up IQFeed Wine prefix: $WINEPREFIX" >&2
        WINEPREFIX="$WINEPREFIX" "$server" -k >/dev/null 2>&1 || true
        WINEPREFIX="$WINEPREFIX" "$server" -w >/dev/null 2>&1 || true
        _kill_iqfeed_prefix_processes TERM
        sleep 1
        _kill_iqfeed_prefix_processes KILL
        return 0
    fi

    if command -v "$WINE_BINARY" >/dev/null 2>&1 || [ -x "$WINE_BINARY" ]; then
        echo "Cleaning up IQFeed Wine prefix via wineboot: $WINEPREFIX" >&2
        WINEPREFIX="$WINEPREFIX" "$WINE_BINARY" wineboot -e >/dev/null 2>&1 || true
        _kill_iqfeed_prefix_processes TERM
        sleep 1
        _kill_iqfeed_prefix_processes KILL
    fi
    return 0
}

_iqfeed_launch_and_wait() {
    local logs_dir="${IQFEED_LOG_DIR:-${ROOT:-$PWD}/iqfeed_data/logs}"
    mkdir -p "$logs_dir"
    logs_dir="$(cd "$logs_dir" && pwd)"  # absolute, so subshell cd below can't break it
    local stamp; stamp="$(date +"%Y%m%d_%H%M%S")"
    local log_file="$logs_dir/iqconnect_${stamp}.log"

    echo "Launching IQConnect under Wine. Log: $log_file" >&2
    (
        cd "$(dirname "$IQCONNECT_PATH")"
        nohup "$WINE_BINARY" "$IQCONNECT_PATH" \
            -product   "$IQFEED_PRODUCT" \
            -version   "$IQFEED_VERSION" \
            -login     "$IQFEED_LOGIN" \
            -password  "$IQFEED_PASSWORD" \
            -autoconnect \
            -savelogininfo \
            >"$log_file" 2>&1 &
    )

    local deadline=$(( $(date +%s) + IQFEED_WAIT_SECONDS ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        if iqfeed_port_open; then
            return 0
        fi
        sleep 1
    done
    echo "WARN: port $IQFEED_HOST:$IQFEED_PORT not open within ${IQFEED_WAIT_SECONDS}s (log: $log_file)" >&2
    return 1
}

# Keep one idle client attached so IQConnect never hits its no-client
# auto-shutdown (it exits ~5s after the last client disconnects — the cause
# of the 2026-06-11 "IQConnect keeps dying after every pull" incident).
_ensure_iqfeed_keepalive() {
    local script="${ROOT:-$PWD}/lib/iqfeed_keepalive.py"
    [ -f "$script" ] || return 0
    if pgrep -f "iqfeed_keepalive.py" >/dev/null 2>&1; then
        return 0
    fi
    nohup python3 "$script" >/dev/null 2>&1 &
    echo "Started IQConnect keepalive client (prevents no-client auto-shutdown)." >&2
}

ensure_iqfeed_lookup() {
    if iqfeed_port_open; then
        _ensure_iqfeed_keepalive
        return 0
    fi

    if ! command -v "$WINE_BINARY" >/dev/null 2>&1; then
        echo "ERROR: '$WINE_BINARY' not found. See docs/MAC_SETUP.md." >&2
        return 1
    fi

    if [ ! -f "$IQCONNECT_PATH" ]; then
        echo "ERROR: IQConnect not found at: $IQCONNECT_PATH" >&2
        echo "       Install IQFeed under Wine (see docs/MAC_SETUP.md) or set IQCONNECT_PATH." >&2
        return 1
    fi

    : "${IQFEED_PRODUCT:?IQFEED_PRODUCT not set (see .env.example)}"
    : "${IQFEED_LOGIN:?IQFEED_LOGIN not set (see .env.example)}"
    : "${IQFEED_PASSWORD:?IQFEED_PASSWORD not set (see .env.example)}"

    # Round 1: plain launch (the common cold-start case).
    if _iqfeed_launch_and_wait; then
        _ensure_iqfeed_keepalive
        return 0
    fi

    # Round 2 (auto-heal): a dead IQConnect usually leaves the Wine prefix
    # wedged (hung wineserver/winedevice/iqconnect), and fresh launches into a
    # wedged prefix never reach the listening state — observed 2026-06-11
    # (relaunches failed for hours until the prefix was cleared). Force-reset
    # the prefix (scoped to THIS WINEPREFIX via lsof) and relaunch once.
    echo "auto-heal: resetting IQFeed Wine prefix and relaunching IQConnect" >&2
    IQFEED_KEEP_WINE=0 cleanup_iqfeed_wine
    sleep 3
    if _iqfeed_launch_and_wait; then
        echo "auto-heal: IQConnect recovered after prefix reset" >&2
        _ensure_iqfeed_keepalive
        return 0
    fi

    echo "ERROR: IQFeed lookup port $IQFEED_HOST:$IQFEED_PORT did not open (launch + prefix-reset relaunch both failed)." >&2
    echo "       Check the iqconnect_*.log files in iqfeed_data/logs and DTN account status." >&2
    return 1
}
