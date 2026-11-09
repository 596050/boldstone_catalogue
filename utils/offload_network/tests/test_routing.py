"""Tests for config-driven LAN-first SSH routing (lib/routing).

Each host may declare a `lan_host` (directly-routable LAN address) + a
`tailscale_host` (canonical overlay name == ssh-config HostName). When the
LAN address is reachable we route SSH/rsync over it (HostName override +
shared HostKeyAlias); otherwise we fall back to the host's Tailscale name.
"""
from lib import routing


HOSTS = {
    "kenne":     {"ssh_alias": "kenne",
                  "lan_host": "scan-amd64-w11.fritz.box",
                  "tailscale_host": "scan-amd64-w11"},
    "scan-xeon": {"ssh_alias": "scan-xeon",
                  "lan_host": "scan-xeon.fritz.box",
                  "tailscale_host": "scan-xeon"},
    "cdec":      {"ssh_alias": "cdec", "tailscale_host": "cdec-24core"},  # remote, no LAN
    "scan-new":  {"ssh_alias": "scan-new"},                              # no LAN/canonical
}


def setup_function(_):
    routing._cache.clear()


def test_lan_preferred_when_reachable():
    addr, via, canon = routing.resolve_route("kenne", hosts=HOSTS, probe=lambda h: True)
    assert via == "lan"
    assert addr == "scan-amd64-w11.fritz.box"
    assert canon == "scan-amd64-w11"


def test_tailscale_when_lan_unreachable():
    addr, via, canon = routing.resolve_route("kenne", hosts=HOSTS, probe=lambda h: False)
    assert via == "tailscale"
    assert addr is None
    assert canon == "scan-amd64-w11"


def test_tailscale_when_no_lan_host():
    _, via, canon = routing.resolve_route("cdec", hosts=HOSTS, probe=lambda h: True)
    assert via == "tailscale"
    assert canon == "cdec-24core"


def test_unknown_host_is_noop_tailscale():
    addr, via, canon = routing.resolve_route("1.2.3.4", hosts=HOSTS, probe=lambda h: True)
    assert via == "tailscale"
    assert addr is None
    assert canon == "1.2.3.4"


def test_prefer_lan_false_forces_tailscale():
    hosts = dict(HOSTS, kenne=dict(HOSTS["kenne"], prefer_lan=False))
    _, via, _ = routing.resolve_route("kenne", hosts=hosts, probe=lambda h: True)
    assert via == "tailscale"


def test_force_tailscale_env(monkeypatch):
    monkeypatch.setenv("FLEET_FORCE_TAILSCALE", "1")
    routing._cache.clear()
    _, via, _ = routing.resolve_route("kenne", hosts=HOSTS, probe=lambda h: True)
    assert via == "tailscale"


def test_ssh_route_opts_lan():
    opts = routing.ssh_route_opts("scan-xeon", hosts=HOSTS, probe=lambda h: True)
    assert opts == ["-o", "HostName=scan-xeon.fritz.box", "-o", "HostKeyAlias=scan-xeon"]


def test_ssh_route_opts_tailscale_is_empty():
    assert routing.ssh_route_opts("cdec", hosts=HOSTS, probe=lambda h: True) == []


def test_probe_result_cached_within_ttl():
    calls = {"n": 0}

    def probe(h):
        calls["n"] += 1
        return True

    routing.resolve_route("kenne", hosts=HOSTS, probe=probe, now=100.0)
    routing.resolve_route("kenne", hosts=HOSTS, probe=probe, now=200.0)  # < ttl 300
    assert calls["n"] == 1  # second resolve used the cache, did not re-probe


def test_cache_expires_after_ttl():
    calls = {"n": 0}

    def probe(h):
        calls["n"] += 1
        return True

    routing.resolve_route("kenne", hosts=HOSTS, probe=probe, now=100.0)
    routing.resolve_route("kenne", hosts=HOSTS, probe=probe, now=500.0)  # > ttl 300
    assert calls["n"] == 2
