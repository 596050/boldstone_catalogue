"""Config-driven LAN-first SSH routing for the fleet (Tailscale as backup).

The fleet reaches Windows hosts over SSH. Hosts that share the Mac's local
network (e.g. kenne / scan-xeon on 192.168.0.x) are faster and dependency-free
to reach LAN-direct; genuinely-remote hosts (e.g. cdec, behind a DERP relay)
must go over the Tailscale overlay. This module makes that choice **per host,
from hosts.json**, so every fleet tool (lib.remote, the v2 transport, fleet.py)
routes the same way.

hosts.json schema (per ssh host):

    "kenne": {
      "ssh_alias": "kenne",                         # ~/.ssh/config alias (user + key)
      "lan_host":  "scan-amd64-w11.fritz.box",      # primary: directly-routable LAN addr
      "tailscale_host": "scan-amd64-w11",           # backup/canonical: the ssh-config HostName
      "prefer_lan": true                            # optional, default true
    }

Resolution (cached per alias for `cache_ttl` s so we don't probe every call):
  - If `lan_host` is set, `prefer_lan` is true, and a quick TCP probe of
    `lan_host:22` succeeds  -> route over LAN: inject
    `-o HostName=<lan_host> -o HostKeyAlias=<tailscale_host>` (the HostKeyAlias
    keeps host-key verification under the same known_hosts entry both paths
    share, so no prompt/mismatch).
  - Otherwise -> use the alias's configured (Tailscale) HostName as-is (no opts).

A host with no `lan_host` (cdec, scan-new) always uses Tailscale — so being
off-LAN, or a host being genuinely remote, falls back automatically. Set
`FLEET_FORCE_TAILSCALE=1` to disable LAN routing globally.
"""
from __future__ import annotations

import json
import os
import pathlib
import socket
import time
from typing import Callable, Optional

from .inventory import hosts_path
_HOSTS_JSON = hosts_path()
_DEFAULT_TTL = 300.0
_PROBE_PORT = 22
_PROBE_TIMEOUT = 1.5

# alias -> ((address, via, canonical), expiry_monotonic)
_cache: dict[str, tuple] = {}


def _load_hosts() -> dict:
    try:
        return json.loads(_HOSTS_JSON.read_text()).get("hosts", {}) or {}
    except Exception:
        return {}


def _tcp_open(host: str, port: int = _PROBE_PORT, timeout: float = _PROBE_TIMEOUT) -> bool:
    """True if a TCP connection to host:port succeeds within `timeout`."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _force_tailscale() -> bool:
    return os.environ.get("FLEET_FORCE_TAILSCALE", "").strip().lower() in ("1", "true", "yes")


def resolve_route(
    alias: str,
    *,
    hosts: Optional[dict] = None,
    probe: Callable[[str], bool] = _tcp_open,
    ttl: float = _DEFAULT_TTL,
    now: Optional[float] = None,
) -> tuple:
    """Resolve how to reach `alias`. Returns ``(address, via, canonical)``:

      via == "lan"        -> `address` is the LAN host to route to (HostName override)
      via == "tailscale"  -> `address` is None; use the alias's configured HostName

    `canonical` is the stable host-key name (the tailscale_host, else the alias).
    The probe result is cached per alias for `ttl` seconds.
    """
    if _force_tailscale():
        return (None, "tailscale", alias)
    now = time.monotonic() if now is None else now
    hit = _cache.get(alias)
    if hit and hit[1] > now:
        return hit[0]

    cfg = (hosts if hosts is not None else _load_hosts()).get(alias, {}) or {}
    lan = cfg.get("lan_host")
    canonical = cfg.get("tailscale_host") or alias
    prefer = cfg.get("prefer_lan", True)

    if lan and prefer and probe(lan):
        result = (lan, "lan", canonical)
    else:
        result = (None, "tailscale", canonical)

    _cache[alias] = (result, now + ttl)
    return result


def ssh_route_opts(alias: str, **kw) -> list:
    """SSH ``-o`` options to route `alias` LAN-first. Returns a HostName
    override + a shared HostKeyAlias when LAN is preferred & reachable, else
    ``[]`` (use the alias's configured Tailscale HostName unchanged)."""
    addr, via, canonical = resolve_route(alias, **kw)
    if via == "lan" and addr:
        return ["-o", f"HostName={addr}", "-o", f"HostKeyAlias={canonical}"]
    return []


def route_label(alias: str, **kw) -> str:
    """'lan' or 'tailscale' — for diagnostics / status output."""
    return resolve_route(alias, **kw)[1]


def clear_cache() -> None:
    _cache.clear()
