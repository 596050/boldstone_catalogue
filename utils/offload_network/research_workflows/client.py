"""Portable workflow requester with resumable object transfers and verified return."""

import errno
from http.client import IncompleteRead
import os
import shutil
import ssl
import time
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path

from lib.file_lock import file_lock
from offload_service.client import Client as BaseClient

from .common import (
    atomic,
    canonical,
    digest,
    hash_id,
    load,
    name,
    no_links,
    parse,
    positive,
    sha,
    sync_directory,
    sync_tree,
    verify_tree,
)
from .objects import CHUNK, SCHEMA, SUPPORTED_SCHEMAS, extract_object


def transient_observation_error(error):
    """Classify GET transport failures; never retry writes or hide auth errors."""
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {404, 408, 425, 429, 500, 502, 503, 504}
    if isinstance(error, ssl.SSLError):
        return False
    if isinstance(error, urllib.error.URLError):
        return (transient_observation_error(error.reason)
                if isinstance(error.reason, BaseException) else True)
    if isinstance(error, (ConnectionError, TimeoutError, IncompleteRead)):
        return True
    return isinstance(error, OSError) and error.errno in {
        errno.ECONNRESET, errno.ECONNREFUSED, errno.ECONNABORTED,
        errno.EPIPE, errno.ETIMEDOUT, errno.ENETUNREACH, errno.EHOSTUNREACH,
        errno.EINTR,
    }


def checked_workflow_status(status, workflow, expected_sha256=None, *, require_terminal=False):
    """A terminal observation must identify the exact requested workflow."""
    from .spec import TERMINAL

    if (not isinstance(status, dict) or status.get("workflow_id") != name(workflow)
            or type(status.get("terminal")) is not bool):
        raise ValueError("workflow status identity or terminal flag differs")
    identity = hash_id(status.get("workflow_sha256"))
    if expected_sha256 is not None and identity != hash_id(expected_sha256):
        raise ValueError("workflow status differs from the expected workflow hash")
    nodes = status.get("nodes")
    if not isinstance(nodes, list) or not nodes or any(not isinstance(n, dict) for n in nodes):
        raise ValueError("workflow status has no valid node observations")
    states = {n.get("state") for n in nodes}
    complete = states <= TERMINAL
    expected_state = ("completed" if states == {"succeeded"} else "completed_with_errors") if complete else "running"
    if status["terminal"] != complete or status.get("state") != expected_state:
        raise ValueError("workflow terminal flag, state and node observations disagree")
    if require_terminal and not complete:
        raise ValueError("a confirmed terminal workflow status is required")
    return status


def release_download_prefix(directory, identity):
    """Remove only the exact duplicate of an already verified retained object."""
    part = no_links(Path(directory) / (identity + ".part"), directory)
    if part.exists():
        if not part.is_file() or sha(part) != identity:
            raise ValueError("completed download prefix changed; retaining bytes")
        part.unlink()
        sync_directory(part.parent)


class Client(BaseClient):
    def open(self, path, body=None, *, data=None, method=None, headers=None, timeout=None):
        actual = {"Authorization": "Bearer " + self.token, "X-Offload-Token": self.token}
        if body is not None:
            data = canonical(body).encode()
            actual["Content-Type"] = "application/json"
        elif data is not None:
            actual["Content-Type"] = "application/octet-stream"
        actual.update(headers or {})
        request = urllib.request.Request(self.url + path, data=data, headers=actual, method=method)
        return self.opener.open(request, timeout=self.timeout if timeout is None else min(self.timeout, timeout))

    def request(self, path, body=None, **kwargs):
        with self.open(path, body, **kwargs) as response:
            data = response.read((16 << 20) + 1)
            if len(data) > 16 << 20:
                raise ValueError("control response exceeds 16 MiB")
            return parse(data)

    def upload(self, archive, *, identity=None):
        archive = Path(archive)
        identity = hash_id(identity) if identity else sha(archive)
        if sha(archive) != identity:
            raise ValueError("local object changed before upload")
        prefix = "/v2/objects/" + identity
        state = self.request(prefix + "/begin", {"bytes": archive.stat().st_size})
        if state["state"] == "committed":
            return identity
        offset = state["offset"]
        with archive.open("rb") as stream:
            stream.seek(offset)
            for chunk in iter(lambda: stream.read(CHUNK), b""):
                # Retrying upload() re-reads the authoritative retained offset.
                state = self.request(prefix + "/chunks/" + str(offset), data=chunk, method="PUT")
                offset = state["offset"]
        self.request(prefix + "/commit", {})
        return identity

    def submit_plan(self, directory, *, validate_only=False):
        directory = Path(directory)
        from .spec import identity, output_plan, validate

        workflow = validate(load(directory / "WORKFLOW.json"))
        receipt = load(directory / "PLAN_RECEIPT.json")
        if receipt["workflow_sha256"] != identity(workflow) or load(
            directory / "OUTPUT_PLAN.json"
        ) != output_plan(workflow):
            raise ValueError("compiled plan changed")
        if "batch" in workflow and load(directory / "BATCH_PLAN.json") != workflow["batch"]:
            raise ValueError("compiled candidate roster changed")
        for archive in sorted((directory / "objects").glob("*.tar.gz")):
            self.upload(archive, identity=archive.name.removesuffix(".tar.gz"))
        return self.request("/v2/validate" if validate_only else "/v2/workflows", workflow)

    def workflow_status(self, workflow, *, timeout=None):
        return self.request("/v2/workflows/" + name(workflow),
                            **({"timeout": timeout} if timeout is not None else {}))

    def revoke_workflow(self, workflow, workflow_sha256):
        return self.request("/v2/workflows/" + name(workflow) + "/revoke",
                            {"workflow_sha256": hash_id(workflow_sha256)})

    def workflow_revocation(self, workflow):
        return self.request("/v2/workflows/" + name(workflow) + "/revocation")

    def wait_workflow(self, workflow, *, deadline=3600, interval=0.25,
                      expected_sha256=None, observation_hook=None):
        positive(deadline, 365 * 86400, integer=False)
        positive(interval, 60, integer=False)
        until = time.monotonic() + deadline
        while True:
            remaining = until - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("poll deadline elapsed; remote computation was not cancelled")
            try:
                status = checked_workflow_status(
                    self.workflow_status(workflow, timeout=remaining), workflow, expected_sha256)
            except (OSError, IncompleteRead) as error:
                if not transient_observation_error(error):
                    raise
                if observation_hook is not None:
                    observation_hook({"workflow_id": workflow, "error_type": type(error).__name__,
                        "error": str(error), "remaining_seconds": max(0, until - time.monotonic()),
                        "elapsed_seconds": max(0, deadline - (until - time.monotonic()))})
            else:
                if status["terminal"]:
                    return status
            time.sleep(min(interval, max(0, until - time.monotonic())))

    def download_object(self, ident, directory, *, max_bytes=1 << 30, archive_only=False):
        hash_id(ident)
        directory = Path(directory)
        destination = directory / ident
        stage = no_links(directory / ("." + ident + ".receiving"), directory)
        if destination.exists():
            verify_object(destination, ident, max_bytes=max_bytes)
            release_download_prefix(directory, ident)
            return destination
        directory.mkdir(parents=True, exist_ok=True)
        if (stage / "archive.tar.gz").exists():
            # Crash after moving the verified prefix but before publishing the
            # directory. This fixed identity-owned stage is discoverable again;
            # no remote connection or second archive copy is necessary.
            verify_object(stage, ident, max_bytes=max_bytes)
            if load(stage / "RECEIVED.json") != {"object_sha256": ident}:
                raise ValueError("interrupted download receipt changed")
            sync_tree(stage)
            os.replace(stage, destination)
            sync_directory(directory)
            release_download_prefix(directory, ident)
            return destination
        state = self.request("/v2/objects/" + ident)
        if state["state"] != "committed" or state["bytes"] > max_bytes:
            raise ValueError("object is unavailable or exceeds download budget")
        part = no_links(directory / (ident + ".part"), directory)
        offset = part.stat().st_size if part.exists() else 0
        if offset > state["bytes"]:
            raise ValueError("retained download is longer than the declared object")
        if offset < state["bytes"]:
            headers = {"If-Match": '"' + ident + '"'}
            if offset:
                headers["Range"] = "bytes=" + str(offset) + "-"
            with self.open("/v2/objects/" + ident + "/archive", headers=headers) as response:
                if response.headers.get("X-Content-SHA256") != ident:
                    raise ValueError("download content identity changed")
                if int(response.headers["Content-Length"]) != state["bytes"] - offset:
                    raise ValueError("download length does not match retained offset")
                if offset and (
                    response.status != 206
                    or response.headers.get("Content-Range")
                    != f"bytes {offset}-{state['bytes'] - 1}/{state['bytes']}"
                ):
                    raise ValueError("server did not honor the immutable resume range")
                with part.open("ab" if offset else "xb") as stream:
                    size = offset
                    for chunk in iter(lambda: response.read(CHUNK), b""):
                        size += len(chunk)
                        if size > state["bytes"]:
                            raise ValueError("server exceeded declared object length")
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
        if part.stat().st_size != state["bytes"] or sha(part) != ident:
            raise ValueError(
                "incomplete/corrupt object; retained prefix needs inspection or a fresh destination"
            )
        if stage.exists():
            # No archive was moved into this disposable stage, and the complete
            # authoritative .part was just hash-verified. Only its regenerable
            # metadata/expansion is discarded; never delete an ambiguous archive.
            shutil.rmtree(stage)
        stage.mkdir(mode=0o700)
        content = stage
        try:
            if archive_only:
                from .compressed import marker, verify_archive

                atomic(content / "OBJECT.json", state["manifest"])
                atomic(content / "ARCHIVE_ONLY.json", marker(ident, state["manifest"]))
                verify_archive(content, ident, state["manifest"], max_bytes=max_bytes,
                               archive_path=part)
            else:
                # The safe extractor owns creation of its output directory.
                content.rmdir()
                extract_object(part, content, max_bytes=max_bytes)
                if {p.name for p in content.iterdir()} != {"OBJECT.json", "data"}:
                    raise ValueError("unexpected object archive members")
                if load(content / "OBJECT.json") != state["manifest"]:
                    raise ValueError("returned file manifest differs from object metadata")
                verify_tree(content / "data", state["manifest"]["files"], max_bytes=max_bytes)
            atomic(content / "RECEIVED.json", {"object_sha256": ident})
            sync_tree(content)
            # Only after metadata and the archived contents are verified/flushed
            # does the prefix move into the recoverable stage. No duplicate bulk
            # copy and no network re-download after a crash at either rename.
            os.replace(part, content / "archive.tar.gz")
            sync_directory(content)
            sync_directory(directory)
            os.replace(content, destination)
            sync_directory(directory)
        except BaseException:
            if stage.exists() and not (stage / "archive.tar.gz").exists():
                shutil.rmtree(stage)
            raise
        release_download_prefix(directory, ident)
        return destination

    def collect(self, workflow, destination, *, max_bytes=1 << 30, partial=False,
                shared_objects=False, acknowledge=True, capacity_guard=None, expected_delivery=None):
        name(workflow)
        if expected_delivery is not None:
            expected_delivery = deepcopy(expected_delivery)
            if (digest(expected_delivery["manifest"]) != expected_delivery["delivery_sha256"]
                    or expected_delivery["manifest"]["status"]["workflow_id"] != workflow
                    or (not partial and not expected_delivery["manifest"]["final"])):
                raise ValueError("invalid pinned collection delivery")
        destination = Path(destination).absolute()
        if destination.is_symlink():
            raise ValueError("collection destination cannot be a symlink")
        destination.parent.mkdir(parents=True, exist_ok=True)
        lock_path = destination.parent / ("." + destination.name + ".collection.lock")
        with file_lock(lock_path, timeout=0):
            if destination.exists():
                receipt = verify_collection(destination, max_bytes=max_bytes)
                if receipt["workflow_id"] != workflow:
                    raise ValueError("destination belongs to another workflow")
                if expected_delivery is not None and receipt["delivery_sha256"] != expected_delivery["delivery_sha256"]:
                    raise ValueError("destination differs from pinned delivery")
                if not partial and not receipt["final"]:
                    raise ValueError(
                        "destination is a partial snapshot; collect final results into a fresh directory"
                    )
                if acknowledge:
                    self.request(
                        "/v2/workflows/" + workflow + "/ack",
                        {"delivery_sha256": receipt["delivery_sha256"]},
                    )
                return receipt
            delivery = expected_delivery if expected_delivery is not None else self.request(
                "/v2/workflows/" + workflow + ("/snapshot" if partial else "/delivery")
            )
            if digest(delivery["manifest"]) != delivery["delivery_sha256"]:
                raise ValueError("delivery manifest hash mismatch")
            if delivery["manifest"]["status"]["workflow_id"] != workflow:
                raise ValueError("delivery belongs to another workflow")
            stage = destination.parent / ("." + destination.name + ".offload-partial")
            if stage.is_symlink():
                raise ValueError("collection staging root is a symlink")
            stage.mkdir(mode=0o700, exist_ok=True)
            if (stage / "DELIVERY.json").exists() and load(stage / "DELIVERY.json") != delivery:
                raise ValueError("partial collection belongs to a different immutable delivery")
            atomic(stage / "DELIVERY.json", delivery)
            if shared_objects:
                atomic(stage / "OBJECT_STORE.json", SHARED_LAYOUT)
            cache, prefix = collection_objects(stage)
            objects = set(delivery["manifest"]["objects"].values())
            total = additional = 0
            for ident in sorted(objects):
                meta = self.request("/v2/objects/" + hash_id(ident))
                size = meta["bytes"] + sum(f["bytes"] for f in meta["manifest"]["files"].values())
                total += size
                if not (cache / ident).exists():
                    part = no_links(cache / (ident + ".part"), cache)
                    receiving = no_links(cache / ("." + ident + ".receiving"), cache)
                    staged_archive = receiving / "archive.tar.gz"
                    if staged_archive.is_file():
                        verify_object(receiving, ident, max_bytes=max_bytes)
                        retained = meta["bytes"]
                    else:
                        retained = part.stat().st_size if part.is_file() else 0
                    if retained > meta["bytes"]:
                        raise ValueError("retained download exceeds declared object size")
                    # Expanded verification ceilings are independent from actual
                    # archive-only storage. Credit resumable bytes already
                    # retained; no second archive copy is required to finalize.
                    additional += (meta["bytes"] if shared_objects else size) - retained
                    additional += len(canonical(meta["manifest"]).encode()) + (8 << 10)
            if total > max_bytes:
                raise ValueError("collection exceeds total byte budget")
            if shutil.disk_usage(stage).free < additional + (16 << 20):
                raise OSError(errno.ENOSPC, "collection exceeds free-space budget")
            if capacity_guard:
                capacity_guard(additional)
            for ident in sorted(objects):
                cache.mkdir(parents=True, exist_ok=True)
                with file_lock(cache / ("." + ident + ".lock"), timeout=0):
                    self.download_object(ident, cache, max_bytes=max_bytes, archive_only=shared_objects)
            index = {
                port: prefix + ident + "/data"
                for port, ident in delivery["manifest"]["objects"].items()
            }
            atomic(stage / "INDEX.json", index)
            from .batch import candidate_results, result_filename

            candidates = candidate_results(delivery["manifest"], index)
            if candidates is not None:
                atomic(stage / result_filename(delivery["manifest"]["workflow"]), candidates)
            receipt = {
                "schema": "marketmaker.offload_collection.v1",
                "workflow_id": workflow,
                "delivery_sha256": delivery["delivery_sha256"],
                "collected_objects": sorted(objects),
                "remote_only": delivery["manifest"]["remote_only"],
                "verification": "ARCHIVE_AND_FILE_MANIFESTS_VERIFIED",
                "final": delivery["manifest"]["final"],
                "workflow_state": delivery["manifest"]["status"]["state"],
                "required_local_missing": delivery["manifest"]["required_local_missing"],
                "native_independent_replay": "NOT_RUN_BY_COLLECTOR",
                "required_inputs_available_locally": all(
                    j["id"] + ".__capsule__" in index
                    and all(j["id"] + ".__input_" + port + "__" in index for port in j["inputs"])
                    for j in delivery["manifest"]["workflow"]["jobs"]
                ),
                "automatic_delete": False,
            }
            atomic(stage / "COLLECTION_RECEIPT.json", receipt)
            verify_collection(stage, max_bytes=max_bytes)
            os.replace(stage, destination)
            sync_directory(destination.parent)
            if acknowledge:
                self.request(
                    "/v2/workflows/" + workflow + "/ack",
                    {"delivery_sha256": delivery["delivery_sha256"]},
                )
            return receipt


SHARED_LAYOUT = {"schema": "marketmaker.offload_shared_objects.v1",
                 "relative_path": "../../../objects"}


def collection_objects(directory):
    """Standalone by default; optional fixed layout in a guarded evidence repository.

    No symlinks/hardlinks or worker-supplied host paths. Copying a shared collection
    requires its referenced objects and REPOSITORY.json, not just its small index.
    """
    directory = Path(directory).absolute()
    marker = directory / "OBJECT_STORE.json"
    if not marker.exists():
        return directory / "objects", "objects/"
    if load(marker) != SHARED_LAYOUT or directory.parents[1].name != "collections":
        raise ValueError("invalid shared collection layout")
    root = directory.parents[2]
    if load(root / "REPOSITORY.json").get("schema") != "marketmaker.offload_repository.v1":
        raise ValueError("shared collection lacks its repository identity")
    no_links(directory, root)
    no_links(root / "objects", root)
    return root / "objects", SHARED_LAYOUT["relative_path"] + "/"


def verify_object(directory, identity, *, max_bytes=1 << 30):
    directory = Path(directory)
    if directory.is_symlink() or sha(directory / "archive.tar.gz") != hash_id(identity):
        raise ValueError("retained object archive changed")
    manifest = load(directory / "OBJECT.json")
    if manifest.get("schema") not in SUPPORTED_SCHEMAS:
        raise ValueError("unsupported object manifest")
    if (directory / "ARCHIVE_ONLY.json").exists():
        from .compressed import marker, verify_archive

        if load(directory / "ARCHIVE_ONLY.json") != marker(identity, manifest):
            raise ValueError("compressed-retention receipt changed")
        verify_archive(directory, identity, manifest, max_bytes=max_bytes)
        if (directory / "data").exists():
            verify_tree(directory / "data", manifest["files"], max_bytes=max_bytes)
        return manifest
    # Bind the extracted manifest to the original authenticated archive, not just itself.
    import tarfile

    with tarfile.open(directory / "archive.tar.gz", "r:gz") as archive:
        member = archive.getmember("OBJECT.json")
        if member.size > 8 << 20 or parse(archive.extractfile(member).read()) != manifest:
            raise ValueError("extracted object manifest changed")
    verify_tree(directory / "data", manifest["files"], max_bytes=max_bytes)
    return manifest


def verify_collection(directory, *, max_bytes=1 << 30):
    directory = Path(directory)
    delivery = load(directory / "DELIVERY.json", max_bytes=16 << 20)
    ident = digest(delivery["manifest"])
    receipt = load(directory / "COLLECTION_RECEIPT.json")
    if ident != delivery["delivery_sha256"] or receipt["delivery_sha256"] != ident:
        raise ValueError("collection identity changed")
    objects = set(delivery["manifest"]["objects"].values())
    if receipt["collected_objects"] != sorted(objects):
        raise ValueError("collection is missing a declared object")
    if receipt["workflow_id"] != delivery["manifest"]["status"]["workflow_id"]:
        raise ValueError("collection workflow changed")
    for field, expected in {
        "final": delivery["manifest"]["final"],
        "workflow_state": delivery["manifest"]["status"]["state"],
        "remote_only": delivery["manifest"]["remote_only"],
        "required_local_missing": delivery["manifest"]["required_local_missing"],
    }.items():
        if receipt[field] != expected:
            raise ValueError("collection receipt changed: " + field)
    cache, prefix = collection_objects(directory)
    expected_index = {
        port: prefix + hash_id(obj) + "/data"
        for port, obj in delivery["manifest"]["objects"].items()
    }
    if load(directory / "INDEX.json") != expected_index:
        raise ValueError("collection index changed")
    from .batch import candidate_results, result_filename

    candidates = candidate_results(delivery["manifest"], expected_index)
    if (
        candidates is not None
        and load(directory / result_filename(delivery["manifest"]["workflow"])) != candidates
    ):
        raise ValueError("independent candidate result index changed")
    total_bytes = 0
    for obj in sorted(objects):
        manifest = verify_object(cache / obj, obj, max_bytes=max_bytes)
        total_bytes += (cache / obj / "archive.tar.gz").stat().st_size
        total_bytes += sum(value["bytes"] for value in manifest["files"].values())
        if total_bytes > max_bytes:
            raise ValueError("collection exceeds aggregate verification budget")
    jobs = {j["id"]: j for j in delivery["manifest"]["workflow"]["jobs"]}
    from .output_manifest import native_summary

    for node in delivery["manifest"]["status"]["nodes"]:
        envelope = node["outputs"] or {}
        port = node["id"] + ".research_evidence"
        if (
            envelope.get("native_result")
            and envelope.get("output_status") == "VERIFIED"
            and port in expected_index
        ):
            from .compressed import data_view

            with data_view(cache / delivery["manifest"]["objects"][port], max_bytes=max_bytes) as view:
                actual = native_summary(None, jobs[node["id"]], native_directory=view)
            if actual != envelope["native_result"]:
                raise ValueError("collected native research evidence changed")
    return receipt
