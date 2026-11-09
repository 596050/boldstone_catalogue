#!/usr/bin/env python3
"""Hold an idle client connection to IQConnect's lookup port (127.0.0.1:9100).

IQConnect auto-exits ~5 s after its LAST client disconnects ("NO CLIENTS
CONNECTED SINCE STARTUP / LAST CLIENT DISCONNECTED" in IQConnectLog.txt), so
every pull session was killing it and the next pull paid a full Wine boot
(~90-120 s under load, often timing out). Keeping one idle connection open
makes IQConnect persistent — the normal usage pattern for IQFeed apps.

Singleton via pid lock. Reconnects forever while the port comes and goes;
exits after 6 h of continuous dead port (ensure_iqfeed_lookup restarts it on
the next successful launch).
"""
import os
import pathlib
import socket
import sys
import time

HOST, PORT = "127.0.0.1", 9100
LOCK = pathlib.Path(os.environ.get("IQFEED_KEEPALIVE_PID", str(
    pathlib.Path(__file__).resolve().parents[3] / ".runtime/iqfeed/iqfeed_keepalive.pid"
)))
GIVE_UP_AFTER_DEAD_S = 6 * 3600


def _alive(pid_text: str) -> bool:
    try:
        os.kill(int(pid_text), 0)
        return True
    except Exception:
        return False


def main() -> int:
    if LOCK.exists() and _alive(LOCK.read_text().strip()):
        return 0
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(str(os.getpid()))
    dead_since = None
    try:
        while True:
            try:
                with socket.create_connection((HOST, PORT), timeout=5) as s:
                    dead_since = None
                    s.settimeout(60)
                    while True:
                        try:
                            if s.recv(4096) == b"":
                                break  # server closed the socket
                        except socket.timeout:
                            continue   # quiet port is normal; keep holding
            except OSError:
                pass
            if dead_since is None:
                dead_since = time.time()
            elif time.time() - dead_since > GIVE_UP_AFTER_DEAD_S:
                return 0
            time.sleep(10)
    finally:
        try:
            if LOCK.read_text().strip() == str(os.getpid()):
                LOCK.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
