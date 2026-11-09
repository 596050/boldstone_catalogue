"""Explicit source selection; symlink compatibility copies are opt-in, code-only."""

import shutil
from pathlib import Path

from .common import inventory, positive, rel, sha

SKIP = {".git", ".env", "__pycache__", ".DS_Store", ".pytest_cache", ".ruff_cache"}


def snapshot(source, destination, *, include=None, resolve_code_links=False,
             max_bytes=1 << 30, max_files=100000):
    positive(max_bytes, 1048576 << 20)
    positive(max_files, 10000000)
    source = Path(source).absolute()
    destination = Path(destination)
    if source.is_symlink():
        raise ValueError("source root may not be a symlink")
    source = source.resolve()
    if type(resolve_code_links) is not bool:
        raise ValueError("resolve_code_links must be boolean")
    if include is not None and (not isinstance(include, list) or not include):
        raise ValueError("include must be a nonempty list of relative paths")
    if source.is_file():
        root, selected = source.parent, [source]
    elif source.is_dir():
        root = source
        selected = [source / rel(p) for p in include] if include is not None else [source]
    else:
        raise FileNotFoundError(source)
    root = root.resolve()
    if source.is_dir() and destination.resolve().is_relative_to(root):
        raise ValueError("snapshot destination cannot be inside the source")
    copied, aliases, selected_files = {}, {}, {}
    total = 0
    for item in selected:
        if not item.exists():
            raise FileNotFoundError(item)
        paths = sorted(item.rglob("*")) if item.is_dir() and not item.is_symlink() else [item]
        for path in paths:
            relative = rel(path.relative_to(root).as_posix())
            for parent in path.parents:
                if parent == root:
                    break
                if parent.is_symlink():
                    raise ValueError("directory symlinks may not be traversed")
            if set(path.relative_to(root).parts) & SKIP:
                continue
            if path.is_symlink():
                target = path.resolve()
                if (
                    not resolve_code_links
                    or path.suffix != ".py"
                    or not target.is_file()
                    or not target.is_relative_to(root)
                ):
                    raise ValueError(
                        "only explicitly allowed in-root Python file links may be materialized"
                    )
                aliases[relative] = target.relative_to(root).as_posix()
            elif path.is_dir():
                continue
            elif not path.is_file():
                raise ValueError("source includes a non-regular file")
            if relative in selected_files:
                continue
            size = path.stat().st_size
            total += size
            if total > max_bytes or len(selected_files) >= max_files:
                raise ValueError("source selection exceeds its size/count budget before copying")
            selected_files[relative] = (path, size)
    if not selected_files:
        raise ValueError("empty source selection")
    destination.mkdir(parents=True, exist_ok=False)
    for relative, (path, size) in selected_files.items():
        before = sha(path)
        if path.stat().st_size != size:
            raise ValueError("source changed after snapshot size preflight")
        target = destination / relative
        if target.exists():
            if sha(target) != before:
                raise ValueError("overlapping capsule inputs disagree")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if sha(target) != before or sha(path) != before:
            raise ValueError("source changed while taking snapshot")
        copied[relative] = before
    for relative, expected in copied.items():
        if sha(root / relative) != expected:
            raise ValueError("multi-file input changed during snapshot")
    return {"files": inventory(destination, max_bytes=max_bytes, max_files=max_files),
            "materialized_code_aliases": aliases}


def research_selection(repository, additional=()):
    """Code/config only. Real models, retained libraries and data are explicit."""
    repository = Path(repository)
    testing = repository / "research/testing_stages"
    paths = ["research/__init__.py"]
    for path in sorted(testing.glob("*.py")):
        paths.append(path.relative_to(repository).as_posix())
    for folder in [testing / "runtime", *sorted(testing.glob("stage_[0-9][0-9]_*"))]:
        for path in sorted(folder.glob("*.py")):
            paths.append(path.relative_to(repository).as_posix())
    for path in sorted((testing / "configs").glob("*.json")):
        paths.append(path.relative_to(repository).as_posix())
    default_statistics = testing / "stage_07_statistics/default_statistics.json"
    if default_statistics.is_file():
        paths.append(default_statistics.relative_to(repository).as_posix())
    paths.extend(rel(p) for p in additional)
    return list(dict.fromkeys(paths))
