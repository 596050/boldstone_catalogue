"""Requester-side hash-bound file capture; providers/model semantics stay external."""

import shutil
from pathlib import Path

from .common import atomic, capture_file, fields, hash_id, inventory, load, no_links, positive, rel, sha
from .execution.portable import SCHEMA, distinct_paths, replace_paths

REQUEST_SCHEMA = "marketmaker.portable_input_request.v1"


def prepare(request, destination, *, base=None):
    fields(request, {"schema", "files", "documents", "max_bytes", "min_free_bytes"},
           {"schema", "files", "documents", "max_bytes", "min_free_bytes"})
    if request["schema"] != REQUEST_SCHEMA:
        raise ValueError("unsupported portable input request")
    positive(request["max_bytes"], 1 << 40)
    if type(request["min_free_bytes"]) is not int or request["min_free_bytes"] < 0:
        raise ValueError("declare a nonnegative free-space reserve")
    if not isinstance(request["files"], dict) or not request["files"]:
        raise ValueError("declare explicit hash-bound input files")
    if not isinstance(request["documents"], dict):
        raise ValueError("declare path-relocated documents, or an empty mapping")
    distinct_paths(request["files"])
    distinct_paths([*request["documents"], "RELOCATION.json"])
    base, destination = Path(base or ".").resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    sources, sizes, total = {}, {}, 0
    for name, reference in request["files"].items():
        rel(name)
        fields(reference, {"path", "sha256"}, {"path", "sha256"})
        hash_id(reference["sha256"])
        source = (base / reference["path"]).absolute()
        if source.is_symlink() or not source.is_file():
            raise ValueError("input is not a regular local file: " + name)
        sizes[name] = source.stat().st_size
        total += sizes[name]
        if total > request["max_bytes"]:
            raise ValueError("input files exceed their declared byte budget")
        if sha(source) != reference["sha256"]:
            raise ValueError("input differs from its declared hash: " + name)
        sources[name] = source
    if len(sources) > 100000 or total > request["max_bytes"]:
        raise ValueError("input files collide or exceed their declared byte budget")
    for name, document in request["documents"].items():
        rel(name)
        if name == "RELOCATION.json":
            raise ValueError("reserved relocation receipt path")
        fields(document, {"source", "paths"}, {"source", "paths"})
        if document["source"] not in sources or not isinstance(document["paths"], dict):
            raise ValueError("document source and explicit path map are required")
        if any(not isinstance(key, str) or not key or value not in sources for key, value in document["paths"].items()):
            raise ValueError("document paths must map to declared input files")
        replace_paths(load(sources[document["source"]]), document["paths"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    no_links(destination, destination.parent)
    if shutil.disk_usage(destination.parent).free < total + request["min_free_bytes"]:
        raise ValueError("insufficient input capture space above the declared reserve")
    destination.mkdir()
    atomic(destination / "REQUEST.json", request)
    try:
        for name, source in sources.items():
            target = no_links(destination / "files" / name, destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            expected = request["files"][name]["sha256"]
            capture_file(source, target, expected_sha256=expected, max_bytes=sizes[name])
        manifest = {"schema": SCHEMA, "files": inventory(destination / "files", max_bytes=request["max_bytes"]),
                    "documents": request["documents"], "source_bytes_modified": False}
        if shutil.disk_usage(destination).free < request["min_free_bytes"]:
            raise ValueError("input capture consumed its free-space reserve")
        atomic(destination / "PORTABLE_INPUT.json", manifest)
        return manifest
    except BaseException as error:
        atomic(destination / "FAILURE.json", {"status": "CAPTURE_FAILED", "error": str(error)})
        raise


def from_file(request, destination):
    request = Path(request).resolve()
    return prepare(load(request), destination, base=request.parent)
