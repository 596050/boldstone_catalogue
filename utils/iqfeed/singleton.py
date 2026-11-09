"""IQFeed (IQConnect) singleton + keepalive — the IB-Gateway pattern for IQFeed.

IQConnect runs under Wine; login is fully automatic from .env (no GUI/2FA), so
recovery is simpler than the gateway. Reuses the tested pure `plan()` from
gateway_singleton (identical decision logic); only process detection, the launch
command, and the port differ.
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

from utils.ibkr.common import REPO_ROOT
from utils.ibkr.singleton import plan  # reuse the verified decision logic
from utils.data_paths import resolve_data_path

LOCK_PATH = resolve_data_path("research/iqfeed_singleton.lock")
STATUS_PATH = resolve_data_path("research/iqfeed_singleton_status.json")
HALT_SENTINEL = resolve_data_path("research/runtime_halt_sentinel")
START_SCRIPT = REPO_ROOT / "utils/iqfeed/start.sh"
IQCONNECT_MATCH = "iqconnect.exe"
LOOKUP_PORT = 9100


def iqfeed_pids() -> list[int]:
    try:
        out = subprocess.run(["pgrep", "-f", IQCONNECT_MATCH], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return sorted(int(p) for p in out.split() if p.strip().isdigit())


def port_listening(host: str = "127.0.0.1", port: int = LOOKUP_PORT, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def keeper_pid(pids: list[int]) -> int | None:
    # IQConnect's port owner isn't easily lsof'd (Wine); keep the oldest by convention.
    return pids[0] if pids else None


def enforce(*, launch: bool = True) -> dict:
    pids = iqfeed_pids()
    port_up = port_listening()
    halted = HALT_SENTINEL.exists()
    decision = plan(pids, port_up=port_up, halted=halted, keeper=keeper_pid(pids))

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
        subprocess.Popen(["/bin/bash", str(START_SCRIPT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        acted.append("launched_iqconnect")

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "iqconnect_pids": pids,
        "port_9100_up": port_up,
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
        print(json.dumps({"skipped": "another iqfeed singleton manager holds the lock"}))
        return 0
    try:
        while True:
            s = enforce(launch=launch)
            print(json.dumps({"action": s["action"], "pids": s["iqconnect_pids"],
                              "port": s["port_9100_up"], "acted": s["acted"]}))
            if not loop:
                return 0
            time.sleep(max(20, loop))
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IQFeed singleton + keepalive manager")
    ap.add_argument("--loop", type=int, default=0)
    ap.add_argument("--no-launch", action="store_true")
    a = ap.parse_args(argv)
    return run(loop=a.loop, launch=not a.no_launch)


if __name__ == "__main__":
    raise SystemExit(main())
