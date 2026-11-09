#!/bin/bash
# Validate the IBC auto-login wiring WITHOUT launching anything.
set -uo pipefail
IBKR_UTIL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$IBKR_UTIL_DIR/../.." && pwd)"
BROKER_ENV_FILE="${MARKETMAKER_ENV_FILE:-$REPO/.env}"
IBC_PATH="${IBC_PATH:-$REPO/.runtime/ibkr/ibc}"
IBC_INI="${IBC_INI:-$IBC_PATH/config/marketmaker_paper.ini}"
ok=1
chk(){ if eval "$2"; then echo "  PASS $1"; else echo "  FAIL $1"; ok=0; fi; }
echo "IB Gateway / IBC preflight:"
chk "standalone offline gateway 10.45"  '[ -d "$HOME/Applications/IB Gateway 10.45/jars" ]'
chk "IBC installed"                     '[ -x "$IBC_PATH/gatewaystartmacos.sh" ]'
chk "paper config present + locked 600" '[ "$(stat -f %A "$IBC_INI" 2>/dev/null)" = "600" ]'
chk "config is paper mode"              'grep -q "^TradingMode=paper" "$IBC_INI"'
chk "config port 4002"                  'grep -q "^OverrideTwsApiPort=4002" "$IBC_INI"'
chk "password NOT in config"            '! grep -qE "^Password=.+" "$IBC_INI"'
chk "IBKR_USERNAME in .env"             'grep -q "^IBKR_USERNAME=" "$BROKER_ENV_FILE"'
chk "IBKR_PASSWORD in .env"             'grep -q "^IBKR_PASSWORD=" "$BROKER_ENV_FILE"'
chk "start script executable"           '[ -x "$REPO/utils/ibkr/start.sh" ]'
chk "java present"                      'command -v java >/dev/null'
echo "RESULT: $([ $ok = 1 ] && echo ALL-PASS || echo HAS-FAILURES)"
exit $((1-ok))
