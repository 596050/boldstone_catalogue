"""lib/network.py — prefer direct LAN routes over overlay tunnels.

Background: SSH/rsync invocations resolve host aliases via ``~/.ssh/config``.
The user's config aliases (kenne → scan-amd64-w11) resolve through Tailscale's
MagicDNS to a 100.x.x.x address. Tailscale then transparently routes those
packets — sometimes via a direct LAN path (`direct 192.168.0.121:41641`)
encapsulated in WireGuard, sometimes via a DERP relay.

EVEN WHEN Tailscale picks "direct", every packet still pays:
  - WireGuard encapsulation overhead (~80 bytes per packet)
  - userspace tailscaled forwarding cost
  - extra cryptographic processing on each side

For 60+ GB cohort collects between Mac and a Windows box one switch away,
that overhead is real. This module detects same-LAN reachability and lets
callers prefer the raw LAN IP (e.g. 192.168.0.121:22) so the transport is
plain TCP over the local switch.

DESIGN:
  - Discovery is opportunistic + cached (~/.fleet/network_cache.json, 1h TTL)
  - Detection requires BOTH:
      (a) an RFC1918 / link-local candidate IP (filters out public addresses
          like scan-xeon's 195.244.3.2 that Tailscale also calls "direct")
      (b) an SSH banner response on port 22 (proves the LAN path is open)
  - Output: a per-alias `-o HostName=<lan_ip>` override that callers splice
    into their SSH/rsync command line. The alias's User / IdentityFile / etc
    from ssh_config are preserved; only the destination IP is overridden.

EXTENSIBILITY: this is shaped around Tailscale today but the discovery flow
is overlay-agnostic — `_tailscale_direct_endpoints()` is the only Tailscale-
specific function. Adding ZeroTier / Nebula / Cloudflare Tunnel later would
mean adding sibling probe functions and merging their candidates.
"""
from __future__ import annotations

import json
import pathlib
import re
import socket
import subprocess
import time
from typing import Optional

from fleet.paths import network_cache_path


CACHE_PATH = network_cache_path()
CACHE_TTL_SEC = 3600  # 1 hour — LAN addresses rarely change


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_rfc1918(ip: str) -> bool:
    """True for RFC1918 private ranges + link-local (169.254/16).

    Used to filter out PUBLIC addresses that Tailscale sometimes reports
    as "direct" — those are NOT same-LAN; they're outbound public IPs.
    """
    try:
        parts = [int(x) for x in ip.split(".")]
    except (ValueError, AttributeError):
        return False
    if len(parts) != 4:
        return False
    if any(p < 0 or p > 255 for p in parts):
        return False
    if parts[0] == 10:
        return True
    if parts[0] == 192 and parts[1] == 168:
        return True
    if parts[0] == 172 and 16 <= parts[1] <= 31:
        return True
    if parts[0] == 169 and parts[1] == 254:
        return True
    return False


def _ssh_banner_check(ip: str, port: int = 22, timeout: float = 3.0) -> bool:
    """Probe ip:port for an SSH banner ('SSH-2.0-OpenSSH_...').

    This is what proves the LAN route actually works for SSH — not just
    that the IP is in a private range. A reachable SSH server on the same
    LAN takes ~1-5 ms; a stale/unreachable one fails fast via timeout.
    """
    try:
        with socket.create_connection((ip, port), timeout=timeout) as s:
            s.settimeout(timeout)
            banner = s.recv(64)
            return banner.startswith(b"SSH-")
    except (socket.timeout, ConnectionError, OSError):
        return False


def _resolve_ssh_hostname(alias: str) -> Optional[str]:
    """Use ``ssh -G`` to find what HostName the user's ssh_config maps an
    alias to (e.g. 'kenne' -> 'scan-amd64-w11'). Returns None on failure."""
    try:
        r = subprocess.run(
            ["ssh", "-G", alias],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if line.startswith("hostname "):
            return line.split(None, 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# Overlay-specific discoveries (only Tailscale today; add siblings as needed)
# ---------------------------------------------------------------------------

_DIRECT_ENDPOINT_RE = re.compile(r"\bdirect (\d+\.\d+\.\d+\.\d+):\d+")


def _tailscale_direct_endpoints() -> dict[str, str]:
    """Parse ``tailscale status`` for direct LAN endpoints.

    Each peer line looks like::

        100.89.46.50  scan-amd64-w11  ...  active; direct 192.168.0.121:41641, ...

    The hostname (2nd column) is what the user's MagicDNS / ssh_config
    resolves to. Filter to RFC1918 IPs only — Tailscale also reports
    "direct" for peers reachable via punched public IPs.

    Returns ``{tailscale_hostname -> private_ip}``.
    """
    try:
        r = subprocess.run(
            ["tailscale", "status"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    if r.returncode != 0:
        return {}
    out: dict[str, str] = {}
    for line in r.stdout.splitlines():
        m = _DIRECT_ENDPOINT_RE.search(line)
        if not m:
            continue
        ip = m.group(1)
        if not _is_rfc1918(ip):
            continue
        parts = line.split()
        if len(parts) >= 2:
            out[parts[1]] = ip
    return out


def _discover_candidates(alias: str) -> list[str]:
    """Aggregate candidate LAN IPs for an alias from every known overlay.

    Today: just Tailscale's direct endpoint. When other overlays land
    (ZeroTier, Cloudflare Tunnel, etc.), add their probes here.
    """
    candidates: list[str] = []
    hostname = _resolve_ssh_hostname(alias)
    if hostname:
        ts = _tailscale_direct_endpoints()
        ip = ts.get(hostname)
        if ip:
            candidates.append(ip)
    return candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_lan_addresses(
    aliases: list[str], *, force: bool = False
) -> dict[str, Optional[str]]:
    """For each alias, return its preferred LAN IP (verified SSH-reachable)
    or None if no direct LAN route is detectable.

    Cached at ``CACHE_PATH`` for ``CACHE_TTL_SEC`` seconds. Pass force=True
    to bypass cache and rerun discovery.

    Result is also persisted to the cache so subsequent calls / processes
    pick up the same addresses without re-probing.
    """
    if not force:
        cache = _load_cache()
        if cache and (time.time() - cache.get("timestamp", 0)) < CACHE_TTL_SEC:
            cached = cache.get("addresses", {})
            return {a: cached.get(a) for a in aliases}

    fresh: dict[str, Optional[str]] = {}
    for alias in aliases:
        chosen: Optional[str] = None
        for ip in _discover_candidates(alias):
            if _ssh_banner_check(ip):
                chosen = ip
                break
        fresh[alias] = chosen

    # Merge with prior cache so this call doesn't blow away other hosts'
    # entries. Discovery for alias X SETS x → (ip|None) even on None so
    # subsequent calls don't keep probing a known-unreachable host.
    cache = _load_cache()
    addrs = cache.get("addresses", {})
    addrs.update(fresh)
    _save_cache({"timestamp": time.time(), "addresses": addrs})
    return fresh


def preferred_ssh_options(alias: str, *, prefer_lan: bool = True) -> list[str]:
    """Return SSH command-line options for the alias, preferring LAN if known.

    When a cached LAN address is available and ``prefer_lan=True``, returns
    ``['-o', 'HostName=<lan_ip>']``. Otherwise returns ``[]``.

    Splicing the result into an SSH/rsync command preserves the alias's
    User / IdentityFile / etc from ssh_config — only the destination IP
    is overridden.

    Does NOT trigger discovery; reads cache only. Call ``discover_lan_addresses``
    first if the cache might be empty.
    """
    if not prefer_lan:
        return []
    cache = _load_cache()
    if not cache:
        return []
    addrs = cache.get("addresses", {})
    lan = addrs.get(alias)
    if lan:
        return ["-o", f"HostName={lan}"]
    return []


def cache_snapshot() -> dict:
    """Return the current cache dict (for debugging/inspection)."""
    return _load_cache()


# ---------------------------------------------------------------------------
# Cache IO
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(data: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(CACHE_PATH)
