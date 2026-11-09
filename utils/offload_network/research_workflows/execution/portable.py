"""Explicit path-only JSON relocation for any declared immutable input bundle."""

import hashlib
import json
import os
from pathlib import Path

SCHEMA = "marketmaker.portable_input_bundle.v1"


def load(path):
    if Path(path).stat().st_size > 8 << 20:
        raise ValueError("portable JSON exceeds its limit")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or value.startswith("/") or any(p in ("", ".", "..") or p.endswith((" ", "."))
                                           for p in value.split("/"))):
        raise ValueError("portable relative path required")
    return value


def distinct_paths(names):
    files, parents, parts = set(), set(), {}
    for name in names:
        name = relative(name)
        key = name.casefold()
        ancestors = {p.as_posix().casefold() for p in Path(name).parents if p != Path(".")}
        if key in files or key in parents or files.intersection(ancestors):
            raise ValueError("case-colliding or file/directory-colliding paths")
        # Detect different spellings of shared parent directories as well.
        for prefix in [name, *[p.as_posix() for p in Path(name).parents if p != Path(".")]]:
            if prefix.casefold() in parts and parts[prefix.casefold()] != prefix:
                raise ValueError("case-colliding directory paths")
            parts[prefix.casefold()] = prefix
        files.add(key)
        parents.update(ancestors)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def replace_paths(value, replacements):
    """Only exact declared string values/dict keys change; no numeric coercion."""
    counts = {key: 0 for key in replacements}
    def string(value):
        if value in replacements:
            counts[value] += 1
            return replacements[value]
        return value
    def visit(value):
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                renamed = string(key)
                if renamed in result:
                    raise ValueError("path relocation creates duplicate JSON keys")
                result[renamed] = visit(child)
            return result
        if isinstance(value, list):
            return [visit(child) for child in value]
        return string(value) if isinstance(value, str) else value
    result = visit(value)
    if any(count == 0 for count in counts.values()):
        raise ValueError("declared input path was not found in the source document")
    return result, counts


def materialize(root, destination):
    root, destination = Path(root).absolute(), Path(destination).absolute()
    record = load(root / "PORTABLE_INPUT.json")
    if record.get("schema") != SCHEMA:
        raise ValueError("unsupported portable input bundle")
    files = record["files"]
    distinct_paths(files)
    distinct_paths([*record["documents"], "RELOCATION.json"])
    observed = set()
    source = root / "files"
    if source.is_symlink() or not source.is_dir():
        raise ValueError("portable source directory is absent/linked")
    for parent, dirs, leaves in os.walk(source):
        for item in dirs + leaves:
            if (Path(parent) / item).is_symlink():
                raise ValueError("linked portable input")
        for leaf in leaves:
            path = Path(parent) / leaf
            name = relative(path.relative_to(source).as_posix())
            if (name not in files or not path.is_file() or path.stat().st_size != files[name]["bytes"]
                    or sha(path) != files[name]["sha256"]):
                raise ValueError("portable input bytes differ from their manifest")
            observed.add(name)
    if observed != set(files):
        raise ValueError("portable input file inventory differs")
    if destination.is_symlink() or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError("relocated documents need a fresh directory separate from their immutable input")
    destination.mkdir(parents=True, exist_ok=False)
    evidence = []
    for name, document in record["documents"].items():
        name = relative(name)
        original = relative(document["source"])
        if original not in files:
            raise ValueError("document source is not a verified input")
        replacements = {}
        for before, target in document["paths"].items():
            if relative(target) not in files:
                raise ValueError("relocation target is not a verified input")
            replacements[before] = str(source / target)
        result, counts = replace_paths(load(source / original), replacements)
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as stream:
            json.dump(result, stream, sort_keys=True, allow_nan=False)
            stream.write("\n")
        evidence.append({"output": name, "output_sha256": sha(output), "source": original,
                         "source_sha256": files[original]["sha256"], "replacements": replacements,
                         "replacement_counts": counts})
    with (destination / "RELOCATION.json").open("x") as stream:
        json.dump({"schema": "marketmaker.input_relocation_receipt.v1", "documents": evidence,
                   "bundle_manifest_sha256": sha(root / "PORTABLE_INPUT.json"),
                   "payload_bytes_modified": False, "transformation": "exact_declared_path_strings_only"}, stream,
                  sort_keys=True, allow_nan=False)
    return destination
