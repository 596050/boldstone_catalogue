"""Explicit, recoverable retention of completed local jobs; no model assumptions.

Uses the normal local-run receipt, exclusive worker ownership lock, terminal
queue records, verified collection and Docker mount identities. No cleanup is
implicit in job execution, and no receipt is interpreted as authority to stop a
worker. Archive bytes remain available for complete restore.
"""

from contextlib import closing
import ctypes
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from lib.file_lock import file_lock

from .client import verify_collection, verify_object
from .common import atomic, digest, fields, hash_id, inventory, load, no_links, positive, rel, sha, sync_directory, verify_tree
from .compressed import compact_object, verify_archive
from .objects import extract_object, pack
from .spec import TERMINAL

SCHEMA = "marketmaker.local_retention_request.v1"


def process_alive(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("positive recorded worker PID required")
    if sys.platform == "win32":
        # os.kill(pid, 0) is not a portable read-only Windows liveness probe.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # unknown/access-denied stays live
        try:
            code = ctypes.c_uint32()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def container_mounts():
    process = subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True, check=True, timeout=30)
    ids = process.stdout.split()
    if not ids:
        return []
    inspected = subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True, check=True, timeout=30)
    return [{"id": row["Id"], "sources": [mount["Source"] for mount in row["Mounts"]]}
            for row in json.loads(inspected.stdout)]


def validate(request, *, base=None):
    fields(request, {"schema", "local_run", "work_attempts", "objects", "max_bytes", "min_free_bytes"},
           {"schema", "local_run", "work_attempts", "objects", "max_bytes", "min_free_bytes"})
    if request["schema"] != SCHEMA:
        raise ValueError("unsupported retention request")
    for key in ("objects", "work_attempts"):
        if not isinstance(request[key], list) or any(not isinstance(v, str) for v in request[key]) or len(set(request[key])) != len(request[key]):
            raise ValueError("retention targets must be distinct explicit identities")
    if not request["objects"] and not request["work_attempts"]:
        raise ValueError("declare at least one retention target")
    from offload_service.core import ID
    if any(not ID.fullmatch(value) or not value.startswith("offload-") for value in request["work_attempts"]):
        raise ValueError("invalid attempt identity")
    for value in request["objects"]:
        hash_id(value)
    positive(request["max_bytes"], 1 << 40)
    if type(request["min_free_bytes"]) is not int or request["min_free_bytes"] < 0:
        raise ValueError("nonnegative retention reserve required")
    receipt = (Path(base or ".").resolve() / request["local_run"]).absolute()
    if receipt.name != "LOCAL_RUN.json" or receipt.is_symlink() or not receipt.is_file():
        raise ValueError("exact LOCAL_RUN.json receipt required")
    directory = receipt.parent.resolve()
    receipt = directory / receipt.name
    config = load(no_links(directory / "worker.json", directory))
    root = no_links(directory / rel(config["root"]), directory)
    if root == directory or not root.is_dir():
        raise ValueError("retention requires a worker root beneath its local-run directory")
    return receipt, directory, root


def inactive(request, receipt, directory, root):
    record = load(receipt)
    if (record.get("schema") != "marketmaker.local_offload_run.v1" or record.get("backend") != "docker"
            or record.get("status") != "COLLECTED_AND_VERIFIED" or record.get("worker_stopped") is not True
            or record.get("worker_exit_code") != 0 or record.get("forced_worker_stop")
            or process_alive(record["worker_pid"])):
        raise ValueError("verified collection and clean, inactive local worker required")
    returned = no_links(directory / "returned", directory)
    if Path(record["returned"]).absolute() != returned:
        raise ValueError("return receipt belongs to another local directory")
    verified = verify_collection(returned, max_bytes=request["max_bytes"])
    if verified != record["collection"] or not verified["final"]:
        raise ValueError("retained final collection differs")
    database = no_links(root / "jobs.sqlite3", root)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        jobs = db.execute("SELECT id,state,attempt FROM jobs").fetchall()
        nodes = db.execute("SELECT workflow,id,state FROM workflow_nodes").fetchall()
        assignments = db.execute("SELECT workflow,job_id FROM workflow_attempts").fetchall()
    if (not jobs or not nodes or any(row[1] not in TERMINAL for row in jobs)
            or any(row[0] != record["workflow_id"] or row[2] not in TERMINAL for row in nodes)
            or any(row[0] != record["workflow_id"] for row in assignments)
            or {row[0] for row in jobs} - {row[1] for row in assignments}):
        raise ValueError("all local worker jobs must belong to the completed workflow and be terminal")
    if set(request["work_attempts"]) - {row[2] for row in jobs}:
        raise ValueError("requested work is not an owned completed attempt")
    mounts = container_mounts()
    for row in mounts:
        for value in row["sources"]:
            source = Path(value).resolve()
            if source.is_relative_to(root.resolve()) or root.resolve().is_relative_to(source):
                raise ValueError("a retained container can still access the selected worker root")
    return {"local_run_sha256": sha(receipt), "collection": verified, "jobs": jobs,
            "nodes": nodes, "docker_mounts": mounts}


def retain(request, destination=None, *, base=None, execute=False):
    receipt, directory, root = validate(request, base=base)
    limit = request["max_bytes"]
    with file_lock(root / "worker.lock", timeout=0):
        before = inactive(request, receipt, directory, root)
        object_root = no_links(root / "workflows/objects", root)
        for identity in request["objects"]:
            manifest = verify_object(object_root / identity, identity, max_bytes=limit)
            verify_archive(object_root / identity, identity, manifest, max_bytes=limit)
        if destination is not None:
            destination = Path(destination).absolute()
            no_links(destination, destination.parent)
            destination = destination.resolve()
            if (destination == directory or destination.is_relative_to(directory)
                    or directory.is_relative_to(destination) or destination.is_symlink()):
                raise ValueError("recovery directory must be separate from the local worker tree")
        retained = destination / "INTENT.json" if destination else None
        if retained is not None and retained.exists():
            intent = load(no_links(retained, destination))
            if (intent.get("schema") != "marketmaker.local_retention_receipt.v1"
                    or intent["request_sha256"] != digest(request) or intent.get("request") != request
                    or intent["local_run_sha256"] != sha(receipt)
                    or set(intent["work"]) != set(request["work_attempts"])
                    or intent["objects"] != request["objects"]):
                raise ValueError("retention destination belongs to different work")
        else:
            if destination is not None and destination.exists():
                raise ValueError("recovery destination must be fresh or contain this request's INTENT.json")
            work = {key: inventory(no_links(root / "work" / key, root), max_bytes=limit)
                    for key in request["work_attempts"]}
            intent = {"schema": "marketmaker.local_retention_receipt.v1", "request_sha256": digest(request),
                      "local_run_sha256": sha(receipt), "local_run": str(receipt), "work": work,
                      "objects": request["objects"], "request": request,
                      "logical_work_bytes": sum(row["bytes"] for files in work.values() for row in files.values()),
                      "physical_bytes_reclaimed": None, "automatic_delete": False}
        if not execute:
            return {**intent, "status": "INSPECTED_NOT_EXECUTED", "ownership": before}
        if destination is None:
            raise ValueError("execution requires a separate recovery directory")
        destination.mkdir(parents=True, exist_ok=True)
        if not retained.exists():
            atomic(retained, intent)
        completed = no_links(destination / "COMPLETED.json", destination)
        previous = load(completed) if completed.exists() else None
        if previous is not None:
            if (any(previous.get(key) != value for key, value in intent.items())
                    or previous.get("status") != "COMPLETED"
                    or [row["object_sha256"] for row in previous["compacted_objects"]] != request["objects"]):
                raise ValueError("completed retention receipt differs from intent")
            if any((root / "work" / key).exists() or (root / "work" / (key + ".retiring")).exists()
                   for key in intent["work"]):
                raise ValueError("completed work targets reappeared; do not reuse the old retention intent")
        archives = destination / "archives"
        no_links(archives, destination)
        archives.mkdir(exist_ok=True)
        for key, files in intent["work"].items():
            original = no_links(root / "work" / key, root)
            parked = no_links(root / "work" / (key + ".retiring"), root)
            archive = no_links(archives / (key + ".tar.gz"), destination)
            marker = no_links(archives / (key + ".json"), destination)
            size = sum(row["bytes"] for row in files.values())
            if not marker.exists():
                if archive.exists():
                    raise ValueError("uncommitted archive retained; use a new recovery destination")
                if shutil.disk_usage(destination).free < request["min_free_bytes"] + 2 * size + (16 << 20):
                    raise ValueError("insufficient reserve for archive and complete restore verification")
                verify_tree(original, files, max_bytes=limit)
                packed = pack(original, archive, max_bytes=limit)
                atomic(marker, {"object_sha256": packed["object_sha256"], "files": files})
            bound = load(marker)
            if bound["files"] != files:
                raise ValueError("retention archive manifest differs from intent")
            manifest = {"schema": "marketmaker.offload_object.v1", "files": files}
            verify_archive(archives, bound["object_sha256"], manifest, max_bytes=limit, archive_path=archive)
            proof = no_links(destination / (key + ".RESTORE_VERIFIED.json"), destination)
            if proof.exists() and load(proof) != bound:
                raise ValueError("restore verification receipt differs from the archive identity")
            if not proof.exists():
                if shutil.disk_usage(destination).free < request["min_free_bytes"] + size + (16 << 20):
                    raise ValueError("insufficient reserve for complete restore verification")
                with tempfile.TemporaryDirectory(prefix=".restore-proof-", dir=destination) as temporary:
                    restored = Path(temporary) / "object"
                    extract_object(archive, restored, max_bytes=limit)
                    verify_tree(restored / "data", files, max_bytes=limit)
                atomic(proof, bound)
            inactive(request, receipt, directory, root)
            if original.exists():
                if parked.exists():
                    raise ValueError("ambiguous original and interrupted retirement")
                verify_tree(original, files, max_bytes=limit)
                os.replace(original, parked)
                sync_directory(original.parent)
            if parked.exists():
                # On interrupted deletion, each remaining member must still be
                # an exact subset of the fully verified, restorable archive.
                remaining = inventory(parked, max_bytes=limit)
                if any(files.get(name) != row for name, row in remaining.items()):
                    raise ValueError("interrupted retirement contains unexpected bytes")
                shutil.rmtree(parked)
                sync_directory(parked.parent)
        compacted = []
        for identity in request["objects"]:
            inactive(request, receipt, directory, root)
            compacted.append(compact_object(object_root / identity, identity, max_bytes=limit))
        inactive(request, receipt, directory, root)
        result = {**intent, "status": "COMPLETED", "compacted_objects": compacted,
                  "restore": "Use restore-retention with this directory, an explicit attempt and a fresh output directory."}
        if previous is not None:
            return previous
        atomic(completed, result)
        return result


def restore(directory, attempt, destination, *, max_bytes):
    from offload_service.core import ID
    if not ID.fullmatch(attempt) or not attempt.startswith("offload-"):
        raise ValueError("explicit attempt identity required")
    directory, destination = Path(directory).absolute(), Path(destination).absolute()
    intent = load(directory / "INTENT.json")
    bound = load(directory / "archives" / (attempt + ".json"))
    if bound["files"] != intent["work"].get(attempt):
        raise ValueError("restore identity differs from retained intent")
    archive = directory / "archives" / (attempt + ".tar.gz")
    manifest = {"schema": "marketmaker.offload_object.v1", "files": bound["files"]}
    verify_archive(directory, bound["object_sha256"], manifest, max_bytes=max_bytes, archive_path=archive)
    extract_object(archive, destination, max_bytes=max_bytes)
    verify_tree(destination / "data", bound["files"], max_bytes=max_bytes)
    return {"status": "RESTORED_AND_VERIFIED", "directory": str(destination / "data"), "attempt": attempt}
