#!/usr/bin/env python3
"""
Concurrent VPN tunnel manager — runs multiple OpenVPN connections simultaneously.

Each tunnel gets its own tun device (tun10, tun11, ...) with --route-nopull so
tunnels don't fight over the default route.  Callers route traffic through a
specific tunnel by using a requests.Session bound to that tunnel's local IP.

Library usage:

    from utils.networking.vpn_concurrent import ConcurrentVPN

    with ConcurrentVPN(num_tunnels=3) as vpn:
        tunnels = vpn.connect_all()
        session = vpn.get_session(0)          # session bound to tunnel 0
        r = session.get("https://httpbin.org/ip")
        print(r.json())
        vpn.rotate_tunnel(0, reason="blocked")

CLI usage:

    python -m utils.networking.vpn_concurrent connect   --num-tunnels 3
    python -m utils.networking.vpn_concurrent status
    python -m utils.networking.vpn_concurrent disconnect
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import platform
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import socket
import socketserver
import struct

import requests
import requests.adapters
import urllib3

from utils.networking.vpn import (
    DEFAULT_AUTH_FILE,
    DEFAULT_CONFIGS_DIR,
    OPENVPN_BIN,
    get_ip_country,
    get_public_ip,
    start_sudo_keepalive,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TUN_OFFSET = 10  # tun10, tun11, ... to avoid conflicts with system tun0
IS_MACOS = platform.system() == "Darwin"


def _sudo_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a sudo command non-interactively — never blocks for password.

    Injects ``-n`` (non-interactive) into the sudo invocation so it
    returns immediately with exit-code 1 when the ticket has expired,
    instead of hanging while waiting for a password on ``/dev/tty``.
    """
    # Insert -n after "sudo" if not already present
    if cmd and cmd[0] == "sudo" and "-n" not in cmd:
        cmd = [cmd[0], "-n"] + cmd[1:]
    kwargs.setdefault("capture_output", True)
    return subprocess.run(cmd, **kwargs)


# ---------------------------------------------------------------------------
# Tunnel dataclass
# ---------------------------------------------------------------------------

@dataclass
class Tunnel:
    """Represents a single OpenVPN tunnel."""

    tunnel_id: int
    tun_device: str  # e.g. "tun10"
    config: Path | None = None
    server: str | None = None
    ip: str | None = None  # public IP through this tunnel
    local_ip: str | None = None  # IP assigned to the tun device
    pid: int | None = None
    connected: bool = False
    socks_port: int = 0  # local SOCKS5 proxy port (0 = not running)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _socks_server: Any = field(default=None, repr=False)

    @property
    def socks_proxy_url(self) -> str | None:
        """SOCKS5 proxy URL for Playwright/requests, or None if not running."""
        if self.socks_port and self.connected:
            return f"socks5://127.0.0.1:{self.socks_port}"
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tunnel_id": self.tunnel_id,
            "tun_device": self.tun_device,
            "config": str(self.config) if self.config else None,
            "server": self.server,
            "ip": self.ip,
            "local_ip": self.local_ip,
            "pid": self.pid,
            "connected": self.connected,
            "socks_port": self.socks_port,
            "socks_proxy": self.socks_proxy_url,
        }


# ---------------------------------------------------------------------------
# Bound HTTP adapter — routes requests through a specific source address
# ---------------------------------------------------------------------------

class BoundHTTPAdapter(requests.adapters.HTTPAdapter):
    """HTTPAdapter that binds outgoing connections to a specific source address."""

    def __init__(self, source_address: tuple[str, int], **kwargs: Any) -> None:
        self._source_address = source_address
        super().__init__(**kwargs)

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["source_address"] = self._source_address
        super().init_poolmanager(*args, **kwargs)


# ---------------------------------------------------------------------------
# Minimal SOCKS5 proxy — binds outgoing connections to a specific source IP
# ---------------------------------------------------------------------------
# This allows Playwright (Chromium) to route traffic through a specific VPN
# tunnel by connecting to a local SOCKS5 proxy on 127.0.0.1:<port>.

SOCKS5_BASE_PORT = 10800  # tunnel 0 -> 10800, tunnel 1 -> 10801, ...


class _Socks5Handler(socketserver.BaseRequestHandler):
    """Handle one SOCKS5 connection, routing outgoing through the tunnel."""

    def handle(self) -> None:
        client = self.request
        client.settimeout(60)
        try:
            self._do_socks5(client)
        except (OSError, struct.error, IndexError, TimeoutError):
            pass
        finally:
            client.close()

    def _do_socks5(self, client: socket.socket) -> None:
        # Greeting
        data = client.recv(256)
        if len(data) < 3 or data[0] != 0x05:
            return
        # No-auth reply
        client.sendall(b"\x05\x00")

        # Request
        data = client.recv(256)
        if len(data) < 7 or data[0] != 0x05 or data[1] != 0x01:
            client.sendall(b"\x05\x07\x00\x01" + b"\x00" * 6)
            return

        atyp = data[3]
        if atyp == 0x01:  # IPv4
            dst_addr = socket.inet_ntoa(data[4:8])
            dst_port = struct.unpack("!H", data[8:10])[0]
        elif atyp == 0x03:  # Domain
            dlen = data[4]
            dst_addr = data[5:5 + dlen].decode("ascii", errors="replace")
            dst_port = struct.unpack("!H", data[5 + dlen:7 + dlen])[0]
        elif atyp == 0x04:  # IPv6
            dst_addr = socket.inet_ntop(socket.AF_INET6, data[4:20])
            dst_port = struct.unpack("!H", data[20:22])[0]
        else:
            client.sendall(b"\x05\x08\x00\x01" + b"\x00" * 6)
            return

        # Connect to destination through the tunnel interface
        try:
            remote = self._connect_via_tunnel(dst_addr, dst_port)
        except OSError:
            client.sendall(b"\x05\x05\x00\x01" + b"\x00" * 6)
            return

        # Success reply
        bind_addr = remote.getsockname()
        reply = b"\x05\x00\x00\x01"
        reply += socket.inet_aton(bind_addr[0])
        reply += struct.pack("!H", bind_addr[1])
        client.sendall(reply)

        # Relay data
        self._relay(client, remote)

    def _connect_via_tunnel(self, dst_addr: str, dst_port: int) -> socket.socket:
        """Connect to destination, forcing traffic through the VPN tunnel.

        On macOS, uses IP_BOUND_IF to bind the socket to the utun interface
        (source-IP binding alone doesn't route through utun on macOS).
        On Linux, uses source-IP binding (works with policy routing).
        """
        # Resolve hostname if needed
        addr_infos = socket.getaddrinfo(dst_addr, dst_port, socket.AF_INET,
                                         socket.SOCK_STREAM)
        if not addr_infos:
            raise OSError(f"Could not resolve {dst_addr}")

        last_err = None
        for family, socktype, proto, canonname, sockaddr in addr_infos:
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(30)

                if IS_MACOS and hasattr(self.server, 'tun_device') and self.server.tun_device:
                    # macOS: use IP_BOUND_IF to force traffic through the
                    # utun interface, combined with source-IP binding so the
                    # VPN server recognises the traffic.
                    IP_BOUND_IF = 25  # from <netinet/in.h> on macOS
                    try:
                        ifindex = socket.if_nametoindex(self.server.tun_device)
                        sock.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF, ifindex)
                    except (OSError, ValueError):
                        pass
                    sock.bind((self.server.bind_ip, 0))
                else:
                    # Linux: source-IP binding works with policy routing
                    sock.bind((self.server.bind_ip, 0))

                sock.connect(sockaddr)
                return sock
            except OSError as e:
                last_err = e
                try:
                    sock.close()
                except Exception:
                    pass
                continue

        raise last_err or OSError(f"Failed to connect to {dst_addr}:{dst_port}")

    @staticmethod
    def _relay(client: socket.socket, remote: socket.socket) -> None:
        import select
        sockets = [client, remote]
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets, 60)
            if exceptional:
                break
            for sock in readable:
                data = sock.recv(65536)
                if not data:
                    return
                if sock is client:
                    remote.sendall(data)
                else:
                    client.sendall(data)


class _Socks5Server(socketserver.ThreadingTCPServer):
    """Threaded SOCKS5 server that routes outgoing connections through a tunnel."""
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, port: int, bind_ip: str, tun_device: str = "") -> None:
        self.bind_ip = bind_ip
        self.tun_device = tun_device
        super().__init__(("127.0.0.1", port), _Socks5Handler)


# ---------------------------------------------------------------------------
# Helper: get local IP assigned to a tun device
# ---------------------------------------------------------------------------

def _get_tun_local_ip(tun_device: str) -> str | None:
    """Read the local (source) IP assigned to a tun device.

    On macOS: parses ``ifconfig tunN``.
    On Linux: parses ``ip addr show tunN``.
    """
    try:
        if IS_MACOS:
            result = subprocess.run(
                ["ifconfig", tun_device],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
            # Look for inet lines:  inet 10.8.8.5 --> 10.8.8.1 netmask ...
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
        else:
            result = subprocess.run(
                ["ip", "addr", "show", tun_device],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
            # Look for: inet 10.8.8.5/24 ...
            match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _get_public_ip_via_socks(socks_port: int) -> str | None:
    """Get the public IP via a local SOCKS5 proxy (reliable on macOS)."""
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    proxy_url = f"socks5h://127.0.0.1:{socks_port}"
    for svc in services:
        try:
            resp = requests.get(
                svc,
                proxies={"https": proxy_url, "http": proxy_url},
                timeout=10,
            )
            ip = resp.text.strip()
            if ip and ip.count(".") == 3:
                return ip
        except Exception:
            continue
    return None


def _get_public_ip_via_interface(tun_device: str) -> str | None:
    """Get the public IP visible through a specific tun device using curl --interface."""
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    for svc in services:
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "8", "--interface", tun_device, svc],
                capture_output=True, text=True, timeout=15,
            )
            ip = result.stdout.strip()
            if ip and ip.count(".") == 3:
                return ip
        except (subprocess.TimeoutExpired, OSError):
            continue
    return None


# ---------------------------------------------------------------------------
# ConcurrentVPN
# ---------------------------------------------------------------------------

class ConcurrentVPN:
    """Manages N simultaneous OpenVPN tunnels, each on its own tun device.

    Each tunnel connects with ``--route-nopull`` so it does not take over the
    default route.  Callers use :meth:`get_session` to obtain a
    ``requests.Session`` that is bound to a specific tunnel's local IP.

    Parameters
    ----------
    num_tunnels : int
        Number of simultaneous VPN tunnels to maintain.
    configs_dir : Path
        Directory containing .ovpn configuration files.
    auth_file : Path
        OpenVPN auth-user-pass file.
    log_file : Path | None
        Optional JSON file for logging IP events.
    country : str | None
        Prefer servers from this 2-letter country code.
    verbose : bool
        Print status messages to stdout.
    """

    def __init__(
        self,
        num_tunnels: int = 3,
        configs_dir: str | Path = DEFAULT_CONFIGS_DIR,
        auth_file: str | Path = DEFAULT_AUTH_FILE,
        log_file: str | Path | None = None,
        country: str | None = None,
        verbose: bool = True,
        tun_offset: int = 0,
        daemon_prefix: str = "openvpn-concurrent",
    ) -> None:
        self.num_tunnels = num_tunnels
        self.configs_dir = Path(configs_dir)
        self.auth_file = Path(auth_file)
        self.log_file = Path(log_file) if log_file else None
        self.country = country.lower() if country else None
        self.verbose = verbose
        self.tun_offset = tun_offset
        self.daemon_prefix = daemon_prefix

        self._tmpdir = Path(tempfile.mkdtemp(prefix="vpn_concurrent_"))
        self._used_configs: set[str] = set()
        self._tunnels: list[Tunnel] = []
        self._sessions: dict[int, requests.Session] = {}
        self._setup_done = False
        # Counter for generating unique tun device names on reconnection.
        # macOS can't reuse a tun device name after the previous openvpn
        # process died — "Error: problem with tun vs. tap setting".
        self._tun_generation = 0

        # Detect tun devices and SOCKS ports already in use by other scripts
        occupied_tuns = self._detect_occupied_tuns()
        occupied_ports = self._detect_occupied_ports()

        # Create tunnel objects, skipping occupied tun devices
        # tun_offset shifts device numbering so multiple scripts can run
        # without overlapping: script A uses tun_offset=0 (tun10,11,12),
        # script B uses tun_offset=3 (tun13,14,15).
        for i in range(num_tunnels):
            tun_num = TUN_OFFSET + tun_offset + i
            tun_name = f"tun{tun_num}"
            if tun_name in occupied_tuns:
                self._log(f"WARNING: {tun_name} already in use by another "
                          f"process — shifting to avoid conflict")
                # Find next free tun device
                while tun_name in occupied_tuns:
                    tun_num += 1
                    tun_name = f"tun{tun_num}"
                occupied_tuns.add(tun_name)  # reserve it
            socks_port = SOCKS5_BASE_PORT + tun_offset + i
            if socks_port in occupied_ports:
                self._log(f"WARNING: SOCKS port {socks_port} already in use "
                          f"— shifting to avoid conflict")
                while socks_port in occupied_ports:
                    socks_port += 1
                occupied_ports.add(socks_port)
            self._tunnels.append(
                Tunnel(
                    tunnel_id=i,
                    tun_device=tun_name,
                    socks_port=0,  # assigned during _start_socks_proxy
                )
            )

    def _detect_occupied_tuns(self) -> set[str]:
        """Find tun/utun devices currently in use by other OpenVPN processes."""
        occupied: set[str] = set()
        try:
            result = _sudo_run(
                ["sudo", "ps", "-eo", "args"], text=True, timeout=5,
            )
            if result.returncode != 0:
                return occupied
            for line in result.stdout.splitlines():
                line = line.strip()
                # Only look at openvpn processes NOT owned by this script
                if "openvpn" not in line or self.daemon_prefix in line:
                    continue
                # Extract --dev tunN
                idx = line.find("--dev ")
                if idx >= 0:
                    dev = line[idx + 6:].split()[0]
                    occupied.add(dev)
        except Exception:
            pass
        if occupied:
            self._log(f"Detected occupied tun devices: {sorted(occupied)}")
        return occupied

    def _detect_occupied_ports(self) -> set[int]:
        """Find SOCKS5 ports already bound in the 108xx range."""
        occupied: set[int] = set()
        try:
            result = subprocess.run(
                ["lsof", "-iTCP:10800-10899", "-sTCP:LISTEN", "-P", "-n"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines()[1:]:  # skip header
                parts = line.split()
                for part in parts:
                    if ":108" in part:
                        port_str = part.split(":")[-1]
                        try:
                            occupied.add(int(port_str))
                        except ValueError:
                            pass
        except Exception:
            pass
        if occupied:
            self._log(f"Detected occupied SOCKS ports: {sorted(occupied)}")
        return occupied

    # -- Context manager -----------------------------------------------------

    def __enter__(self) -> ConcurrentVPN:
        self._preflight()
        self._install_signal_handlers()
        atexit.register(self._atexit_cleanup)
        self._setup_done = True
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.disconnect_all()
        self._cleanup_tmpdir()
        return False

    # -- Public API ----------------------------------------------------------

    def _kill_stale_openvpn(self) -> None:
        """Kill orphaned openvpn daemons whose tmpdir no longer exists.

        Each ConcurrentVPN instance writes pid files to a unique tmpdir.
        If that tmpdir is gone, the parent process died without cleanup
        and the openvpn process is orphaned.  Active scripts' tunnels
        are left alone.

        Only matches daemons with this instance's daemon_prefix — never
        kills tunnels owned by other scripts.
        """
        try:
            result = _sudo_run(
                ["sudo", "ps", "-eo", "pid,args"],
                text=True, timeout=5,
            )
            if result.returncode != 0:
                return
            killed = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if self.daemon_prefix not in line:
                    continue
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                pid_str, args = parts
                # Extract the --writepid path to find the tmpdir
                idx = args.find("--writepid ")
                if idx < 0:
                    continue
                pid_path = args[idx + len("--writepid "):].split()[0]
                tmpdir = os.path.dirname(pid_path)
                # If the tmpdir still exists, a live script owns this process
                if os.path.isdir(tmpdir):
                    continue
                # Orphaned — kill it
                pid = int(pid_str)
                killed.append(pid)
                try:
                    _sudo_run(["sudo", "kill", str(pid)])
                except Exception:
                    pass
            if killed:
                self._log(f"Killed {len(killed)} orphaned openvpn process(es): {killed}")
                time.sleep(1)
                for pid in killed:
                    try:
                        os.kill(pid, 0)
                        _sudo_run(["sudo", "kill", "-9", str(pid)])
                    except (ProcessLookupError, PermissionError):
                        pass
        except Exception:
            pass

    def connect_all(self) -> list[Tunnel]:
        """Connect all N tunnels to different servers in parallel.

        Returns the list of Tunnel objects.  Some may have ``connected=False``
        if they failed; a warning is logged for each failure.
        """
        self._kill_stale_openvpn()
        configs = self._pick_configs(self.num_tunnels)

        def _connect_one(tunnel: Tunnel, config: Path) -> Tunnel:
            self._connect_tunnel(tunnel, config)
            return tunnel

        with ThreadPoolExecutor(max_workers=self.num_tunnels) as pool:
            futures = {
                pool.submit(_connect_one, t, c): t
                for t, c in zip(self._tunnels, configs)
            }
            for future in as_completed(futures):
                tunnel = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    self._log(f"Tunnel {tunnel.tunnel_id} ({tunnel.tun_device}) "
                              f"failed: {exc}")

        connected = [t for t in self._tunnels if t.connected]
        failed = [t for t in self._tunnels if not t.connected]

        # Keep sudo alive so rotations don't fail with password prompts
        if connected:
            start_sudo_keepalive()

        # Start SOCKS5 proxies for connected tunnels (skip if already started)
        for t in connected:
            if not t.socks_port:
                self._start_socks_proxy(t)

        self._log(
            f"{len(connected)}/{self.num_tunnels} tunnels connected"
            + (f" ({len(failed)} failed)" if failed else "")
        )
        for t in connected:
            socks_info = f", socks5://127.0.0.1:{t.socks_port}" if t.socks_port else ""
            self._log(f"  tunnel {t.tunnel_id}: {t.tun_device} -> "
                      f"{t.ip} ({t.server}{socks_info})")
        return list(self._tunnels)

    def get_tunnel(self, slot: int) -> Tunnel | None:
        """Get the Tunnel for a given slot (wraps if slot >= num_tunnels).

        Returns None if the tunnel at that slot is not connected.
        """
        tunnel = self._tunnels[slot % self.num_tunnels]
        return tunnel if tunnel.connected else None

    def get_session(self, slot: int) -> requests.Session | None:
        """Return a ``requests.Session`` routed through the given tunnel.

        On macOS, routes traffic via the tunnel's local SOCKS5 proxy
        (works reliably with utun devices).  On Linux, uses BoundHTTPAdapter
        to bind directly to the tunnel's local IP.

        Returns None if the tunnel is not connected.
        """
        tunnel = self.get_tunnel(slot)
        if tunnel is None:
            return None

        idx = tunnel.tunnel_id
        # Cache sessions so repeated calls reuse the same pool
        if idx in self._sessions:
            return self._sessions[idx]

        session = requests.Session()

        if IS_MACOS and tunnel.socks_port:
            # Use the SOCKS5 proxy — reliable on macOS where source-IP
            # binding doesn't route through utun devices.
            proxy_url = f"socks5h://127.0.0.1:{tunnel.socks_port}"
            session.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
        elif tunnel.local_ip:
            # Linux: bind directly to the tunnel's local IP
            adapter = BoundHTTPAdapter(
                source_address=(tunnel.local_ip, 0),
                max_retries=urllib3.Retry(
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[502, 503, 504],
                ),
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
        else:
            return None

        self._sessions[idx] = session
        return session

    def get_playwright_proxy(self, slot: int) -> dict[str, str] | None:
        """Return Playwright proxy config for a tunnel's SOCKS5 proxy.

        Returns ``{"server": "socks5://127.0.0.1:10800"}`` or None.
        Use with ``browser = pw.chromium.launch(proxy=vpn.get_playwright_proxy(0))``.
        """
        tunnel = self.get_tunnel(slot)
        if tunnel is None or not tunnel.socks_proxy_url:
            return None
        return {"server": tunnel.socks_proxy_url}

    def is_tunnel_alive(self, slot: int) -> bool:
        """Check if a tunnel's openvpn process is still running."""
        tunnel = self._tunnels[slot % self.num_tunnels]
        if not tunnel.connected:
            return False
        if tunnel.pid is None:
            return False
        try:
            result = _sudo_run(
                ["sudo", "kill", "-0", str(tunnel.pid)],
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def check_and_heal(self) -> list[int]:
        """Check all tunnels and reconnect any that have died.

        Returns list of tunnel IDs that were reconnected.
        Thread-safe — can be called from any thread.
        """
        healed = []
        for tunnel in self._tunnels:
            if not tunnel.connected:
                # Already marked disconnected — try to reconnect
                self._log(f"Tunnel {tunnel.tunnel_id}: detected as disconnected "
                          f"— attempting reconnection")
                new_ip = self.rotate_tunnel(tunnel.tunnel_id,
                                           reason="self-heal (disconnected)")
                if new_ip:
                    healed.append(tunnel.tunnel_id)
                continue

            # Check if openvpn process is still alive
            alive = self.is_tunnel_alive(tunnel.tunnel_id)
            if not alive:
                self._log(f"Tunnel {tunnel.tunnel_id}: openvpn process died "
                          f"(was PID {tunnel.pid}) — reconnecting")
                # Mark as disconnected before rotating
                tunnel.connected = False
                new_ip = self.rotate_tunnel(tunnel.tunnel_id,
                                           reason="self-heal (process died)")
                if new_ip:
                    healed.append(tunnel.tunnel_id)
                continue

            # Check if SOCKS5 proxy can actually connect through the tunnel
            if tunnel.socks_port:
                ip = _get_public_ip_via_socks(tunnel.socks_port)
                if ip is None:
                    self._log(f"Tunnel {tunnel.tunnel_id}: SOCKS5 proxy "
                              f"unreachable — reconnecting")
                    new_ip = self.rotate_tunnel(tunnel.tunnel_id,
                                               reason="self-heal (socks dead)")
                    if new_ip:
                        healed.append(tunnel.tunnel_id)

        if healed:
            self._log(f"Self-healing complete: reconnected tunnels {healed}")
        return healed

    def rotate_tunnel(self, slot: int, reason: str = "rotation") -> str | None:
        """Disconnect and reconnect a specific tunnel to a new server.

        Returns the new public IP, or None on failure.
        """
        tunnel = self._tunnels[slot % self.num_tunnels]
        with tunnel.lock:
            self._log(f"Rotating tunnel {tunnel.tunnel_id} "
                      f"({tunnel.tun_device}) — reason: {reason}")

            old_ip = tunnel.ip
            old_server = tunnel.server

            # Disconnect
            self._disconnect_tunnel(tunnel)
            if old_ip:
                self._log_ip(old_server, old_ip,
                             f"disconnected — {reason}", tunnel.tunnel_id)

            # Invalidate cached session
            self._sessions.pop(tunnel.tunnel_id, None)

            # On macOS, assign a fresh tun device name. The kernel won't
            # let openvpn reuse a device name after the previous process
            # died ("Error: problem with tun vs. tap setting").
            if IS_MACOS:
                self._tun_generation += 1
                new_num = (TUN_OFFSET + self.tun_offset
                           + tunnel.tunnel_id
                           + self.num_tunnels * self._tun_generation)
                new_dev = f"tun{new_num}"
                self._log(f"Tunnel {tunnel.tunnel_id}: fresh device "
                          f"{new_dev} (was {tunnel.tun_device})")
                tunnel.tun_device = new_dev

            # Pick a new config
            configs = self._pick_configs(1)
            if not configs:
                self._log(f"No configs available for rotation of tunnel "
                          f"{tunnel.tunnel_id}")
                return None

            self._connect_tunnel(tunnel, configs[0])
            if tunnel.connected:
                self._start_socks_proxy(tunnel)
                self._log(f"Tunnel {tunnel.tunnel_id} rotated: "
                          f"{tunnel.ip} ({tunnel.server})")
                return tunnel.ip
            else:
                self._log(f"Tunnel {tunnel.tunnel_id} rotation failed")
                return None

    def disconnect_all(self) -> None:
        """Disconnect all tunnels and clean up."""
        for tunnel in self._tunnels:
            with tunnel.lock:
                if tunnel.connected:
                    self._log(f"Disconnecting tunnel {tunnel.tunnel_id} "
                              f"({tunnel.tun_device})...")
                    self._disconnect_tunnel(tunnel)
                    self._log_ip(tunnel.server, tunnel.ip,
                                 "disconnected", tunnel.tunnel_id)

        # Close cached sessions
        for session in self._sessions.values():
            try:
                session.close()
            except Exception:
                pass
        self._sessions.clear()

    def status(self) -> list[dict[str, Any]]:
        """Return status of all tunnels as a list of dicts."""
        return [t.to_dict() for t in self._tunnels]

    # -- Internal: config selection ------------------------------------------

    def _list_configs(self) -> list[Path]:
        """List available .ovpn config files, filtered by country if set."""
        configs = sorted(self.configs_dir.glob("*.ovpn"))
        if self.country:
            aliases = {"gb": ["gb", "uk"], "uk": ["uk", "gb"]}
            prefixes = aliases.get(self.country, [self.country])
            filtered = [
                c for c in configs
                if any(c.stem.startswith(p + ".") for p in prefixes)
            ]
            if filtered:
                return filtered
            self._log(f"No configs for country '{self.country}', using all")
        return configs

    def _pick_configs(self, n: int) -> list[Path]:
        """Pick *n* random configs that haven't been used yet.

        Guarantees no duplicates across currently-connected tunnels.
        """
        all_configs = self._list_configs()
        if not all_configs:
            raise RuntimeError(f"No .ovpn files found in {self.configs_dir}")

        # Exclude configs already in use by connected tunnels
        active_servers = {
            t.server for t in self._tunnels
            if t.connected and t.server
        }
        unused = [
            c for c in all_configs
            if c.stem not in self._used_configs and c.stem not in active_servers
        ]
        if len(unused) < n:
            # Reset history but still avoid active servers
            self._log(f"Resetting config history ({len(unused)} unused, need {n})")
            self._used_configs.clear()
            unused = [
                c for c in all_configs
                if c.stem not in active_servers
            ]

        random.shuffle(unused)
        picked = unused[:n]
        for c in picked:
            self._used_configs.add(c.stem)
        return picked

    # -- Internal: tunnel connection -----------------------------------------

    def _connect_tunnel(self, tunnel: Tunnel, config: Path) -> None:
        """Launch openvpn for a single tunnel.  Updates the Tunnel in-place."""
        tunnel.config = config
        tunnel.server = config.stem
        tunnel.connected = False
        tunnel.ip = None
        tunnel.local_ip = None
        tunnel.pid = None

        pid_file = self._tmpdir / f"openvpn_{tunnel.tunnel_id}.pid"
        log_file = self._tmpdir / f"openvpn_{tunnel.tunnel_id}.log"

        for p in (pid_file, log_file):
            p.write_bytes(b"")

        self._log(f"Tunnel {tunnel.tunnel_id}: connecting via "
                  f"{config.stem} on {tunnel.tun_device}...")

        try:
            result = _sudo_run(
                [
                    "sudo", OPENVPN_BIN,
                    "--config", str(config),
                    "--auth-user-pass", str(self.auth_file),
                    "--dev", tunnel.tun_device,
                    "--route-nopull",
                    "--script-security", "2",
                    "--daemon", f"{self.daemon_prefix}-{tunnel.tunnel_id}",
                    "--writepid", str(pid_file),
                    "--log-append", str(log_file),
                    "--connect-retry", "3",
                    "--connect-timeout", "30",
                ],
                text=True, timeout=15,
            )
        except subprocess.TimeoutExpired:
            self._log(f"Tunnel {tunnel.tunnel_id}: openvpn launch timed out")
            return
        except OSError as exc:
            self._log(f"Tunnel {tunnel.tunnel_id}: openvpn launch error: {exc}")
            return

        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            self._log(f"Tunnel {tunnel.tunnel_id}: openvpn launch failed: {err}")
            return

        # Read PID
        try:
            pid_text = pid_file.read_text().strip()
            if pid_text:
                tunnel.pid = int(pid_text)
        except (ValueError, OSError):
            pass

        # Wait for "Initialization Sequence Completed"
        max_wait = 60
        poll_interval = 3
        polls = max_wait // poll_interval
        for wait_num in range(polls):
            time.sleep(poll_interval)

            # Try to read PID if we don't have it yet
            if tunnel.pid is None:
                try:
                    pid_text = pid_file.read_text().strip()
                    if pid_text:
                        tunnel.pid = int(pid_text)
                except (ValueError, OSError):
                    pass

            try:
                log_text = log_file.read_text(errors="replace")
                if "Initialization Sequence Completed" in log_text:
                    # On macOS, OpenVPN uses utun devices (not tun).
                    # Parse the actual device name from the log.
                    if IS_MACOS:
                        utun_match = re.search(
                            r"(?:Opened utun device|TUN/TAP device)\s+(utun\d+)",
                            log_text,
                        )
                        if utun_match:
                            actual_dev = utun_match.group(1)
                            if actual_dev != tunnel.tun_device:
                                self._log(
                                    f"Tunnel {tunnel.tunnel_id}: macOS assigned "
                                    f"{actual_dev} (requested {tunnel.tun_device})")
                                tunnel.tun_device = actual_dev

                    # Tunnel is up — get local IP
                    time.sleep(2)
                    local_ip = _get_tun_local_ip(tunnel.tun_device)
                    if not local_ip:
                        # Retry once
                        time.sleep(2)
                        local_ip = _get_tun_local_ip(tunnel.tun_device)

                    if not local_ip:
                        self._log(f"Tunnel {tunnel.tunnel_id}: connected but "
                                  f"could not get local IP for {tunnel.tun_device}")
                        return

                    tunnel.local_ip = local_ip

                    # Add route for the VPN gateway so traffic flows through this tun
                    self._add_tunnel_route(tunnel, log_text)

                    # On macOS, start SOCKS5 proxy early so we can use it for
                    # IP verification (curl --interface doesn't work with utun)
                    if IS_MACOS:
                        self._start_socks_proxy(tunnel)

                    # Get public IP through this tunnel
                    if IS_MACOS and tunnel.socks_port:
                        public_ip = _get_public_ip_via_socks(tunnel.socks_port)
                        if not public_ip:
                            time.sleep(3)
                            public_ip = _get_public_ip_via_socks(tunnel.socks_port)
                    else:
                        public_ip = _get_public_ip_via_interface(tunnel.tun_device)
                        if not public_ip:
                            time.sleep(3)
                            public_ip = _get_public_ip_via_interface(tunnel.tun_device)

                    if public_ip:
                        tunnel.ip = public_ip
                        tunnel.connected = True
                        self._log_ip(tunnel.server, tunnel.ip,
                                     "connected", tunnel.tunnel_id)
                        self._log(f"Tunnel {tunnel.tunnel_id}: UP — "
                                  f"local={local_ip}, public={public_ip}, "
                                  f"server={tunnel.server}")
                    else:
                        # Tunnel is up but we can't verify the public IP;
                        # still mark as connected since the tunnel works
                        tunnel.ip = None
                        tunnel.connected = True
                        self._log(f"Tunnel {tunnel.tunnel_id}: UP — "
                                  f"local={local_ip}, public=unknown, "
                                  f"server={tunnel.server}")
                    return

                if "AUTH_FAILED" in log_text:
                    self._log(f"Tunnel {tunnel.tunnel_id}: auth failed — "
                              f"check {self.auth_file}")
                    return

                if "Connection refused" in log_text or "SIGTERM" in log_text:
                    self._log(f"Tunnel {tunnel.tunnel_id}: server rejected "
                              f"connection")
                    return

            except OSError:
                pass

            if self.verbose and wait_num % 3 == 2:
                elapsed = (wait_num + 1) * poll_interval
                self._log(f"Tunnel {tunnel.tunnel_id}: waiting... "
                          f"({elapsed}s)")

        # Timed out
        self._log(f"Tunnel {tunnel.tunnel_id}: connection timed out "
                  f"for {config.stem}")
        # Show last log lines for debugging
        try:
            lines = log_file.read_text(errors="replace").strip().splitlines()
            for line in lines[-5:]:
                self._log(f"  {line}")
        except Exception:
            pass

    def _add_tunnel_route(self, tunnel: Tunnel, log_text: str) -> None:
        """Add routes so traffic sent via this tun device actually reaches
        the internet through the VPN server.

        On macOS we parse the openvpn log for the remote VPN gateway and add
        a default route scoped to the tun device.

        On Linux we use ip-rule / ip-route with a dedicated routing table.
        """
        # Parse the VPN gateway IP from the openvpn log.
        # OpenVPN logs lines like:
        #   /sbin/route add -net 10.8.0.1 ... dev tun10
        #   PUSH: Received control message: ... route-gateway 10.8.0.1
        # Or from ifconfig output in the log:
        #   /sbin/ifconfig tun10 10.8.8.5 10.8.8.1 ...
        gateway = None

        # Try to find "route-gateway X.X.X.X" in PUSH messages
        gw_match = re.search(r"route-gateway\s+(\d+\.\d+\.\d+\.\d+)", log_text)
        if gw_match:
            gateway = gw_match.group(1)

        # Fallback: parse the ifconfig line for the peer/destination address
        if not gateway:
            # macOS ifconfig in openvpn log: /sbin/ifconfig tun10 10.8.8.5 10.8.8.1
            ifcfg_match = re.search(
                rf"ifconfig\s+{re.escape(tunnel.tun_device)}\s+"
                rf"(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)",
                log_text,
            )
            if ifcfg_match:
                # Second IP is the peer/gateway
                gateway = ifcfg_match.group(2)

        # Fallback: use the local IP's assumed gateway (replace last octet with 1)
        if not gateway and tunnel.local_ip:
            parts = tunnel.local_ip.rsplit(".", 1)
            if len(parts) == 2:
                gateway = parts[0] + ".1"

        if not gateway:
            self._log(f"Tunnel {tunnel.tunnel_id}: could not determine VPN "
                      f"gateway — routing may not work")
            return

        if IS_MACOS:
            # Add scoped default routes through this tunnel's gateway.
            # -ifscope ensures these routes only apply to sockets bound to
            # this interface (via IP_BOUND_IF), so multiple tunnels can each
            # have their own routes without conflicting.
            for net in ["0.0.0.0/1", "128.0.0.0/1"]:
                try:
                    _sudo_run(
                        [
                            "sudo", "route", "add",
                            "-ifscope", tunnel.tun_device,
                            "-net", net, gateway,
                        ],
                        text=True, timeout=10,
                    )
                except (subprocess.TimeoutExpired, OSError) as exc:
                    self._log(f"Tunnel {tunnel.tunnel_id}: route add "
                              f"failed for {net}: {exc}")
        else:
            # Linux: use policy routing with a dedicated table
            table_id = 100 + tunnel.tunnel_id
            try:
                # Flush any existing rules/routes for this table
                _sudo_run(
                    ["sudo", "ip", "rule", "del", "from", tunnel.local_ip,
                     "table", str(table_id)],
                    timeout=10,
                )
                _sudo_run(
                    ["sudo", "ip", "route", "flush", "table", str(table_id)],
                    timeout=10,
                )
                # Add default route in the table
                _sudo_run(
                    ["sudo", "ip", "route", "add", "default", "via", gateway,
                     "dev", tunnel.tun_device, "table", str(table_id)],
                    text=True, timeout=10, check=True,
                )
                # Add ip rule: traffic from this tun's IP uses this table
                _sudo_run(
                    ["sudo", "ip", "rule", "add", "from", tunnel.local_ip,
                     "table", str(table_id)],
                    text=True, timeout=10, check=True,
                )
            except (subprocess.TimeoutExpired, OSError,
                    subprocess.CalledProcessError) as exc:
                self._log(f"Tunnel {tunnel.tunnel_id}: policy routing "
                          f"setup failed: {exc}")

    def _remove_tunnel_routes(self, tunnel: Tunnel) -> None:
        """Remove routes added by _add_tunnel_route."""
        if IS_MACOS:
            for net in ["0.0.0.0/1", "128.0.0.0/1"]:
                try:
                    _sudo_run(
                        [
                            "sudo", "route", "delete",
                            "-ifscope", tunnel.tun_device,
                            "-net", net,
                        ],
                        text=True, timeout=10,
                    )
                except (subprocess.TimeoutExpired, OSError):
                    pass
        else:
            table_id = 100 + tunnel.tunnel_id
            if tunnel.local_ip:
                try:
                    _sudo_run(
                        ["sudo", "ip", "rule", "del", "from", tunnel.local_ip,
                         "table", str(table_id)],
                        timeout=10,
                    )
                except (subprocess.TimeoutExpired, OSError):
                    pass
            try:
                _sudo_run(
                    ["sudo", "ip", "route", "flush", "table", str(table_id)],
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass

    def _start_socks_proxy(self, tunnel: Tunnel) -> None:
        """Start a local SOCKS5 proxy that routes through the tunnel."""
        if not tunnel.local_ip or not tunnel.connected:
            return
        # Stop any existing proxy for this tunnel
        self._stop_socks_proxy(tunnel)

        port = SOCKS5_BASE_PORT + self.tun_offset + tunnel.tunnel_id

        # Already running from early start in _connect_tunnel
        if tunnel.socks_port == port and tunnel._socks_server is not None:
            return

        # If port is held by a stale process, try to free it
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            test_sock.bind(("127.0.0.1", port))
        except OSError:
            my_pid = os.getpid()
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True, text=True, timeout=5,
                )
                pids = [int(p) for p in result.stdout.strip().split() if p]
                if pids and all(p == my_pid for p in pids):
                    pass  # our own threads — will be cleaned up by _stop_socks_proxy
                elif pids:
                    self._log(f"Tunnel {tunnel.tunnel_id}: port {port} held by "
                              f"PID(s) {pids} — killing stale processes...")
                    for pid in pids:
                        for sig in (signal.SIGTERM, signal.SIGKILL):
                            try:
                                os.kill(pid, sig)
                            except PermissionError:
                                _sudo_run(["sudo", "kill", f"-{sig.value}", str(pid)])
                            except ProcessLookupError:
                                break
                            # Give process a moment to die
                            time.sleep(0.3)
                            try:
                                os.kill(pid, 0)
                            except (ProcessLookupError, PermissionError):
                                break  # dead
                    # Verify port is free now
                    time.sleep(0.5)
                    test2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    try:
                        test2.bind(("127.0.0.1", port))
                    except OSError:
                        self._log(f"Tunnel {tunnel.tunnel_id}: port {port} still "
                                  f"occupied after killing stale PIDs — giving up.")
                        return
                    finally:
                        test2.close()
            except Exception:
                pass
        finally:
            test_sock.close()

        try:
            server = _Socks5Server(port, tunnel.local_ip, tunnel.tun_device)
            thread = threading.Thread(
                target=server.serve_forever,
                name=f"socks5-tunnel-{tunnel.tunnel_id}",
                daemon=True,
            )
            thread.start()
            tunnel.socks_port = port
            tunnel._socks_server = server
            self._log(f"Tunnel {tunnel.tunnel_id}: SOCKS5 proxy on "
                      f"127.0.0.1:{port} -> {tunnel.local_ip}")
        except OSError as exc:
            self._log(f"Tunnel {tunnel.tunnel_id}: failed to start SOCKS5 "
                      f"proxy on port {port}: {exc}")

    def _stop_socks_proxy(self, tunnel: Tunnel) -> None:
        """Stop the SOCKS5 proxy for a tunnel."""
        if tunnel._socks_server is not None:
            try:
                tunnel._socks_server.shutdown()
            except Exception:
                pass
            tunnel._socks_server = None
        tunnel.socks_port = 0

    def _disconnect_tunnel(self, tunnel: Tunnel) -> None:
        """Kill the openvpn process for a single tunnel and clean up routes."""
        # Stop SOCKS proxy first
        self._stop_socks_proxy(tunnel)
        # Remove routes (while tun device still exists)
        self._remove_tunnel_routes(tunnel)

        # Kill the openvpn process by PID
        if tunnel.pid is not None:
            try:
                _sudo_run(
                    ["sudo", "kill", str(tunnel.pid)],
                    timeout=10,
                )
                # Wait for process to exit
                for _ in range(10):
                    check = _sudo_run(
                        ["sudo", "kill", "-0", str(tunnel.pid)],
                        timeout=10,
                    )
                    if check.returncode != 0:
                        break
                    time.sleep(0.5)
            except (subprocess.TimeoutExpired, OSError):
                pass

        # Also try killing by daemon name as a fallback
        daemon_name = f"{self.daemon_prefix}-{tunnel.tunnel_id}"
        try:
            _sudo_run(
                ["sudo", "pkill", "-f", daemon_name],
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

        time.sleep(1)

        # Invalidate cached session
        old_session = self._sessions.pop(tunnel.tunnel_id, None)
        if old_session:
            try:
                old_session.close()
            except Exception:
                pass

        tunnel.connected = False
        tunnel.ip = None
        tunnel.local_ip = None
        tunnel.pid = None

    # -- Internal: preflight -------------------------------------------------

    def _preflight(self) -> None:
        """Validate setup before connecting."""
        if OPENVPN_BIN == "openvpn" and not shutil.which("openvpn"):
            raise RuntimeError(
                "openvpn not found. Install with:\n  brew install openvpn"
            )
        configs = self._list_configs()
        if not configs:
            raise RuntimeError(
                f"No .ovpn files in {self.configs_dir}\n"
                f"Download from: "
                f"https://account.protonvpn.com/downloads"
                f"#openvpn-configuration-files"
            )
        if len(configs) < self.num_tunnels:
            self._log(
                f"WARNING: only {len(configs)} configs available for "
                f"{self.num_tunnels} tunnels — some servers will be reused"
            )
        if not self.auth_file.exists():
            raise RuntimeError(
                f"Auth file not found: {self.auth_file}\n"
                f"Create with: sudo tee {self.auth_file} "
                f"<<< 'username\\npassword'"
            )

    # -- Internal: signal / cleanup ------------------------------------------

    def _install_signal_handlers(self) -> None:
        """Ensure cleanup on SIGINT/SIGTERM."""
        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)

        def _handler(signum: int, frame: Any) -> None:
            signame = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            print(f"\n  [vpn-concurrent] Caught {signame}, disconnecting...")
            self.disconnect_all()
            self._cleanup_tmpdir()
            if signum == signal.SIGINT and callable(prev_sigint):
                prev_sigint(signum, frame)
            elif signum == signal.SIGTERM and callable(prev_sigterm):
                prev_sigterm(signum, frame)
            else:
                sys.exit(128 + signum)

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def _atexit_cleanup(self) -> None:
        """atexit handler."""
        any_connected = any(t.connected for t in self._tunnels)
        if any_connected:
            print("\n  [vpn-concurrent] Cleaning up VPN connections...")
            self.disconnect_all()
        self._cleanup_tmpdir()

    def _cleanup_tmpdir(self) -> None:
        if self._tmpdir.exists():
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    # -- Internal: logging ---------------------------------------------------

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [vpn-concurrent] {msg}")

    def _log_ip(
        self,
        server: str | None,
        ip: str | None,
        reason: str,
        tunnel_id: int | None = None,
    ) -> None:
        """Append to the IP log JSON file."""
        if not self.log_file:
            return
        log: list[dict[str, Any]] = []
        if self.log_file.exists():
            try:
                log = json.loads(
                    self.log_file.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                pass
        log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tunnel_id": tunnel_id,
            "server": server,
            "ip": ip,
            "reason": reason,
        })
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text(
            json.dumps(log, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Concurrent OpenVPN tunnel manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "command",
        choices=["connect", "status", "disconnect"],
        help="Action to perform",
    )
    ap.add_argument(
        "--num-tunnels", "-n", type=int, default=3,
        help="Number of simultaneous tunnels (default: 3)",
    )
    ap.add_argument(
        "--configs", type=Path, default=DEFAULT_CONFIGS_DIR,
        help="Directory with .ovpn files",
    )
    ap.add_argument(
        "--auth", type=Path, default=DEFAULT_AUTH_FILE,
        help="OpenVPN auth file",
    )
    ap.add_argument(
        "--log-file", type=Path, default=None,
        help="IP log JSON file",
    )
    ap.add_argument(
        "--country", type=str, default=None,
        help="Prefer servers in this country code (e.g. gb, us, de)",
    )
    ap.add_argument(
        "--quiet", action="store_true",
        help="Suppress verbose output",
    )
    ap.add_argument(
        "--tun-offset", type=int, default=0,
        help="Offset for tun device numbering and SOCKS5 ports, so multiple "
             "scripts can run without overlap (default: 0). E.g. --tun-offset 3 "
             "gives tun13,14,15 and ports 10803,10804,10805.",
    )
    return ap


def cli_main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "status":
        ip = get_public_ip()
        print(f"Current public IP: {ip or 'unknown'}")
        try:
            result = subprocess.run(
                ["pgrep", "-f", "openvpn-concurrent"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                print(f"openvpn-concurrent processes: {len(pids)} "
                      f"(pids: {', '.join(pids)})")
            else:
                print("openvpn-concurrent processes: none")
        except Exception:
            pass

        # Check each tun device
        for i in range(args.num_tunnels):
            tun = f"tun{TUN_OFFSET + args.tun_offset + i}"
            local_ip = _get_tun_local_ip(tun)
            if local_ip:
                pub_ip = _get_public_ip_via_interface(tun)
                print(f"  {tun}: local={local_ip}, public={pub_ip or 'unknown'}")
            else:
                print(f"  {tun}: down")
        return

    if args.command == "disconnect":
        # Kill all openvpn-concurrent daemons
        print("Stopping all concurrent VPN tunnels...")
        try:
            subprocess.run(
                ["sudo", "pkill", "-f", "openvpn-concurrent"],
                capture_output=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            print("Warning: pkill timed out")
        time.sleep(2)

        # Clean up routes for each possible tun device
        for i in range(args.num_tunnels):
            tun = f"tun{TUN_OFFSET + args.tun_offset + i}"
            if IS_MACOS:
                for net in ["0.0.0.0/1", "128.0.0.0/1"]:
                    try:
                        subprocess.run(
                            ["sudo", "route", "delete", "-net", net,
                             "-interface", tun],
                            capture_output=True, timeout=10,
                        )
                    except (subprocess.TimeoutExpired, OSError):
                        pass
            else:
                table_id = 100 + i
                try:
                    subprocess.run(
                        ["sudo", "ip", "route", "flush", "table",
                         str(table_id)],
                        capture_output=True, timeout=10,
                    )
                except (subprocess.TimeoutExpired, OSError):
                    pass

        print("Disconnected all tunnels.")
        ip = get_public_ip()
        print(f"Current IP: {ip or 'unknown'}")
        return

    if args.command == "connect":
        vpn = ConcurrentVPN(
            num_tunnels=args.num_tunnels,
            configs_dir=args.configs,
            auth_file=args.auth,
            log_file=args.log_file,
            country=args.country,
            verbose=not args.quiet,
            tun_offset=args.tun_offset,
        )
        vpn._preflight()
        vpn._install_signal_handlers()
        atexit.register(vpn._atexit_cleanup)
        vpn._setup_done = True

        tunnels = vpn.connect_all()
        print(f"\n--- Tunnel Status ---")
        for t in tunnels:
            state = "UP" if t.connected else "DOWN"
            print(f"  [{state}] tunnel {t.tunnel_id}: {t.tun_device} "
                  f"-> {t.ip or 'n/a'} ({t.server or 'n/a'})")
        print(f"\nTunnels will stay active. Use 'disconnect' command to stop.")

        # Keep alive until interrupted
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nInterrupted.")
            vpn.disconnect_all()
            vpn._cleanup_tmpdir()
            ip = get_public_ip()
            print(f"Disconnected. Current IP: {ip or 'unknown'}")
        return


if __name__ == "__main__":
    cli_main()
