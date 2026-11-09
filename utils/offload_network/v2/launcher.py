"""Submitter-side launcher for v2 sealed bundles.

Given a manifest whose seal has been pushed to the remote, the
launcher:
  1. Computes the per-job remote workdir under host.remote_workdir.
  2. Creates that workdir on the remote (mkdir -p equivalent).
  3. Extracts the seal into the workdir (PowerShell tar).
  4. Spawns the bootstrap.cmd as a detached background process via
     Start-Process so the ssh session can return immediately.
  5. Records the wrapper PID so callers can monitor.

The remote runner writes status.json into the workdir; submit.py polls
that file to detect completion.
"""
from __future__ import annotations

import json
import pathlib
import textwrap
from typing import Optional

from .manifest import SealedManifest, SealError, SealStatus
from .transport import (
    remote_run, remote_run_retrying, remote_run_posix_retrying,
    remote_path_exists,
)


def remote_workdir_for(manifest: SealedManifest) -> str:
    """C:/sealed/jobs/<job_id> (under host.remote_workdir)."""
    base = manifest.host.remote_workdir.rstrip("/\\")
    return f"{base}/{manifest.job_id}"


def ensure_remote_dir(host_alias: str, remote_path: str, *, platform: str = "windows") -> None:
    """mkdir -p the remote dir. Idempotent (-Force) + retried on
    transient SSH failures."""
    if platform in {"linux", "macos"}:
        r = remote_run_posix_retrying(
            host_alias=host_alias, script='mkdir -p -- "$1"', args=[remote_path],
            timeout=30, label=f"ensure_remote_dir {remote_path}",
        )
        if r.returncode != 0:
            raise SealError(f"mkdir {remote_path} on {host_alias} failed: {r.stderr[:200]}")
        return
    safe = remote_path.replace("'", "''")
    ps = f"New-Item -ItemType Directory -Force -Path '{safe}' | Out-Null"
    r = remote_run_retrying(
        host_alias=host_alias, powershell_script=ps,
        timeout=30, label=f"ensure_remote_dir {remote_path}",
    )
    if r.returncode != 0:
        raise SealError(f"mkdir {remote_path} on {host_alias} failed: {r.stderr[:200]}")


def extract_seal_remote(host_alias: str, *, seal_remote_path: str, workdir: str,
                        archive_format: str, platform: str = "windows", force: bool = False,
                        expected_sha256: str = "", python_executable: str = "") -> bool:
    """Verify before extraction/execution; only a hash-bound completion marker permits reuse."""
    import base64
    import re
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise SealError("expected seal SHA-256 is required before remote extraction")
    helper = pathlib.Path(__file__).with_name("safe_archive.py").read_text()
    code = helper + """
import hashlib, json, os, sys, tempfile, uuid
seal, destination, expected = sys.argv[1:4]
digest = hashlib.sha256()
with open(seal, 'rb') as stream:
    for chunk in iter(lambda: stream.read(1 << 20), b''):
        digest.update(chunk)
if digest.hexdigest() != expected:
    raise ValueError('remote seal SHA-256 mismatch')
dest = pathlib.Path(destination)
marker = dest / '.seal-complete.json'
if marker.is_file():
    if json.loads(marker.read_text()).get('sha256') != expected:
        raise ValueError('existing job has a different seal identity')
    print('REUSED')
else:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.extract-', dir=dest.parent) as temporary:
        staging = pathlib.Path(temporary) / 'job'
        with open_archive(seal) as archive:
            extract_tar(archive, staging)
        (staging / '.seal-complete.json').write_text(json.dumps({'sha256': expected}))
        if dest.exists():
            # Retain interrupted extraction evidence, never overwrite an active job.
            if (dest / 'status.json').exists():
                raise ValueError('unverified existing job has execution status; manual reconciliation required')
            os.replace(dest, str(dest) + '.incomplete.' + uuid.uuid4().hex)
        os.replace(staging, dest)
    print('EXTRACTED')
"""
    encoded = base64.b64encode(code.encode()).decode()
    wrapper = f"import base64;exec(base64.b64decode('{encoded}'))"
    python = python_executable or ("python" if platform == "windows" else "python3")
    if platform in {"linux", "macos"}:
        result = remote_run_posix_retrying(host_alias=host_alias,
            script='"$1" -c "$2" "$3" "$4" "$5"',
            args=[python, wrapper, seal_remote_path, workdir, expected_sha256],
            timeout=600, label=f"verified extract {workdir}")
    else:
        quote = lambda value: "'" + value.replace("'", "''") + "'"
        script = "& " + " ".join(map(quote, [python, "-c", wrapper, seal_remote_path,
                                             workdir, expected_sha256]))
        script += "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
        result = remote_run_retrying(host_alias=host_alias, powershell_script=script,
                                    timeout=600, label=f"verified extract {workdir}")
    if result.returncode != 0:
        raise SealError(f"verified extract on {host_alias} failed: {result.stderr[-400:]}")
    if "EXTRACTED" not in result.stdout and "REUSED" not in result.stdout:
        raise SealError("remote extraction did not acknowledge verified completion")
    return "EXTRACTED" in result.stdout


def spawn_bootstrap(
    host_alias: str,
    workdir: str,
    *,
    platform: str = "windows",
    force: bool = False,
) -> Optional[int]:
    """Spawn bootstrap.cmd FULLY DETACHED from the SSH session.

    Idempotent: if ``status.json`` already exists in ``workdir``, an
    earlier runner has already started (or completed) in this workdir.
    Returns ``None`` without spawning so callers can move directly to
    polling. Without this guard, a re-submit after a transient SSH
    failure would launch a SECOND python runner that races the first
    one over status.json, run.log, and the result archive. Set
    ``force=True`` to override (e.g. when a previous runner crashed
    without updating status and you want to restart).

    Uses an inline Python script that calls subprocess.Popen with
    DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB.
    Plain PowerShell Start-Process does NOT break out of the SSH job
    object — when ssh disconnects, the spawned process is reaped. v1
    fixed this exact issue the same way.
    """
    if not force:
        status_path = f"{workdir.rstrip('/')}/status.json"
        if remote_path_exists(host_alias, status_path, platform=platform, timeout=15):
            # A runner is already (or was already) here. Caller should
            # poll the existing status.json rather than restart.
            return None
    if platform in {"linux", "macos"}:
        result = remote_run_posix_retrying(
            host_alias=host_alias,
            script=(
                'set -eu\ncd -- "$1"\ntest -f bootstrap.sh\n'
                'nohup sh ./bootstrap.sh </dev/null >>bootstrap.log 2>&1 &\n'
                'printf "PID=%s\\n" "$!"'
            ),
            args=[workdir], timeout=60, label=f"spawn_bootstrap {workdir}",
        )
        if result.returncode != 0:
            raise SealError(
                f"spawn on {host_alias} failed: rc={result.returncode}\n"
                f"  stdout: {result.stdout[:400]}\n  stderr: {result.stderr[:400]}"
            )
        for line in result.stdout.splitlines():
            if line.startswith("PID="):
                try:
                    return int(line[4:].strip())
                except ValueError:
                    break
        return None
    safe = workdir.replace("'", "''").replace("\\", "\\\\")
    # Pass DEVNULL for stdout/stderr; cmd.exe's own redirects write to
    # bootstrap.log, and the python runner opens run.log itself and dup2's.
    # Passing a real file handle here would conflict with the runner's
    # append-open (Windows file sharing) and cause the runner's open to
    # fail with "process cannot access the file".
    py = (
        "import subprocess, sys, os; "
        f"workdir = r'{safe}'; "
        "boot = os.path.join(workdir, 'bootstrap.cmd'); "
        "DETACHED = 0x00000008; NEW_GROUP = 0x00000200; BREAKAWAY = 0x01000000; "
        "p = subprocess.Popen(['cmd.exe', '/c', boot], cwd=workdir, "
        "creationflags=DETACHED | NEW_GROUP | BREAKAWAY, "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, "
        "close_fds=True); "
        "print('PID=' + str(p.pid))"
    )
    ps = textwrap.dedent(f"""
        $workdir = '{safe}'
        $bootstrap = Join-Path $workdir 'bootstrap.cmd'
        if (-not (Test-Path -LiteralPath $bootstrap)) {{
            throw "bootstrap.cmd missing in $workdir"
        }}
        & python -c "{py}"
    """).strip()
    r = remote_run_retrying(
        host_alias=host_alias, powershell_script=ps,
        timeout=60, label=f"spawn_bootstrap {workdir}",
    )
    if r.returncode != 0:
        raise SealError(
            f"spawn on {host_alias} failed: rc={r.returncode}\n"
            f"  stdout: {r.stdout[:400]}\n  stderr: {r.stderr[:400]}"
        )
    pid = None
    for line in r.stdout.splitlines():
        if line.startswith("PID="):
            try:
                pid = int(line[4:].strip())
                break
            except ValueError:
                pass
    return pid


def launch(
    manifest: SealedManifest,
    *,
    seal_remote_path: str,
) -> dict:
    """Run the full extract-and-spawn sequence. Returns a dict with
    {workdir, pid, status_path}."""
    workdir = remote_workdir_for(manifest)
    ensure_remote_dir(manifest.host.ssh_alias, workdir, platform=manifest.host.platform)
    extract_seal_remote(
        manifest.host.ssh_alias,
        seal_remote_path=seal_remote_path,
        workdir=workdir,
        archive_format=manifest.archive_format,
        platform=manifest.host.platform,
        expected_sha256=manifest.seal_sha256 or "",
        python_executable=manifest.host.python_executable or "",
    )
    manifest.status = SealStatus.EXTRACTED
    pid = spawn_bootstrap(manifest.host.ssh_alias, workdir, platform=manifest.host.platform)
    manifest.status = SealStatus.RUNNING
    return {
        "workdir": workdir,
        "pid": pid,
        "status_path": f"{workdir}/status.json",
        "result_archive_glob": f"{workdir}/{manifest.job_id}.result.*",
    }


def read_remote_status(
    host_alias: str, status_path: str, *, platform: str = "windows"
) -> Optional[dict]:
    """Read remote status.json. Returns parsed dict or None if not yet
    present.

    Retries transient SSH failures internally — a single dropped poll
    during a 25-minute replay is no reason to abort the whole submit.
    Returns None on definitive non-transport errors (eg. file missing,
    JSON malformed) so the poll loop tries again on the next tick.
    """
    if platform in {"linux", "macos"}:
        try:
            r = remote_run_posix_retrying(
                host_alias=host_alias,
                script='test -f "$1" && cat -- "$1"', args=[status_path],
                timeout=30, label=f"read_remote_status {status_path}",
            )
        except Exception:
            return None
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return None
    safe = status_path.replace("'", "''")
    ps = f"$p='{safe}'; if (Test-Path -LiteralPath $p) {{ Get-Content -Raw -LiteralPath $p }}"
    try:
        r = remote_run_retrying(
            host_alias=host_alias, powershell_script=ps,
            timeout=30, label=f"read_remote_status {status_path}",
        )
    except Exception:
        return None
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
