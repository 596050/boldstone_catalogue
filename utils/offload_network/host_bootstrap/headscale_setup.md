# Headscale — self-hosted, open-source Tailscale control plane

**What it is.** [Headscale](https://github.com/juanfont/headscale) is an
open-source reimplementation of Tailscale's *coordination server* (the only
part Tailscale hosts for you). You keep the **official `tailscale` clients** on
every host — they just register with **your** server instead of
`login.tailscale.com`. The WireGuard data plane is unchanged (still
peer-to-peer, LAN-direct when peers share a network, DERP relays for NAT
traversal). MagicDNS, ACLs, and subnet routes all still work.

**Why for this fleet.** It removes the dependency on Tailscale's hosted control
plane while keeping the exact client UX. It pairs with the LAN-first routing
already shipped (`lib/routing.py`): local hosts (kenne, scan-xeon) stay
LAN-direct; the overlay is the **backup** path and the only path for the
genuinely-remote host (cdec).

> This is the heavier OSS option. For a small fixed fleet the pre-staged
> **WireGuard** mesh (`wg_fallback/`) is simpler. Use Headscale if you want
> Tailscale's niceties (MagicDNS, ACLs, easy enrollment) minus the SaaS.

---

## Topology

```
        [ Headscale control server ]  (VPS w/ public DNS+TLS, or Mac+Fritz!Box forward)
                     ▲  https://headscale.example.com   (clients register here)
                     │
   ┌─────────────────┼───────────────────────────────┐
   │                 │                                │
 [ Mac ]        [ kenne / scan-xeon ]            [ cdec (remote) ]
 overlay+LAN    overlay+LAN-direct               overlay via DERP
```
Data plane is direct WireGuard between peers; the control server only does
key exchange + coordination (it is NOT in the data path).

---

## Recipe

### 1. Provision the control server
Pick ONE:
- **Cheap VPS (recommended):** stable public IP + a DNS name + Let's Encrypt TLS. ~$4/mo.
- **Mac mini + Fritz!Box:** forward TCP 443 (or 8080) to the Mac; use a DDNS name. Works but ties the control plane to your home uplink.

You need: a hostname (e.g. `headscale.example.com`) resolvable from every host, and TLS on it.

### 2. Install Headscale (on the control server)

**Docker (simplest):**
```bash
sudo mkdir -p /etc/headscale /var/lib/headscale
# grab the example config for your version:
docker run --rm headscale/headscale:latest cat /etc/headscale/config.yaml | \
  sudo tee /etc/headscale/config.yaml >/dev/null
# edit config.yaml (see step 3), then run it:
docker run -d --name headscale --restart unless-stopped \
  -v /etc/headscale:/etc/headscale -v /var/lib/headscale:/var/lib/headscale \
  -p 443:8080 \
  headscale/headscale:latest serve
```

**Bare binary (Linux/amd64):**
```bash
V=$(curl -s https://api.github.com/repos/juanfont/headscale/releases/latest | grep -o '"tag_name":"[^"]*' | cut -d'"' -f4)
sudo curl -fsSL -o /usr/local/bin/headscale \
  "https://github.com/juanfont/headscale/releases/download/${V}/headscale_${V#v}_linux_amd64"
sudo chmod +x /usr/local/bin/headscale
sudo mkdir -p /etc/headscale /var/lib/headscale
# install the systemd unit + example config from the release, edit config, then:
sudo systemctl enable --now headscale
```

### 3. Configure `/etc/headscale/config.yaml`
The schema evolves between versions — start from the shipped example and set:
```yaml
server_url: https://headscale.example.com         # the public URL clients hit
listen_addr: 0.0.0.0:8080
prefixes:
  v4: 100.64.0.0/10                                # tailnet IP range
dns:
  magic_dns: true
  base_domain: fleet.internal                      # -> kenne.fleet.internal, etc.
  nameservers:
    global: [1.1.1.1, 8.8.8.8]
database:
  type: sqlite
  sqlite:
    path: /var/lib/headscale/db.sqlite
# TLS: either let Headscale do ACME...
tls_letsencrypt_hostname: headscale.example.com
tls_letsencrypt_challenge_type: HTTP-01
# ...or terminate TLS at Caddy/nginx and proxy to 127.0.0.1:8080 instead.
```

### 4. Create a user + a reusable pre-auth key (for unattended enrollment)
```bash
headscale users create fleet
headscale preauthkeys create --user fleet --reusable --expiration 720h
#  -> prints: <PREAUTHKEY>   (use it to enroll every host hands-free)
```
(In a Docker install prefix with `docker exec headscale `.)

### 5. Point each host's tailscale client at Headscale
The whole trick is `--login-server`. Same client, your control plane.

- **Mac / Linux:**
  ```bash
  tailscale up --login-server https://headscale.example.com --authkey <PREAUTHKEY>
  ```
- **Windows fleet host (elevated PowerShell):**
  ```powershell
  tailscale up --login-server https://headscale.example.com --authkey <PREAUTHKEY> --unattended
  ```
  (`--unattended` keeps the tunnel up across logoff/reboot — required for headless boxes.)

### 6. Verify
```bash
headscale nodes list        # all enrolled hosts + their 100.64.x overlay IPs
# on any host:
tailscale status            # should list the other fleet hosts
tailscale ping kenne        # WireGuard data-plane reachability
```

### 7. (Optional) ACLs + your own DERP
- **ACLs** (same syntax as Tailscale): `headscale policy set -f acl.hujson`.
- **DERP for NAT'd remotes (cdec):** either keep Tailscale's public DERP map
  (`derp.urls: ["https://controlplane.tailscale.com/derpmap/default"]` in
  config) or run your own `derper` binary and point `derp.paths`/`derp.urls`
  at it. LAN + most peers connect directly and never touch DERP.

---

## Wiring it into this repo

Once a host is on Headscale, its overlay name becomes `*.<base_domain>`
(e.g. `kenne.fleet.internal`). Update routing so the **backup** path uses
Headscale instead of hosted Tailscale:

1. In `~/.ssh/config`, point each host's `HostName` at the Headscale MagicDNS
   name (or its 100.64.x IP), e.g. `Host kenne … HostName kenne.fleet.internal`.
2. In `utils/offload_network/hosts.json`, set each host's
   `tailscale_host` to that same name (it is the canonical host-key name used
   by `lib/routing.py`'s LAN-first override).
3. Leave `lan_host` as-is — LAN stays primary; Headscale is the fallback.

`FLEET_FORCE_TAILSCALE=1` still forces the overlay path for debugging.

## Zero-downtime migration off hosted Tailscale
1. Stand up Headscale; enroll **one** test host and confirm `headscale nodes
   list` + SSH over it.
2. Migrate hosts one at a time (`tailscale up --login-server …`), verifying SSH
   after each — the fleet keeps running because LAN-direct is unaffected.
3. Update `hosts.json` `tailscale_host` + `~/.ssh/config` HostNames.
4. Decommission the hosted tailnet.
