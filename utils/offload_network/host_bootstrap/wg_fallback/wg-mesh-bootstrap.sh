#!/bin/bash
# Generate WireGuard hub-and-spoke configs for the fleet-offload cluster.
# Run on the Mac. Keys + per-host .conf files land in ~/.fleet/wg/  (NOT in the repo).
#
# Topology (chosen because scan-xeon is on the home LAN behind the Fritz!Box):
#
#                     [ cdec_24core    ]
#                     [ scan-amd64-new ]
#                     [ kenne          ]   ◄── all spokes peer with scan-xeon (hub)
#                     [ Mac            ]
#
# After running:
#   ~/.fleet/wg/keys/<host>.{priv,pub}     — per-host keypairs
#   ~/.fleet/wg/conf/<host>.conf           — drop-in wg0.conf for each host
#   ~/.fleet/wg/inventory.json             — IP assignments + hub endpoint
#   ~/.fleet/wg/etc_hosts.fragment         — DNS-equivalent /etc/hosts lines
#
# Activation runbook is in utils/offload_network/wg_fallback/README.md.

set -euo pipefail

WG_DIR="$HOME/.fleet/wg"
KEYS="$WG_DIR/keys"
CONF="$WG_DIR/conf"
SUBNET="10.42.0"
LISTEN_PORT="51820"

# Host map: alias|role|wg_ip   (hub gets .1, spokes are .10+)
read -r -d '' HOSTS <<'EOF' || true
scan-xeon|hub|10.42.0.1
mac|spoke|10.42.0.10
kenne|spoke|10.42.0.11
cdec|spoke|10.42.0.12
scan-new|spoke|10.42.0.13
EOF

# 1. Make sure wg keygen is available on Mac
if ! command -v wg >/dev/null 2>&1; then
    echo "[1/5] installing wireguard-tools via brew (one-time)…"
    brew install wireguard-tools
fi

mkdir -p "$KEYS" "$CONF"
chmod 700 "$WG_DIR"
chmod 700 "$KEYS"

# 2. Generate keypairs (per-host) — idempotent: skip if already present
echo "[2/5] generating keypairs (only if missing)…"
while IFS='|' read -r alias role ip; do
    [ -z "$alias" ] && continue
    p="$KEYS/$alias.priv"
    if [ -s "$p" ]; then
        echo "  $alias: priv exists — keeping"
    else
        wg genkey > "$p"
        chmod 600 "$p"
        wg pubkey < "$p" > "$KEYS/$alias.pub"
        chmod 644 "$KEYS/$alias.pub"
        echo "  $alias: generated"
    fi
done <<< "$HOSTS"

# 3. Hub endpoint — Fritz!Box public IP + port-forwarded UDP 51820 -> scan-xeon
# Try to discover the public IP from the Mac (we share a LAN with scan-xeon).
PUBLIC_IP="${WG_HUB_PUBLIC_IP:-}"
if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org || true)
fi
if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP="REPLACE_WITH_FRITZBOX_PUBLIC_IP"
fi
echo "[3/5] hub endpoint = $PUBLIC_IP:$LISTEN_PORT  (override with WG_HUB_PUBLIC_IP=… ./wg-mesh-bootstrap.sh)"

# 4. Generate per-host config files
echo "[4/5] writing per-host wg0.conf…"
HUB_PRIV=$(cat "$KEYS/scan-xeon.priv")
HUB_PUB=$(cat "$KEYS/scan-xeon.pub")

# Hub config — needs one [Peer] block per spoke
{
    cat <<HUB
# scan-xeon  — WireGuard hub for the fleet-offload cluster
[Interface]
PrivateKey = $HUB_PRIV
Address    = $SUBNET.1/24
ListenPort = $LISTEN_PORT
# Allow forwarding between spokes (required for hub-and-spoke routing).
# Windows: also enable IPEnableRouter (registry tweak in install_wireguard.ps1).
HUB
    while IFS='|' read -r alias role ip; do
        [ "$role" = "hub" ] && continue
        [ -z "$alias" ] && continue
        pub=$(cat "$KEYS/$alias.pub")
        cat <<PEER

[Peer]
# $alias
PublicKey  = $pub
AllowedIPs = $ip/32
PersistentKeepalive = 25
PEER
    done <<< "$HOSTS"
} > "$CONF/scan-xeon.conf"

# Spoke configs — each has scan-xeon as its only peer, routes the whole /24 via hub
while IFS='|' read -r alias role ip; do
    [ "$role" = "hub" ] && continue
    [ -z "$alias" ] && continue
    priv=$(cat "$KEYS/$alias.priv")
    cat > "$CONF/$alias.conf" <<SPK
# $alias — WireGuard spoke (hub = scan-xeon)
[Interface]
PrivateKey = $priv
Address    = $ip/24

[Peer]
# scan-xeon (hub)
PublicKey           = $HUB_PUB
Endpoint            = $PUBLIC_IP:$LISTEN_PORT
AllowedIPs          = $SUBNET.0/24
PersistentKeepalive = 25
SPK
done <<< "$HOSTS"

# 5. Inventory + DNS fragment
INV="$WG_DIR/inventory.json"
HF="$WG_DIR/etc_hosts.fragment"
{
    echo "{"
    echo '  "subnet": "'"$SUBNET.0/24"'",'
    echo '  "hub_endpoint": "'"$PUBLIC_IP:$LISTEN_PORT"'",'
    echo '  "listen_port": '"$LISTEN_PORT"','
    echo '  "hosts": {'
    first=1
    while IFS='|' read -r alias role ip; do
        [ -z "$alias" ] && continue
        [ "$first" = "1" ] || echo ","
        first=0
        printf '    "%s": {"role":"%s","wg_ip":"%s"}' "$alias" "$role" "$ip"
    done <<< "$HOSTS"
    echo
    echo "  }"
    echo "}"
} > "$INV"

{
    echo "# Drop into /etc/hosts on each peer to get hostname resolution"
    while IFS='|' read -r alias role ip; do
        [ -z "$alias" ] && continue
        printf "%-15s %s-wg\n" "$ip" "$alias"
    done <<< "$HOSTS"
} > "$HF"

echo "[5/5] done."
echo
echo "Generated:"
ls -la "$KEYS" "$CONF" 2>&1 | sed 's/^/  /'
echo
echo "Next steps (only when you actually need the WG fallback):"
echo "  1. Fritz!Box admin (fritz.box/#opts): add port-forward rule"
echo "     UDP 51820 -> scan-xeon LAN IP -> 51820"
echo "  2. Verify external IP (if changed): export WG_HUB_PUBLIC_IP=<ip> && bash $0  (regenerates)"
echo "  3. Install on each host using utils/offload_network/wg_fallback/install_*.sh"
echo "     - Mac:  utils/offload_network/wg_fallback/install_wireguard_mac.sh"
echo "     - Win:  copy install_wireguard_windows.ps1 + the host's .conf to the box"
echo "  4. sudo wg show  /  on Windows: 'wg show' from elevated cmd"
echo "  5. Test: from Mac:  ping 10.42.0.11   (kenne via WG)"
