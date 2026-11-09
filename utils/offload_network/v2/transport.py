"""Single-file rsync transport for sealed bundles + result archives.

Design notes:
  - The seal archive is ALREADY compressed (tar.gz or tar.zst). Adding
    -z to rsync only burns CPU. We omit -z for the seal push.
  - Result archives are small (typically <50 MB). We DO include -z there
    because they're often mostly JSON/log text that compresses well.
  - --partial + --partial-dir lets a flaky-network transfer resume on
    retry. We retry up to MAX_ATTEMPTS times with exponential backoff.
  - All paths quoted defensively to survive spaces.

Configuration:
  RSYNC_BIN — local rsync binary path. Prefer GNU rsync 3.x over Apple
              openrsync (which silently truncates long transfers). We
              prefer /opt/homebrew/bin/rsync if present.
"""
from __future__ import annotations

import os
import pathlib
import shlex
import shutil
import subprocess
import time
from typing import Optional

from .manifest import SealError, sha256_of_file


_WIN_DRIVE_RE = __import__("re").compile(r"^([A-Za-z]):[/\\](.*)$")


def to_msys_path(p: str) -> str:
    """Translate Windows-style remote path to MSYS-style for rsync.

    rsync running under msys64 on Windows expects POSIX-form paths:
      ``C:/sealed/jobs``  →  ``/c/sealed/jobs``
      ``C:\\sealed\\jobs`` →  ``/c/sealed/jobs``

    Already-POSIX paths are returned unchanged.
    """
    m = _WIN_DRIVE_RE.match(p)
    if not m:
        return p.replace("\\", "/")
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return f"/{drive}/{rest}"


def _find_rsync() -> str:
    for candidate in ("/opt/homebrew/bin/rsync", "/usr/local/bin/rsync"):
        if os.path.isfile(candidate):
            return candidate
    sys_rsync = shutil.which("rsync")
    if sys_rsync:
        return sys_rsync
    raise SealError("no rsync binary found on PATH; install GNU rsync (brew install rsync)")


try:
    RSYNC_BIN = _find_rsync()
except SealError:
    RSYNC_BIN = "rsync"  # HTTP-only installations do not require rsync at import time

# Shared SSH ControlMaster socket dir. Multiplexing lets a job's
# push/spawn/poll/pull reuse ONE connection per host instead of opening a fresh
# SSH connection each time — which (with submit_many's per-host semaphore) keeps
# the fleet from flooding a host's sshd unauthenticated-connection slots
# (MaxStartups). %C is a hash of (localhost, remotehost, port, user) — unique
# per connection, no path-special chars to escape in rsync --rsh.
_CM_DIR = pathlib.Path.home() / ".ssh" / "cm"
_CM_PATH = str(_CM_DIR / "v2-%C")
MAX_ATTEMPTS = 3


def _run(cmd: list[str], *, timeout: int, stream: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess and return CompletedProcess. Caller checks rc."""
    if stream:
        return subprocess.run(cmd, text=True, timeout=timeout)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _retrying(cmd: list[str], *, timeout: int, label: str, stream: bool = False) -> None:
    """Run cmd with up to MAX_ATTEMPTS retries on non-zero exit. Raises
    SealError with the final stderr if all attempts fail."""
    last_err = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = _run(cmd, timeout=timeout, stream=stream)
        except subprocess.TimeoutExpired as e:
            last_err = f"timeout after {timeout}s on attempt {attempt}"
            continue
        if r.returncode == 0:
            return
        stdout = r.stdout or ""
        stderr = r.stderr or ""
        last_err = (
            f"attempt {attempt}/{MAX_ATTEMPTS} rc={r.returncode}\n"
            f"  stdout: {stdout[:400]}\n"
            f"  stderr: {stderr[:400]}"
        )
        if attempt < MAX_ATTEMPTS:
            time.sleep(2 ** attempt)
    raise SealError(f"{label} failed:\n{last_err}")


def _route_opts(host_alias: str) -> list[str]:
    """LAN-first routing opts (config-driven; Tailscale backup; lib/routing.py).
    No-op for hosts without a reachable lan_host, or on any import error."""
    try:
        from lib import routing
        return routing.ssh_route_opts(host_alias)
    except Exception:
        return []


def _ssh_args(host_alias: str, rsync_path: Optional[str]) -> list[str]:
    """Build the ssh args for rsync --rsh (and direct ssh).

    Uses ControlMaster multiplexing so a job's push/spawn/poll/pull reuse ONE
    connection per host (flood control — see _CM_PATH). The remote work is
    spawned DETACHED (launcher.py), so it survives the master closing.
    """
    _CM_DIR.mkdir(parents=True, exist_ok=True)
    args = ["ssh",
            "-o", "ControlMaster=auto",
            "-o", f"ControlPath={_CM_PATH}",
            "-o", "ControlPersist=30",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
            "-o", "ConnectTimeout=30"]
    args += _route_opts(host_alias)
    return args


def _remote_parent(remote_path: str) -> str:
    p = remote_path.replace("\\", "/").rstrip("/")
    if "/" not in p:
        return "."
    return p.rsplit("/", 1)[0]


def _mkdir_remote(host_alias: str, remote_dir: str, *, platform: str = "windows", timeout: int = 30) -> None:
    if platform in {"linux", "macos"}:
        r = remote_run_posix_retrying(
            host_alias=host_alias, script='mkdir -p -- "$1"', args=[remote_dir],
            timeout=timeout, label=f"mkdir {remote_dir}",
        )
        if r.returncode != 0:
            raise SealError(f"cannot create {remote_dir} on {host_alias}: {r.stderr[:200]}")
        return
    safe_remote = remote_dir.replace("'", "''")
    mkdir_ps = f"New-Item -ItemType Directory -Force -Path '{safe_remote}' | Out-Null"
    r = remote_run_retrying(
        host_alias=host_alias, powershell_script=mkdir_ps,
        timeout=timeout, label=f"mkdir {remote_dir}",
    )
    if r.returncode != 0:
        raise SealError(
            f"cannot create {remote_dir} on {host_alias}: {r.stderr[:200]}"
        )


def push_seal(
    *,
    seal_path_local: pathlib.Path | str,
    host_alias: str,
    remote_workdir: str,
    rsync_path: Optional[str] = None,
    platform: str = "windows",
    timeout: int = 7200,
    force: bool = False,
) -> str:
    """rsync a single sealed archive to ``host_alias:<remote_workdir>/``.

    Idempotent: reuse requires matching size AND SHA-256. Every new transfer
    is hash-checked remotely before return. Set ``force=True`` to retransmit.

    Returns the remote absolute path of the seal.
    """
    seal_path_local = pathlib.Path(seal_path_local).resolve()
    if not seal_path_local.is_file():
        raise SealError(f"push_seal: local seal {seal_path_local} missing")
    remote_workdir = remote_workdir.rstrip("/\\")
    # Translate Windows-style remote_workdir to MSYS path for rsync wire,
    # but keep the Windows-style path as the return value (PowerShell tar
    # and Get-ChildItem etc. all want Windows paths).
    remote_path_win = f"{remote_workdir}/{seal_path_local.name}".replace("\\", "/")
    wire_dir = to_msys_path(remote_workdir) if platform == "windows" else remote_workdir
    remote_path_rsync = f"{wire_dir}/{seal_path_local.name}"

    # rsync does not auto-create parent dirs on the remote. Use a single
    # PowerShell call (RETRYING — transient SSH failures here should NOT
    # fail the whole submit) to mkdir the destination.
    _mkdir_remote(host_alias, remote_workdir, platform=platform, timeout=30)

    expected_hash = sha256_of_file(seal_path_local)
    if not force:
        local_size = seal_path_local.stat().st_size
        remote_size = remote_file_size(host_alias, remote_path_win, platform=platform, timeout=30)
        if remote_size == local_size and remote_file_sha256(
                host_alias, remote_path_win, platform=platform) == expected_hash:
            return remote_path_win

    ssh_cmd = " ".join(shlex.quote(a) for a in _ssh_args(host_alias, rsync_path))

    cmd = [
        RSYNC_BIN,
        "-a",                       # archive (preserves perms/times)
        "--checksum",               # equal sizes/mtimes do not prove identical bytes
        "--partial", "--partial-dir=.rsync-partial",
        "--info=progress2,stats2",
        "--rsh", ssh_cmd,
    ]
    if rsync_path:
        cmd += ["--rsync-path", rsync_path]
    cmd += [str(seal_path_local), f"{host_alias}:{remote_path_rsync}"]

    _retrying(cmd, timeout=timeout, label=f"push_seal {seal_path_local.name}")
    if remote_file_sha256(host_alias, remote_path_win, platform=platform) != expected_hash:
        raise SealError("remote seal SHA-256 differs after transfer")
    return remote_path_win


def remote_file_sha256(host_alias, remote_path, *, platform="windows", timeout=600):
    if platform in {"linux", "macos"}:
        result = remote_run_posix_retrying(
            host_alias=host_alias,
            script='if command -v sha256sum >/dev/null 2>&1; then sha256sum -- "$1"; else shasum -a 256 -- "$1"; fi',
            args=[remote_path], timeout=timeout, label="hash remote artifact")
    else:
        safe = remote_path.replace("'", "''")
        result = remote_run_retrying(host_alias=host_alias,
            powershell_script=f"(Get-FileHash -LiteralPath '{safe}' -Algorithm SHA256).Hash",
            timeout=timeout, label="hash remote artifact")
    words = (result.stdout or "").lower().split()
    if result.returncode == 0 and words and __import__("re").fullmatch(r"[0-9a-f]{64}", words[0]):
        return words[0]
    return None


def push_path(
    *,
    local_path: pathlib.Path | str,
    host_alias: str,
    remote_path: str,
    rsync_path: Optional[str] = None,
    platform: str = "windows",
    timeout: int = 7200,
    force: bool = False,
    stream: bool = False,
    atomic_file: bool = True,
) -> str:
    """rsync a large local file/dir to an explicit remote path.

    This is intentionally separate from ``push_seal``: cache .mat files
    can be tens of GB and must be pre-staged with resume/progress instead
    of embedded inside sealed job archives.
    """
    local = pathlib.Path(local_path).resolve()
    if not local.exists():
        raise SealError(f"push_path: local path missing: {local}")
    remote_path = remote_path.replace("\\", "/")
    _mkdir_remote(host_alias, _remote_parent(remote_path), platform=platform, timeout=30)

    transfer_path = remote_path
    partial_path = f"{remote_path}.partial" if local.is_file() and atomic_file else remote_path
    if local.is_file() and not force:
        local_size = local.stat().st_size
        remote_size = remote_file_size(host_alias, remote_path, platform=platform, timeout=30)
        if remote_size == local_size:
            return remote_path
        partial_size = remote_file_size(host_alias, partial_path, platform=platform, timeout=30)
        if partial_size == local_size:
            _promote_remote_partial(
                host_alias=host_alias,
                partial_path=partial_path,
                final_path=remote_path,
                platform=platform,
            )
            return remote_path
        transfer_path = partial_path
    elif local.is_file() and atomic_file:
        transfer_path = partial_path

    ssh_cmd = " ".join(shlex.quote(a) for a in _ssh_args(host_alias, rsync_path))
    cmd = [
        RSYNC_BIN,
        "-a",
        "--partial",
        "--info=progress2,stats2",
        "--rsh", ssh_cmd,
    ]
    if local.is_file() and atomic_file:
        # Write to a visible *.partial file so operators can inspect
        # remote byte growth while the transfer is running. The final
        # cache path appears only after byte-size validation + rename.
        cmd.append("--inplace")
    else:
        cmd.append("--partial-dir=.rsync-partial")
    if rsync_path:
        cmd += ["--rsync-path", rsync_path]
    src_arg = str(local)
    if local.is_dir():
        src_arg = src_arg.rstrip("/") + "/"
    wire_path = to_msys_path(transfer_path) if platform == "windows" else transfer_path
    cmd += [src_arg, f"{host_alias}:{wire_path}"]
    _retrying(cmd, timeout=timeout, label=f"push_path {local.name}", stream=stream)
    if local.is_file() and atomic_file:
        expected_size = local.stat().st_size
        got_size = remote_file_size(host_alias, partial_path, platform=platform, timeout=30)
        if got_size != expected_size:
            raise SealError(
                f"push_path {local.name}: partial size mismatch after rsync "
                f"({got_size} != {expected_size}) at {partial_path}"
            )
        _promote_remote_partial(
            host_alias=host_alias,
            partial_path=partial_path,
            final_path=remote_path,
            platform=platform,
        )
    return remote_path


def _promote_remote_partial(*, host_alias: str, partial_path: str,
                            final_path: str, platform: str = "windows") -> None:
    if platform in {"linux", "macos"}:
        r = remote_run_posix_retrying(
            host_alias=host_alias,
            script='test -f "$1" && mkdir -p -- "$(dirname -- "$2")" && mv -f -- "$1" "$2"',
            args=[partial_path, final_path], timeout=60,
            label=f"promote {partial_path}",
        )
        if r.returncode != 0:
            raise SealError(f"promote partial failed for {partial_path}: {r.stderr[:400]}")
        return
    safe_src = partial_path.replace("'", "''")
    safe_dst = final_path.replace("'", "''")
    ps = (
        f"$src = '{safe_src}'; $dst = '{safe_dst}'; "
        "if (!(Test-Path -LiteralPath $src)) { throw \"partial missing: $src\" }; "
        "$parent = Split-Path -Parent $dst; "
        "New-Item -ItemType Directory -Force -Path $parent | Out-Null; "
        "Move-Item -Force -LiteralPath $src -Destination $dst"
    )
    r = remote_run_retrying(
        host_alias=host_alias,
        powershell_script=ps,
        timeout=60,
        label=f"promote {partial_path}",
    )
    if r.returncode != 0:
        raise SealError(
            f"promote partial failed for {partial_path}: {r.stderr[:400]}"
        )


def pull_path(
    *,
    host_alias: str,
    remote_path: str,
    local_dest: pathlib.Path | str,
    rsync_path: Optional[str] = None,
    platform: str = "windows",
    timeout: int = 7200,
    stream: bool = False,
) -> pathlib.Path:
    """rsync a remote file/glob to a local destination with resume/progress.

    ``remote_path`` is an absolute remote path (Windows or MSYS form).
    ``local_dest`` may be a directory or exact output filename; callers
    should create the right parent/dir before invoking.
    """
    dest = pathlib.Path(local_dest).resolve()
    ssh_cmd = " ".join(shlex.quote(a) for a in _ssh_args(host_alias, rsync_path))
    cmd = [
        RSYNC_BIN,
        "-a",
        "--partial", "--partial-dir=.rsync-partial",
        "--info=progress2,stats2",
        "--rsh", ssh_cmd,
    ]
    if rsync_path:
        cmd += ["--rsync-path", rsync_path]
    dest_arg = str(dest)
    if dest.is_dir():
        dest_arg = dest_arg.rstrip("/") + "/"
    wire_path = to_msys_path(remote_path) if platform == "windows" else remote_path
    cmd += [f"{host_alias}:{wire_path}", dest_arg]
    _retrying(cmd, timeout=timeout, label=f"pull_path {remote_path}", stream=stream)
    return dest


def pull_result(
    *,
    remote_path: str,
    host_alias: str,
    local_dest: pathlib.Path | str,
    rsync_path: Optional[str] = None,
    platform: str = "windows",
    timeout: int = 1800,
) -> pathlib.Path:
    """rsync a single result archive back from ``host_alias:remote_path``.

    Returns the local path to the pulled archive.
    """
    local_dest = pathlib.Path(local_dest).resolve()
    local_dest.parent.mkdir(parents=True, exist_ok=True)
    ssh_cmd = " ".join(shlex.quote(a) for a in _ssh_args(host_alias, rsync_path))

    cmd = [
        RSYNC_BIN,
        "-az",                      # archive + compress (result is small, mostly text)
        "--partial", "--partial-dir=.rsync-partial",
        "--info=stats2",
        "--rsh", ssh_cmd,
    ]
    if rsync_path:
        cmd += ["--rsync-path", rsync_path]
    remote_rsync = to_msys_path(remote_path) if platform == "windows" else remote_path
    cmd += [f"{host_alias}:{remote_rsync}", str(local_dest)]

    _retrying(cmd, timeout=timeout, label=f"pull_result {pathlib.Path(remote_path).name}")
    return local_dest


def remote_remove(
    *,
    host_alias: str,
    remote_path: str,
    platform: str = "windows",
    timeout: int = 60,
) -> None:
    """Best-effort recursive delete of ``remote_path`` on ``host_alias``.

    Used by submit cleanup. Idempotent (no-op if missing). Retried on
    transient SSH failures so a network blip doesn't leave 2.3 GB of
    seal lying around on the remote. Final failure is swallowed —
    cleanup is best-effort and the job's success status doesn't depend
    on it.
    """
    # SAFETY GUARD: this is a `Remove-Item -Recurse -Force` (rm -rf-class)
    # primitive. Every legitimate caller builds remote_path as
    # <root>/<job_id|batch|cohort>/... — so a valid target has >= 3 path segments
    # and is never a bare drive root. Refuse anything shallower so a misconfigured
    # remote_workdir or empty job_id can never recursively wipe `C:/` or a home dir.
    _norm = remote_path.replace("\\", "/").rstrip("/")
    _segs = [s for s in _norm.split("/") if s and s not in (".", "..")]
    if not _norm or _norm.endswith(":") or len(_segs) < 3:
        raise SealError(f"remote_remove refusing unsafe shallow path: {remote_path!r}")
    if platform in {"linux", "macos"}:
        try:
            remote_run_posix_retrying(
                host_alias=host_alias,
                script='test ! -e "$1" || rm -rf -- "$1"',
                args=[remote_path], timeout=timeout, label=f"remote_remove {remote_path}",
            )
        except (SealError, subprocess.TimeoutExpired):
            pass
        return
    ps = (
        f"$p = '{remote_path.replace(chr(39), chr(39)*2)}'; "
        f"if (Test-Path -LiteralPath $p) {{ Remove-Item -Recurse -Force -LiteralPath $p -EA SilentlyContinue }}"
    )
    try:
        remote_run_retrying(
            host_alias=host_alias, powershell_script=ps,
            timeout=timeout, label=f"remote_remove {remote_path}",
        )
    except (SealError, subprocess.TimeoutExpired):
        # Best-effort: cleanup failure is logged at the caller layer if
        # they care. Don't fail the submit.
        pass


def remote_run(
    *,
    host_alias: str,
    powershell_script: str,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Run a PowerShell snippet on ``host_alias`` (base64-encoded for safety).

    Returns the CompletedProcess so callers can inspect rc/stdout/stderr.

    This is the SINGLE-SHOT variant. Use ``remote_run_retrying`` for any
    operation where a transient SSH glitch should not fail the call.
    """
    import base64
    enc = base64.b64encode(powershell_script.encode("utf-16-le")).decode()
    cmd = ["ssh", "-o", "ConnectTimeout=15",
           "-o", "ControlMaster=auto", "-o", f"ControlPath={_CM_PATH}",
           "-o", "ControlPersist=30",
           *_route_opts(host_alias),
           host_alias, f"powershell -NoProfile -EncodedCommand {enc}"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def remote_run_posix(
    *, host_alias: str, script: str, args: Optional[list[str]] = None, timeout: int = 30
) -> subprocess.CompletedProcess:
    """Run a POSIX shell script over SSH without interpolating path values.

    Values are passed as positional arguments to ``sh -s --`` and the script
    itself is delivered on stdin. This avoids nested shell quoting and works
    with the stock shell on Linux and macOS.
    """
    remote_command = "sh -s --"
    if args:
        remote_command += " " + " ".join(shlex.quote(str(arg)) for arg in args)
    command = [*_ssh_args(host_alias, None), host_alias, remote_command]
    return subprocess.run(
        command, input=script, capture_output=True, text=True, timeout=timeout
    )


# Exit codes that indicate the SSH transport itself failed (not the
# remote command). Worth retrying because the next attempt may succeed.
# 255 — ssh exits 255 for any of: connection refused, host unreachable,
#       broken pipe, auth failure (auth is permanent but rare in our use
#       case; we accept retrying it as a benign over-retry).
_TRANSIENT_SSH_RCS = frozenset([255])

# Substrings in stderr that strongly indicate a transport-level glitch
# (network blip, mux race, server-side reset) and not a command error.
_TRANSIENT_STDERR_HINTS = (
    "Connection timed out",
    "Connection reset",
    "Connection refused",
    "Connection closed",
    "kex_exchange_identification",
    "ssh: connect to host",
    "Broken pipe",
    "Timeout, server",
    "Connection to ",
)


def _is_transient_ssh_failure(rc: int, stderr: str) -> bool:
    """Heuristic: did this look like an SSH transport-layer hiccup
    rather than a real remote-command error?"""
    if rc in _TRANSIENT_SSH_RCS:
        return True
    if stderr and any(h in stderr for h in _TRANSIENT_STDERR_HINTS):
        return True
    return False


def remote_run_retrying(
    *,
    host_alias: str,
    powershell_script: str,
    timeout: int = 30,
    max_attempts: int = MAX_ATTEMPTS,
    label: str = "remote_run",
) -> subprocess.CompletedProcess:
    """Run a PowerShell snippet on ``host_alias`` with retries on
    transient SSH-transport failures.

    Distinguishes ``rc != 0`` caused by the remote command (returned
    as-is — caller decides what to do) from ``rc != 0`` caused by SSH
    itself (rc 255 or known network-glitch stderr strings), which is
    retried with exponential backoff.

    Also retries ``subprocess.TimeoutExpired`` — the prior attempt may
    have hung on a mux race or stuck network buffer; the next attempt
    typically goes through quickly.

    Returns the CompletedProcess of the first attempt that either
    (a) succeeded, or (b) failed with a non-transport-level error.
    Raises ``SealError`` only when ALL attempts hit transport-level
    failures.
    """
    last_repr = ""
    for attempt in range(1, max_attempts + 1):
        try:
            r = remote_run(
                host_alias=host_alias,
                powershell_script=powershell_script,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            last_repr = (
                f"attempt {attempt}/{max_attempts}: subprocess timeout after {timeout}s"
            )
            if attempt < max_attempts:
                time.sleep(2 ** attempt)
            continue
        if r.returncode == 0:
            return r
        if not _is_transient_ssh_failure(r.returncode, r.stderr or ""):
            # The command itself failed — surface to the caller. Retrying
            # would just hammer the host with the same broken command.
            return r
        last_repr = (
            f"attempt {attempt}/{max_attempts} rc={r.returncode}\n"
            f"  stdout: {(r.stdout or '')[:300]}\n  stderr: {(r.stderr or '')[:300]}"
        )
        if attempt < max_attempts:
            time.sleep(2 ** attempt)
    raise SealError(f"{label}: all {max_attempts} ssh attempts hit transport errors:\n{last_repr}")


def remote_run_posix_retrying(
    *, host_alias: str, script: str, args: Optional[list[str]] = None,
    timeout: int = 30, max_attempts: int = MAX_ATTEMPTS, label: str = "remote_run_posix",
) -> subprocess.CompletedProcess:
    """POSIX counterpart of :func:`remote_run_retrying`."""
    last_repr = ""
    for attempt in range(1, max_attempts + 1):
        try:
            result = remote_run_posix(
                host_alias=host_alias, script=script, args=args, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            last_repr = f"attempt {attempt}/{max_attempts}: timeout after {timeout}s"
        else:
            if result.returncode == 0 or not _is_transient_ssh_failure(
                result.returncode, result.stderr or ""
            ):
                return result
            last_repr = (
                f"attempt {attempt}/{max_attempts} rc={result.returncode}\n"
                f"  stdout: {(result.stdout or '')[:300]}\n"
                f"  stderr: {(result.stderr or '')[:300]}"
            )
        if attempt < max_attempts:
            time.sleep(2 ** attempt)
    raise SealError(f"{label}: all {max_attempts} ssh attempts hit transport errors:\n{last_repr}")


def remote_path_exists(
    host_alias: str, remote_path: str, *, platform: str = "windows", timeout: int = 30
) -> bool:
    """True iff ``remote_path`` exists on ``host_alias``.

    Wraps remote_run_retrying so a network blip during the check doesn't
    cause a false "missing" answer (which would trigger a redundant
    push/extract). Returns False on definitive command errors.
    """
    if platform in {"linux", "macos"}:
        try:
            r = remote_run_posix_retrying(
                host_alias=host_alias,
                script='if test -e "$1"; then printf YES; else printf NO; fi',
                args=[remote_path], timeout=timeout, label=f"path_exists {remote_path}",
            )
        except SealError:
            return False
        return r.returncode == 0 and "YES" in (r.stdout or "")
    safe = remote_path.replace("'", "''")
    ps = f"if (Test-Path -LiteralPath '{safe}') {{ Write-Output 'YES' }} else {{ Write-Output 'NO' }}"
    try:
        r = remote_run_retrying(
            host_alias=host_alias, powershell_script=ps,
            timeout=timeout, label=f"path_exists {remote_path}",
        )
    except SealError:
        return False
    return r.returncode == 0 and "YES" in (r.stdout or "")


def remote_file_size(
    host_alias: str, remote_path: str, *, platform: str = "windows", timeout: int = 30
) -> Optional[int]:
    """Return the size of ``remote_path`` in bytes, or None if missing
    / unreachable. Used by push_seal to skip re-uploading an identical
    file."""
    if platform in {"linux", "macos"}:
        try:
            r = remote_run_posix_retrying(
                host_alias=host_alias,
                script='test -f "$1" && wc -c < "$1"', args=[remote_path],
                timeout=timeout, label=f"file_size {remote_path}",
            )
        except SealError:
            return None
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        try:
            return int((r.stdout or "").strip().splitlines()[0].strip())
        except (ValueError, IndexError):
            return None
    safe = remote_path.replace("'", "''")
    ps = (
        f"$p = '{safe}'; "
        "if (Test-Path -LiteralPath $p) { Write-Output ((Get-Item -LiteralPath $p).Length) }"
    )
    try:
        r = remote_run_retrying(
            host_alias=host_alias, powershell_script=ps,
            timeout=timeout, label=f"file_size {remote_path}",
        )
    except SealError:
        return None
    if r.returncode != 0:
        return None
    out = (r.stdout or "").strip()
    if not out:
        return None
    try:
        return int(out.splitlines()[0])
    except (ValueError, IndexError):
        return None
