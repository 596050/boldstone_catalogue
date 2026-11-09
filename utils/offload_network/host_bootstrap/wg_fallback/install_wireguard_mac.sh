#!/bin/bash
# Install + activate WireGuard on the Mac as a spoke of scan-xeon.
# Run AFTER wg-mesh-bootstrap.sh has generated ~/.fleet/wg/conf/mac.conf.
#
# Usage:  utils/offload_network/wg_fallback/install_wireguard_mac.sh

set -euo pipefail

CONF_SRC="$HOME/.fleet/wg/conf/mac.conf"
CONF_DST="/usr/local/etc/wireguard/wg0.conf"

if [ ! -s "$CONF_SRC" ]; then
    echo "missing $CONF_SRC — run wg-mesh-bootstrap.sh first." >&2
    exit 1
fi

# 1. Install wireguard-tools if missing
if ! command -v wg-quick >/dev/null 2>&1; then
    echo "[install] brew install wireguard-tools…"
    brew install wireguard-tools
fi

# 2. Drop the config in place (root-owned, 600)
echo "[install] copying $CONF_SRC -> $CONF_DST (needs sudo)…"
sudo mkdir -p "$(dirname "$CONF_DST")"
sudo install -m 600 -o root -g wheel "$CONF_SRC" "$CONF_DST"

# 3. Bring it up
echo "[install] sudo wg-quick up wg0"
sudo wg-quick up wg0

echo
echo "[install] sudo wg show:"
sudo wg show
echo
echo "Done. /etc/hosts fragment at ~/.fleet/wg/etc_hosts.fragment — append manually:"
echo "  sudo sh -c 'cat ~/.fleet/wg/etc_hosts.fragment >> /etc/hosts'"
echo
echo "Tear down later:  sudo wg-quick down wg0"
