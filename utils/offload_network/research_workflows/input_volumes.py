"""Attempt-owned, byte-verified Docker volumes for immutable workflow inputs.

The helper runs only this controller's code, never uploaded code. The eventual
job receives read-only volumes at the same paths as the default bind transport.
Volumes are disposable working copies; authenticated objects remain retained.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import time

from lib.live_files import live_tree_bytes
from offload_service.core import CapacityError

from .common import atomic, load, sha


OWNER_LABEL = "marketmaker.offload.worker"
ATTEMPT_LABEL = "marketmaker.offload.attempt"


class _StageStopped(RuntimeError):
    pass


HELPER = r'''
import hashlib, json, os, pathlib, stat
expected = json.loads(pathlib.Path('/expected.json').read_text())
results = []
def normalize(path):
    info = path.lstat()
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise ValueError('non-regular staged input')
    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
        raise ValueError('hard-linked staged input')
    # Docker cp can retain host ownership and private file modes. This helper
    # owns only disposable volume copies and has CHOWN for this normalization.
    os.chown(path, os.geteuid(), os.getegid(), follow_symlinks=False)
    path.chmod(0o755 if stat.S_ISDIR(info.st_mode) else 0o644)
for item in expected:
    root = pathlib.Path('/stage') / str(item['index'])
    normalize(root)
    disk = os.statvfs(root)
    names = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = pathlib.Path(directory) / name
            normalize(path)
            mode = path.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError('non-regular staged input')
            if stat.S_ISREG(mode):
                if path.stat().st_nlink != 1:
                    raise ValueError('hard-linked staged input')
                names.add(path.relative_to(root).as_posix())
    result = {'index': item['index'], 'free_bytes': disk.f_bavail * disk.f_frsize,
              'files': len(names), 'bytes': 0, 'status': 'EMPTY'}
    if names:
        if names != set(item['files']):
            raise ValueError('staged file inventory differs')
        for name, reference in sorted(item['files'].items()):
            path = root / name
            if path.stat().st_size != reference['bytes']:
                raise ValueError('staged file size differs: ' + name)
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(4 << 20), b''):
                    digest.update(chunk)
            if digest.hexdigest() != reference['sha256']:
                raise ValueError('staged file hash differs: ' + name)
            result['bytes'] += reference['bytes']
        result['status'] = 'VERIFIED'
        # Object identities bind bytes, not host permissions. Make every
        # directory traversable by the eventual unprivileged job UID.
        for directory, dirs, files in os.walk(root, topdown=False):
            for name in files:
                (pathlib.Path(directory) / name).chmod(0o444)
            pathlib.Path(directory).chmod(0o555)
    results.append(result)
print(json.dumps({'objects': results}))
'''


def owner_id(worker):
    return hashlib.sha256(str(worker.root).encode()).hexdigest()


def directory(worker, attempt):
    if not re.fullmatch(r"offload-[0-9a-f]{32}", attempt):
        raise ValueError("invalid persisted container attempt name")
    return worker.root / "workflow_input_transports" / attempt


def _checked_volume(worker, name, attempt):
    expected_name = re.fullmatch(re.escape(attempt) + r"-input-[0-9]+", name)
    if not expected_name:
        raise ValueError("unexpected attempt volume name")
    item = json.loads(worker._docker("volume", "inspect", name))[0]
    labels = item.get("Labels") or {}
    if labels.get(OWNER_LABEL) != owner_id(worker) or labels.get(ATTEMPT_LABEL) != attempt:
        raise ValueError("input volume ownership differs")


def cleanup(worker, attempt):
    """Recover by trusted Docker labels even if a process died before a receipt."""
    record_dir = directory(worker, attempt)
    names = worker._docker("volume", "ls", "--quiet", "--filter",
        f"label={OWNER_LABEL}={owner_id(worker)}", "--filter",
        f"label={ATTEMPT_LABEL}={attempt}").splitlines()
    for name in names:
        _checked_volume(worker, name, attempt)
        worker._docker("volume", "rm", name)
    path = record_dir / "TRANSPORT.json"
    if path.exists():
        row = load(path)
        row["owned_volumes_removed"] = True
        atomic(path, row)


def reserve_inputs(worker, attempt, required, reserve, row):
    # Claim before releasing this lock. Active attempts retain the reservation
    # until their volume cleanup receipt is written, including on failure.
    with worker.input_volume_lock:
        with worker.db_lock:
            attempts = [item[0] for item in worker.db.execute(
                "SELECT attempt FROM jobs WHERE state='running' AND attempt IS NOT NULL")]
        reserved = 0
        for other in attempts:
            path = directory(worker, other) / "TRANSPORT.json"
            if other != attempt and path.exists():
                previous = load(path)
                if not previous.get("owned_volumes_removed", False):
                    reserved += previous.get("reserved_bytes", 0)
        if live_tree_bytes(worker.root) + reserved + required > worker.max_store_mb * (1 << 20):
            raise CapacityError("Docker input copies exceed worker storage budget")
        if shutil.disk_usage(worker.root).free < required + reserve:
            raise CapacityError("insufficient host space for Docker input volumes")
        row["reserved_bytes"] = required
        atomic(directory(worker, attempt) / "TRANSPORT.json", row)


def stage(worker, work, attempt, payload, references):
    """Verify host objects, copy bounded inputs, rehash their Docker-volume bytes."""
    started = time.monotonic()
    deadline = started + min(float(payload["template"]["timeout_s"]), 1800)
    t = payload["template"]
    owner = owner_id(worker)
    record_dir = directory(worker, attempt)
    record_dir.mkdir(parents=True, exist_ok=False)
    references = list(references)
    objects, expected, volume_names, indices = [], [], [], {}
    row = {"schema": "marketmaker.workflow_input_transport.v1", "transport": "docker-volume",
           "attempt": attempt, "owner": owner, "status": "PREPARING", "objects": [],
           "read_only_job_mounts": True, "owned_volumes_removed": False,
           "helper_capabilities": ["CHOWN"], "job_capabilities": []}
    atomic(record_dir / "TRANSPORT.json", row)

    def check_stopped():
        if worker.stop.is_set():
            raise _StageStopped("worker stopping during input staging")
        with worker.db_lock:
            current = worker.db.execute("SELECT cancel FROM jobs WHERE attempt=?", (attempt,)).fetchone()
        if current and current[0]:
            raise _StageStopped("cancellation requested during input staging")

    def call(*args):
        check_stopped()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("input volume staging exceeded its time budget")
        result = subprocess.run(["docker", *args], capture_output=True, text=True,
                                timeout=remaining)
        check_stopped()
        if result.returncode:
            raise RuntimeError("Docker input staging failed: " + result.stderr[-1000:])
        return result.stdout.strip()

    try:
        for identity, target in references:
            if identity in indices:
                row["objects"][indices[identity]]["targets"].append(target)
                continue
            index = len(objects)
            indices[identity] = index
            root, manifest = worker.workflows.objects.get(identity)
            objects.append((root / "data", target))
            expected.append({"index": index, "files": manifest["files"]})
            volume_names.append(attempt + "-input-" + str(index))
            row["objects"].append({"object_sha256": identity, "target": target, "targets": [target],
                "files": len(manifest["files"]),
                "bytes": sum(r["bytes"] for r in manifest["files"].values())})
        required = sum(item["bytes"] for item in row["objects"])
        # The scheduler charges each declared mount against its logical input
        # bound. Preserve that bound while reserving physical copied bytes once
        # per immutable identity. All aliases subsequently mount the same
        # verified volume read-only; there is no shared writable input.
        row["logical_input_bytes"] = sum(row["objects"][indices[identity]]["bytes"]
                                         for identity, _ in references)
        if row["logical_input_bytes"] > t["max_input_mb"] * (1 << 20):
            raise CapacityError("workflow volume inputs exceed per-job input budget")
        reserve = (worker.min_free_mb + t["max_work_mb"]) * (1 << 20)
        reserve_inputs(worker, attempt, required, reserve, row)
        atomic(record_dir / "EXPECTED.json", expected)
        row["expected_manifest_sha256"] = sha(record_dir / "EXPECTED.json")
        row["host_verification_seconds"] = time.monotonic() - started
        for name in volume_names:
            call("volume", "create", "--label", f"{OWNER_LABEL}={owner}",
                 "--label", f"{ATTEMPT_LABEL}={attempt}", name)
            _checked_volume(worker, name, attempt)
        helper = ["container", "create", "--name", attempt, "--pull=never",
            "--network=none", "--read-only", "--cap-drop=ALL", "--cap-add=CHOWN",
            "--security-opt=no-new-privileges", "--user", "0:0", "--init",
            "--memory", f"{int(t['memory_mb'])}m", "--memory-swap", f"{int(t['memory_mb'])}m",
            "--cpus", str(t["cpus"]), "--pids-limit", str(int(t["pids"])),
            "--log-driver=none", "--mount",
            f"type=bind,source={record_dir / 'EXPECTED.json'},target=/expected.json,readonly"]
        for index, name in enumerate(volume_names):
            helper += ["--mount", f"type=volume,source={name},target=/stage/{index}"]
        helper += ["--entrypoint", "python", payload["image_id"], "-I", "-c", HELPER]
        call(*helper)
        before = json.loads(call("container", "start", "--attach", attempt))
        if (len(before["objects"]) != len(expected)
                or any(item["status"] != "EMPTY" for item in before["objects"])):
            raise ValueError("new input volumes are not empty")
        if min(item["free_bytes"] for item in before["objects"]) < required + reserve:
            raise CapacityError("insufficient Docker volume space for inputs and reserve")
        row["docker_free_bytes_before"] = min(item["free_bytes"] for item in before["objects"])
        copied = time.monotonic()
        for index, (source, _) in enumerate(objects):
            call("cp", str(source) + os.sep + ".", attempt + ":/stage/" + str(index))
        row["copy_seconds"] = time.monotonic() - copied
        checked = time.monotonic()
        returned = json.loads(call("container", "start", "--attach", attempt))
        if (len(returned["objects"]) != len(expected)
                or any(actual["index"] != i or actual["status"] != "VERIFIED"
                       or actual["files"] != row["objects"][i]["files"]
                       or actual["bytes"] != row["objects"][i]["bytes"]
                       for i, actual in enumerate(returned["objects"]))):
            raise ValueError("Docker volume verification did not cover every input")
        row["volume_verification_seconds"] = time.monotonic() - checked
        # Remove only the trusted staging helper. The same persisted attempt name
        # is then used by the normal read-only job container and crash recovery.
        call("container", "rm", attempt)
        row["status"] = "VERIFIED"
        return [(volume_names[indices[identity]], target) for identity, target in references]
    except _StageStopped as exc:
        # The caller checks the durable cancellation/stop flag immediately after
        # docker_command returns, before creating a workload container. Let that
        # existing path preserve cancelled versus interrupted state and cleanup.
        row["status"] = "STOPPED"
        row["error"] = str(exc)
        return []
    except BaseException as exc:
        row["status"] = "FAILED"
        row["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        row["elapsed_seconds"] = time.monotonic() - started
        atomic(record_dir / "TRANSPORT.json", row)
