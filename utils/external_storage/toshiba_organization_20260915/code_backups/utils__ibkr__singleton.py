"""IB Gateway singleton + keepalive: exactly one instance, running when it should be.

Guarantees:
  1. SINGLETON — an exclusive file lock serialises all management, and any surplus
     gateway processes beyond one are killed (keeping the one bound to the API port,
     else the oldest). No race window: the lock is held across detect->act.
  2. KEEPALIVE — if zero gateways are running AND we should be up (no halt sentinel),
     the start script is invoked to relaunch+auto-login. Idempotent: safe to call
     every N seconds from cron or a loop.
  3. SAFE — never launches while the halt sentinel is present (guards tripped); never
     kills the healthy listener.

Pure decision logic (`plan`) is separated from side effects (`enforce`) for testing.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from utils.ibkr.common import REPO_ROOT
from utils.data_paths import CONFIGURED_DATA_ROOT

LOCK_PATH = CONFIGURED_DATA_ROOT / "research/ib_gateway_singleton.lock"
STATUS_PATH = CONFIGURED_DATA_ROOT / "research/ib_gateway_singleton_status.json"
HALT_SENTINEL = CONFIGURED_DATA_ROOT / "research/runtime_halt_sentinel"
START_SCRIPT = REPO_ROOT / "utils/ibkr/start.sh"
GATEWAY_PROC_MATCH = "IB Gateway 10.45/.install4j"
API_PORT = 4002


def gateway_pids() -> list[int]:
    """PIDs of running gateway JVMs (oldest first by PID)."""
    try:
        out = subprocess.run(["pgrep", "-f", GATEWAY_PROC_MATCH], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return sorted(int(p) for p in out.split() if p.strip().isdigit())


def port_listening(host: str = "127.0.0.1", port: int = API_PORT, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def pid_listening_on_port(pids: list[int], port: int = API_PORT) -> int | None:
    if not port_listening(port=port):
        return None
    try:
        out = subprocess.run(["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10).stdout
        owners = {int(p) for p in out.split() if p.strip().isdigit()}
    except (OSError, subprocess.TimeoutExpired):
        owners = set()
    for pid in pids:
        if pid in owners:
            return pid
    return owners and next(iter(owners)) or (pids[0] if pids else None)


def plan(pids: list[int], *, port_up: bool, halted: bool, keeper: int | None) -> dict:
    """Pure decision: what to do given process/port/halt state."""
    n = len(pids)
    if n == 0:
        return {"action": "halted_no_launch" if halted else "launch", "kill": [], "keep": None}
    keep = keeper if keeper in pids else pids[0]  # listener wins, else oldest
    surplus = [p for p in pids if p != keep]
    if surplus:
        return {"action": "kill_surplus", "kill": surplus, "keep": keep}
    # exactly one
    if port_up:
        return {"action": "healthy", "kill": [], "keep": keep}
    return {"action": "single_starting_or_stuck", "kill": [], "keep": keep}


def enforce(*, launch: bool = True) -> dict:
    pids = gateway_pids()
    port_up = port_listening()
    halted = HALT_SENTINEL.exists()
    keeper = pid_listening_on_port(pids)
    decision = plan(pids, port_up=port_up, halted=halted, keeper=keeper)

    acted = []
    for pid in decision["kill"]:
        try:
            os.kill(pid, signal.SIGKILL)
            acted.append(f"killed_surplus:{pid}")
        except ProcessLookupError:
            pass
        except OSError as exc:
            acted.append(f"kill_failed:{pid}:{exc}")
    if decision["action"] == "launch" and launch:
        env = dict(os.environ, IBC_AUTOLOGIN_ENABLED="1")
        subprocess.Popen(["/bin/bash", str(START_SCRIPT)], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        acted.append("launched_gateway")

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gateway_pids": pids,
        "port_4002_up": port_up,
        "halted": halted,
        "keeper_pid": decision["keep"],
        "action": decision["action"],
        "acted": acted,
        "singleton_ok": len(pids) <= 1,
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=1))
    return status


def run(*, loop: int = 0, launch: bool = True) -> int:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(json.dumps({"skipped": "another singleton manager holds the lock"}))
        return 0
    try:
        while True:
            status = enforce(launch=launch)
            print(json.dumps({"action": status["action"], "pids": status["gateway_pids"],
                              "port": status["port_4002_up"], "acted": status["acted"]}))
            if not loop:
                return 0
            time.sleep(max(20, loop))
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IB Gateway singleton + keepalive manager")
    ap.add_argument("--loop", type=int, default=0, help="seconds between passes; 0 = once")
    ap.add_argument("--no-launch", action="store_true", help="enforce singleton but never launch")
    return run(loop=ap.parse_args(argv).loop, launch=not ap.parse_args(argv).no_launch)


if __name__ == "__main__":
    raise SystemExit(main())
