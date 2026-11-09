# wg_fallback — WireGuard hub-and-spoke fallback

**Status: PRE-STAGED, NOT ACTIVE.** Tailscale is our current overlay. The
WireGuard package + per-host config files are already installed on every host,
but no tunnel service is running. Activation = one command per host + one
Fritz!Box port-forward rule (manual). Expected switchover time: ~5 minutes.

Each host has:
- WireGuard for Windows installed (winget) — kenne, scan-xeon, cdec
- wireguard-tools installed (brew) — Mac
- Per-host `wg0.conf` staged at `~/Downloads/fleet-offload/wg0.conf` (Windows)
  or `~/.fleet/wg/conf/mac.conf` (Mac)
- Tunnel service NOT installed (no `/installtunnelservice` call yet)

## Topology

```
                   [ cdec_24core    ]
                   [ scan-amd64-new ]   spokes — peer with scan-xeon only
                   [ kenne          ]
                   [ Mac            ]
                        │
                        ▼
              [ scan-xeon — hub @ 10.42.0.1 ]
              listens UDP 51820 on Fritz!Box public IP
              forwards 10.42.0.0/24 between spokes
```

| Host | WG IP | Role |
|---|---|---|
| scan-xeon | 10.42.0.1 | hub |
| Mac | 10.42.0.10 | spoke |
| kenne | 10.42.0.11 | spoke |
| cdec | 10.42.0.12 | spoke |
| scan-new | 10.42.0.13 | spoke |

## Files in this directory

| File | What it does |
|---|---|
| `wg-mesh-bootstrap.sh` | **Run on Mac.** Generates 5 Curve25519 keypairs + 5 `.conf` files under `~/.fleet/wg/` (outside the repo — keys never get committed). Idempotent. |
| `install_wireguard_mac.sh` | **Run on Mac AFTER bootstrap.** brew-installs wireguard-tools, copies `~/.fleet/wg/conf/mac.conf` to `/usr/local/etc/wireguard/wg0.conf`, brings tunnel up. |
| `install_wireguard_windows.ps1` | **Paste on each Windows host (elevated PowerShell).** winget-installs WireGuard, registers the tunnel as an auto-start service. Hub also gets `IPEnableRouter=1`. |

## Pre-stage (already done 2026-06-02)

What's already on every host:
- WireGuard package installed (winget) on kenne, scan-xeon, cdec
- wireguard-tools brew package on Mac
- Per-host `wg0.conf` staged at canonical paths:
  - kenne:     `C:\Users\Kenneth\Downloads\fleet-offload\wg0.conf`
  - scan-xeon: `C:\Users\Kenneth\Downloads\fleet-offload\wg0.conf`
  - cdec:      `C:\Users\kenne\Downloads\fleet-offload\wg0.conf`
  - Mac:       `~/.fleet/wg/conf/mac.conf`
- Keys + inventory on Mac at `~/.fleet/wg/`

## Activation runbook (when you actually need to switch)

### 1. Open the port on the Fritz!Box (one-time, manual)

You have to do this in the Fritz!Box web admin (`fritz.box`):

- Internet → Permit Access → Port Sharing → New Port Sharing
- Protocol: UDP, External port: 51820, Internal IP: scan-xeon LAN IP, Internal port: 51820
- Save.

Verify from another network: `nc -u -zv <fritzbox-public-ip> 51820` (should connect).

### 2. Activate the hub first (scan-xeon)

```bash
ssh scan-xeon '& "C:\Program Files\WireGuard\wireguard.exe" /installtunnelservice C:\Users\Kenneth\Downloads\fleet-offload\wg0.conf'
```

Confirm: `ssh scan-xeon '& "C:\Program Files\WireGuard\wg.exe" show'`

### 3. Activate each spoke

```bash
ssh kenne     '& "C:\Program Files\WireGuard\wireguard.exe" /installtunnelservice C:\Users\Kenneth\Downloads\fleet-offload\wg0.conf'
ssh cdec      '& "C:\Program Files\WireGuard\wireguard.exe" /installtunnelservice C:\Users\kenne\Downloads\fleet-offload\wg0.conf'
# Mac:
utils/offload_network/wg_fallback/install_wireguard_mac.sh
```

### 4. Test connectivity

```bash
ping 10.42.0.1                # scan-xeon (hub)
ping 10.42.0.11               # kenne
ping 10.42.0.12               # cdec
ssh kenne@10.42.0.11 hostname
```

### 5. Update `~/.ssh/config` to use WG addresses

Append `~/.fleet/wg/etc_hosts.fragment` to `/etc/hosts` so the `-wg` aliases work:
```bash
sudo sh -c 'cat ~/.fleet/wg/etc_hosts.fragment >> /etc/hosts'
```

Then update the relevant `Host` blocks (or add `Host kenne-wg` variants pointing
at `10.42.0.11`).

### 6. Update `utils/offload_network/hosts.json`

For every host, change `ssh_alias` to the `-wg` variant. Fleet then routes
through WireGuard instead of Tailscale.

## Re-bootstrap (if the public IP changes or you want to rotate keys)

```bash
WG_HUB_PUBLIC_IP=<new-ip> \
    utils/offload_network/wg_fallback/wg-mesh-bootstrap.sh
# Re-push only the spoke configs:
for h in kenne scan-xeon cdec; do
    case $h in
      kenne|scan-xeon) home='C:/Users/Kenneth' ;;
      cdec)            home='C:/Users/kenne'   ;;
    esac
    scp ~/.fleet/wg/conf/$h.conf $h:$home/Downloads/fleet-offload/wg0.conf
done
```

## Tear-down (back to Tailscale)

```bash
# Mac
sudo wg-quick down wg0

# Each Windows host (elevated PowerShell)
& "C:\Program Files\WireGuard\wireguard.exe" /uninstalltunnelservice wg0
```

Remove the Fritz!Box port-forward rule. Revert `hosts.json` ssh aliases.

## Why we didn't activate this now

Tailscale free tier covers 100 personal devices — we have 5. We won't run out
on the device count. The free tier could change pricing model in the future
(Tailscale has been raising prices on commercial tiers), so this fallback is
worth having pre-built. Switching takes ~30 minutes when it's needed.

## Caveats

- **Hub is a single point of failure.** If scan-xeon is down, all inter-host
  WG traffic stops. Mac's direct LAN access to kenne would still work; Tailscale
  has DERP relays to route around this.
- **Public IP must be stable** or use DDNS. If your home IP changes, regenerate
  with `WG_HUB_PUBLIC_IP=…` and re-push spoke configs.
- **No MagicDNS** — `~/.fleet/wg/etc_hosts.fragment` is the manual equivalent.
  Apply it to each host that should resolve names.
- **No automatic key rotation.** Re-run the bootstrap manually to rotate; you'd
  need to re-push every spoke's conf afterwards.
- **No SSH ACLs.** WireGuard is transport-level; sshd's authorized_keys still
  controls access.
