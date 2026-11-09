"""Compile explicit local selections to transport-independent sealed objects."""

import tempfile
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path

from .capsule import snapshot
from .common import atomic, canonical, digest, fields, hash_id, load, positive
from .objects import pack
from .spec import identity, output_plan, selected_ports, validate


def plan(request, destination, *, base=None, max_object_mb=1024, default_max_attempts=None,
         capsule_staging_directory=None):
    positive(max_object_mb, 1048576)
    if default_max_attempts is not None:
        positive(default_max_attempts, 3)
    base = Path(base or ".").resolve()
    from .batch import SCHEMAS, expand

    if request.get("schema") in SCHEMAS:
        request = expand(request)
    destination = Path(destination).resolve()
    staging = Path(capsule_staging_directory).resolve() if capsule_staging_directory is not None else None
    if staging is not None and not staging.is_dir():
        raise ValueError('capsule staging requires an existing directory with a separately budgeted allowance')

    def selection_path(value):
        fields(value, {"source", "include", "resolve_code_links"}, {"source"})
        source = (base / value["source"]).absolute()
        coordinate = source.resolve()
        if destination == coordinate or destination.is_relative_to(coordinate):
            raise ValueError("plan output cannot be inside a packaged source")
        if staging is not None and source.is_dir() and (staging == coordinate or staging.is_relative_to(coordinate)):
            raise ValueError('capsule staging cannot be inside a packaged source')
        return source

    # Check every static source coordinate before copying/compressing the first
    # object. A late conflicting selection previously wasted earlier captures,
    # including multi-GiB data, before this already-known error was reported.
    preflight = deepcopy(request)
    for job in preflight.get("jobs", []):
        if default_max_attempts is not None:
            job.setdefault("max_attempts", default_max_attempts)
        if not isinstance(job["capsule"], str):
            value = job["capsule"]
            selection_path(value)
        else:
            hash_id(job["capsule"])
        # Different selections may capture identical content. Structural
        # validation cannot decide checkpoint capsule equality before capture.
        job["capsule"] = "0" * 64
        for source in job.get("inputs", {}).values():
            if source.get("mode") == "bundle" and "source" in source:
                value = {key: source.pop(key) for key in
                    ("source", "include", "resolve_code_links") if key in source}
                path = selection_path(value)
                source["object_sha256"] = digest({**value, "source": str(path)})
    # These temporary IDs are placeholders, not captured object content.
    # They are never written or admitted; actual object identities are still
    # computed and the compiled workflow revalidated below.
    validate(preflight)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "objects").mkdir()
    request = deepcopy(request)
    sources = []
    packaged = {}

    def package(value, *, capsule=False):
        if isinstance(value, str):
            return value
        source = selection_path(value)
        selection = canonical({**value, "source": str(source)})
        if selection in packaged:
            return packaged[selection]
        with ExitStack() as stack:
            temp = stack.enter_context(tempfile.TemporaryDirectory(
                prefix=".snapshot-", dir=staging if capsule and staging is not None else destination))
            copied = Path(temp) / "data"
            record = snapshot(
                source,
                copied,
                include=value.get("include"),
                resolve_code_links=value.get("resolve_code_links", False),
                max_bytes=max_object_mb * (1 << 20),
            )
            # Keep the compressed object beside its final destination so the
            # atomic rename works even when capsule scratch is another device.
            archive_directory = (stack.enter_context(tempfile.TemporaryDirectory(prefix='.package-', dir=destination))
                                 if capsule and staging is not None else temp)
            archive = Path(archive_directory) / "object.tar.gz"
            original = source.parent / 'OBJECT.json'
            preserve = (source.name == 'data' and not value.get('include')
                        and not value.get('resolve_code_links') and original.is_file()
                        and load(original) == {'schema':'marketmaker.offload_object.v2', 'files':record['files']})
            ref = pack(source if preserve else copied, archive, max_bytes=max_object_mb * (1 << 20))
            if ref['content_manifest']['files'] != record['files']:
                raise ValueError('retained object differs from the verified source snapshot')
            output = destination / "objects" / (ref["object_sha256"] + ".tar.gz")
            if not output.exists():
                archive.replace(output)
            sources.append({"source": str(source), "object_sha256": ref["object_sha256"], **record})
            packaged[selection] = ref["object_sha256"]
            return ref["object_sha256"]

    for job in request.get("jobs", []):
        if default_max_attempts is not None:
            job.setdefault("max_attempts", default_max_attempts)
        job["capsule"] = package(job["capsule"], capsule=True)
        for source in job.get("inputs", {}).values():
            if source.get("mode") == "bundle" and "source" in source:
                source["object_sha256"] = package(
                    {
                        key: source.pop(key)
                        for key in ("source", "include", "resolve_code_links")
                        if key in source
                    }
                )
    workflow = validate(request)
    outputs = output_plan(workflow)
    atomic(destination / "WORKFLOW.json", workflow)
    atomic(destination / "OUTPUT_PLAN.json", outputs)
    atomic(destination / "LOCAL_SOURCES.json", sources)
    receipt = {
        "schema": "marketmaker.offload_compiled_plan.v1",
        "workflow_sha256": identity(workflow),
        "output_plan": outputs,
        "selected_ports": selected_ports(workflow),
        "plugin_code_executed": False,
        "data_acquired": False,
        "scientific_preflight": "NOT_RUN",
        "performance_qualification": "NOT_ESTABLISHED",
        "source_selection_reuse": "ONE_SNAPSHOT_PER_EXACT_SELECTION",
    }
    if "batch" in workflow:
        atomic(destination / "BATCH_PLAN.json", workflow["batch"])
        key = "runs" if "runs" in workflow["batch"] else "candidates"
        receipt["independent_" + key] = len(workflow["batch"][key])
    if staging is not None:
        receipt['capsule_staging'] = {'directory': str(staging),
            'scope': 'Temporary code snapshots only. Data snapshots and compressed objects remain in the plan directory. Input bytes, hash checks and workflow semantics are unchanged; caller budgets both filesystems.'}
    atomic(destination / "PLAN_RECEIPT.json", receipt)
    return receipt


def from_file(path, destination, **kwargs):
    path = Path(path).resolve()
    return plan(load(path), destination, base=path.parent, **kwargs)
