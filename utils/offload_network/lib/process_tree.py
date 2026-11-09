"""Bounded execution for trusted local commands, not an OS sandbox."""

import os
import signal
import subprocess


def clean_environment(extra=None):
    allowed = {
        "PATH",
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "SYSTEMDRIVE",
    }
    env = {k: v for k, v in os.environ.items() if k in allowed}
    env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONUTF8": "1",
        }
    )
    env.update(extra or {})
    return env


def stop_tree(proc):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(timeout=15)


def run_tree(command, *, timeout, cwd=None, env=None, **kwargs):
    flags = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    proc = subprocess.Popen(command, cwd=cwd, env=env, **flags, **kwargs)
    try:
        rc = proc.wait(timeout=timeout)
        return subprocess.CompletedProcess(command, rc)
    finally:
        # Also reap descendants left behind by a normally exiting parent on POSIX.
        stop_tree(proc)
