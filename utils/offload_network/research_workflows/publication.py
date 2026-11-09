"""Append-only candidate records; large verified evidence stays in the registry."""

import os
import shutil
import tempfile
from pathlib import Path

from lib.file_lock import file_lock

from .batch import candidate_results
from .client import SHARED_LAYOUT, collection_objects, verify_collection, verify_object
from .common import atomic, canonical, digest, load, no_links, sha, sync_directory, sync_tree
from .spec import TERMINAL


def _write_once(path, data):
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError("refusing to overwrite an existing research record: " + str(path))
        return
    temporary = path.with_name("." + path.name + ".writing")
    # This staging file is never a committed record; rewriting it resumes a crash.
    if temporary.is_symlink():
        raise ValueError("publication staging file is a symlink")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def publish(project, collection, binding, *, completed_only=False):
    """Publish only source-authorized destinations, after complete native verification."""
    collection = Path(collection).absolute()
    root = project.bulk()
    no_links(collection, root)
    receipt = verify_collection(collection, max_bytes=project.storage["max_collection_mb"] << 20)
    delivery = load(collection / "DELIVERY.json", max_bytes=16 << 20)["manifest"]
    workflow = delivery["workflow"]
    if (
        binding != project.binding(workflow, binding["origins"])
        or receipt["workflow_id"] != binding["workflow_id"]
    ):
        raise ValueError("collection differs from the source-owned origin binding")
    if not receipt["final"] and not completed_only:
        raise ValueError("publish requires a terminal collection, including failed/blocked results")
    index = load(collection / "INDEX.json")
    roster = candidate_results(delivery, index)
    entries = (
        {}
        if roster is None
        else {entry["job_id"]: entry for entry in roster.get("runs", roster.get("candidates", []))}
    )
    nodes = {node["id"]: node for node in delivery["status"]["nodes"]}
    jobs = {job["id"]: job for job in workflow["jobs"]}
    published = []
    for key, origins in binding["origins"].items():
        node = nodes[key]
        # Retain dependency failures and source provenance, not just winning metrics.
        required, pending = set(), [key]
        while pending:
            current = pending.pop()
            if current not in required:
                required.add(current)
                pending.extend(jobs[current]["depends_on"])
        if not receipt["final"] and any(
            nodes[k]["state"] not in TERMINAL for k in required
        ):
            continue  # Never publish a running node or conceal a live dependency.
        ports = {k: v for k, v in index.items() if k.split(".")[0] in required}
        for origin in origins:
            if (
                shutil.disk_usage(project.root).free
                < (project.storage["local_min_free_mb"] + 16) << 20
            ):
                from .project_storage import StorageUnavailable

                raise StorageUnavailable("local publication free-space reserve exhausted")
            path = no_links(
                project.origin(origin)
                / "offload_runs"
                / workflow["submission_id"]
                / key
                / receipt["delivery_sha256"],
                project.root,
            )
            reference = {
                "storage": project.evidence,
                "collection_relative": collection.relative_to(root).as_posix(),
                "delivery_sha256": receipt["delivery_sha256"],
                "ports": ports,
            }
            result = {
                "schema": "marketmaker.offload_research_record.v1",
                "origin": origin,
                "binding_sha256": digest(binding),
                "binding": binding,
                "workflow_id": binding["workflow_id"],
                "workflow_sha256": digest(workflow),
                "node": node,
                "run": entries.get(key),
                "evidence": reference,
                "dependencies": {k: nodes[k] for k in sorted(required - {key})},
                "attempt_history": [
                    a for a in delivery.get("attempts", []) if a["node"] in required
                ],
                "performance_qualification": "NOT_ESTABLISHED",
                "native_receipts_rewritten": False,
            }
            if not receipt["final"]:
                result["collection_scope"] = "terminal_nodes_of_incomplete_workflow"
            text = (
                f"# Offloaded research run: {key}\n\n"
                f"Workflow: `{binding['workflow_id']}`. Execution state: `{node['state']}`. "
                f"Attempt: {node['attempt']}.\n\n"
                "Processing was outsourced; this directory is the local research record. "
                "Execution success is not evidence of model improvement. Failed, negative, "
                "inconclusive and blocked outcomes are retained unchanged.\n\n"
                "[RUN_RESULT.json](RUN_RESULT.json) contains native gate summaries, exact "
                "model/comparator roles, dependency outcomes, input identities and the "
                "central evidence reference. Large native ledgers and original path-bearing "
                "receipts remain byte-for-byte in that verified collection.\n\n"
                "Resolve a returned file using `research-offload origin --config PROJECT.json "
                "--record PATH/TO/THIS/DIRECTORY --port NODE.research_evidence "
                "--relative RESULT.json`. A missing data drive blocks resolution; there "
                "is no substitute source or local shadow data directory.\n"
            )
            if not receipt["final"]:
                text += "\nThis node and its dependencies are terminal; other batch jobs are still pending. A later final snapshot is the same research attempt, not another trial.\n"
            files = {
                "RUN_RESULT.json": (canonical(result) + "\n").encode(),
                "RESULT.md": text.encode(),
            }
            publication = {
                "schema": "marketmaker.offload_publication.v1",
                "binding_sha256": digest(binding),
                "delivery_sha256": receipt["delivery_sha256"],
            }
            if path.exists():
                for filename, data in files.items():
                    if (path / filename).read_bytes() != data:
                        raise ValueError(
                            "existing research publication differs from verified delivery"
                        )
                publication["files"] = {filename: sha(path / filename) for filename in files}
                if load(path / "PUBLICATION.json") != publication:
                    raise ValueError("existing publication receipt changed")
                published.append(path.relative_to(project.root).as_posix())
                continue
            stage = no_links(path.with_name("." + path.name + ".publishing"), project.root)
            stage.mkdir(parents=True, exist_ok=True)
            for filename, data in files.items():
                _write_once(stage / filename, data)
            publication["files"] = {filename: sha(stage / filename) for filename in files}
            atomic(stage / "PUBLICATION.json", publication)
            os.replace(stage, path)
            sync_directory(path.parent)
            published.append(path.relative_to(project.root).as_posix())
    return published


def import_collection(project, collection, origins):
    """Explicitly adopt an existing result; no resubmission, rerun or network ACK."""
    collection = Path(collection).absolute()
    limit = project.storage["max_collection_mb"] << 20
    receipt = verify_collection(collection, max_bytes=limit)
    manifest = load(collection / "DELIVERY.json", max_bytes=16 << 20)["manifest"]
    binding = project.binding(manifest["workflow"], origins)
    project.state.mkdir(parents=True, exist_ok=True)
    with file_lock(project.state / "queue.lock", timeout=0):
        bulk = project.capacity()
        destination = no_links(
            bulk / "collections" / receipt["workflow_id"] / receipt["delivery_sha256"], bulk
        )
        source_cache, _ = collection_objects(collection)
        cache = no_links(bulk / "objects", bulk)
        cache.mkdir(exist_ok=True)
        for ident in receipt["collected_objects"]:
            target = no_links(cache / ident, bulk)
            if target.exists():
                verify_object(target, ident, max_bytes=limit)
                continue
            source = source_cache / ident
            metadata = verify_object(source, ident, max_bytes=limit)
            # Imported shared objects are archive-only too. Expanded bytes are
            # bounded by verify_object, not reserved as permanent disk payloads.
            size = (source / "archive.tar.gz").stat().st_size
            size += (source / "OBJECT.json").stat().st_size
            project.capacity(size + (1 << 20))
            with tempfile.TemporaryDirectory(prefix=".import-", dir=cache) as temporary:
                stage = Path(temporary) / "object"
                from .compressed import marker

                stage.mkdir()
                for filename in ("archive.tar.gz", "OBJECT.json"):
                    shutil.copyfile(source / filename, stage / filename)
                atomic(stage / "RECEIVED.json", {"object_sha256": ident})
                atomic(stage / "ARCHIVE_ONLY.json", marker(ident, metadata))
                verify_object(stage, ident, max_bytes=limit)
                sync_tree(stage)
                os.replace(stage, target)
                sync_directory(cache)
        if not destination.exists():
            stage = no_links(
                destination.with_name("." + destination.name + ".offload-partial"), bulk
            )
            stage.mkdir(parents=True, exist_ok=True)
            for filename in ("DELIVERY.json", "COLLECTION_RECEIPT.json"):
                _write_once(stage / filename, (collection / filename).read_bytes())
            atomic(stage / "OBJECT_STORE.json", SHARED_LAYOUT)
            index = {
                port: "../../../objects/" + ident + "/data"
                for port, ident in manifest["objects"].items()
            }
            atomic(stage / "INDEX.json", index)
            roster = candidate_results(manifest, index)
            if roster is not None:
                from .batch import result_filename

                atomic(stage / result_filename(manifest["workflow"]), roster)
            verify_collection(stage, max_bytes=limit)
            os.replace(stage, destination)
            sync_directory(destination.parent)
        if verify_collection(destination, max_bytes=limit) != receipt:
            raise ValueError("imported collection receipt differs from original")
        paths = publish(project, destination, binding)
        from .compressed import compact_collection

        compact_collection(project, destination)
        return {
            "collection": str(destination),
            "delivery_sha256": receipt["delivery_sha256"],
            "publications": paths,
            "imported_existing_evidence": True,
            "jobs_executed": 0,
        }


def resolve_record(project, directory, port, relative=None):
    """Read through source-owned references; verify bytes without importing models."""
    no_links(project.state, project.root)
    with file_lock(project.state / "queue.lock", timeout=0):
        return _resolve_record(project, directory, port, relative)


def _resolve_record(project, directory, port, relative=None):
    from .common import rel

    directory = Path(directory).absolute()
    # macOS /var and /tmp are OS aliases outside the project. Canonicalize
    # that prefix, while still rejecting any symlink inside the research tree.
    anchors = [p for p in directory.parents if p.resolve() == project.root]
    if not anchors:
        raise ValueError("research record is outside this project")
    directory = no_links(directory, anchors[0]).resolve()
    if not directory.is_relative_to(project.root):
        raise ValueError("research record escapes its project")
    record = load(directory / "RUN_RESULT.json")
    manifest = load(directory / "PUBLICATION.json")
    if (
        set(manifest["files"]) != {"RUN_RESULT.json", "RESULT.md"}
        or record["binding_sha256"] != digest(record["binding"])
        or manifest["binding_sha256"] != record["binding_sha256"]
        or manifest["delivery_sha256"] != record["evidence"]["delivery_sha256"]
        or any(sha(directory / key) != value for key, value in manifest["files"].items())
        or record["binding"]["project_id"] != project.id
        or record["evidence"]["storage"] != project.evidence
    ):
        raise ValueError("local research publication identity changed")
    if port not in record["evidence"]["ports"]:
        raise ValueError("requested artifact is not a dependency of this research record")
    collection = project.bulk(create=False) / rel(record["evidence"]["collection_relative"])
    if (
        load(collection / "COLLECTION_RECEIPT.json")["delivery_sha256"]
        != manifest["delivery_sha256"]
    ):
        raise ValueError("research collection identity changed")
    verify_collection(collection, max_bytes=project.storage["max_collection_mb"] << 20)
    from .compressed import materialize

    objects, _ = collection_objects(collection)
    delivery = load(collection / "DELIVERY.json", max_bytes=16 << 20)["manifest"]
    return materialize(project, objects / delivery["objects"][port], relative)
