#!/usr/bin/env python3
"""
Split large JSONL (NDJSON) files into smaller shards without breaking lines.

This is useful for keeping individual files under a configured per-file size
limit (e.g. GitHub's 100 MiB limit, or a smaller internal batching limit).

By default, the script:
  - creates sibling files named: <stem>-part-0001.jsonl, <stem>-part-0002.jsonl, ...
  - deletes the original file after a successful split

Examples (from repo root):

  # Split specific files into <= 89 MiB parts
  python utils/git/split_jsonl_shards.py organizations_tmp/organisations-000001.jsonl --max-mib 89

  # Split every JSONL file in a directory matching a glob
  python utils/git/split_jsonl_shards.py organizations_tmp --pattern 'organisations-*.jsonl' --max-mib 89
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence


MiB = 1024 * 1024


def _iter_input_paths(args_paths: Sequence[str], pattern: str) -> List[Path]:
    paths: List[Path] = []
    for raw in args_paths:
        p = Path(raw)
        if p.is_dir():
            paths.extend(sorted(p.glob(pattern)))
        else:
            paths.append(p)
    # Deduplicate while preserving order
    seen = set()
    uniq: List[Path] = []
    for p in paths:
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _part_path(src: Path, part_index: int) -> Path:
    return src.with_name(f"{src.stem}-part-{part_index:04d}{src.suffix}")


def split_jsonl_file(
    path: Path,
    *,
    max_bytes: int,
    keep_original: bool,
    overwrite: bool,
    dry_run: bool,
) -> List[Path]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.is_dir():
        raise IsADirectoryError(str(path))
    if path.suffix.lower() != ".jsonl":
        raise ValueError(f"Refusing to split non-.jsonl file: {path}")

    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = 0

    if size_bytes <= max_bytes:
        return []

    out_paths: List[Path] = []
    part_index = 1
    bytes_in_part = 0
    out_f = None

    def _open_next() -> None:
        nonlocal out_f, part_index, bytes_in_part
        if out_f is not None:
            out_f.close()
            out_f = None
        out_path = _part_path(path, part_index)
        if out_path.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite existing file: {out_path}")
        out_paths.append(out_path)
        bytes_in_part = 0
        if not dry_run:
            out_f = out_path.open("wb" if overwrite else "xb")

    try:
        with path.open("rb") as f:
            _open_next()
            for line_number, line in enumerate(f, start=1):
                line_len = len(line)
                if line_len == 0:
                    continue
                if line_len > max_bytes:
                    raise RuntimeError(
                        f"Line {line_number} in {path} is {line_len} bytes which exceeds "
                        f"the configured max of {max_bytes} bytes; cannot split without "
                        "breaking JSON lines. Increase --max-mib."
                    )

                if bytes_in_part and bytes_in_part + line_len > max_bytes:
                    part_index += 1
                    _open_next()

                if not dry_run:
                    assert out_f is not None
                    out_f.write(line)
                bytes_in_part += line_len

        if out_f is not None:
            out_f.close()
            out_f = None

        if not keep_original and not dry_run:
            path.unlink()

        return out_paths
    except Exception:
        if out_f is not None:
            try:
                out_f.close()
            except Exception:
                pass
        if not dry_run:
            for out_path in out_paths:
                try:
                    if out_path.exists():
                        out_path.unlink()
                except Exception:
                    pass
        raise


def _format_mib(num_bytes: int) -> str:
    return f"{num_bytes / MiB:.2f} MiB"


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Split oversized JSONL files into smaller shards.")
    parser.add_argument(
        "paths",
        nargs="+",
        help="One or more JSONL files and/or directories.",
    )
    parser.add_argument(
        "--pattern",
        default="*.jsonl",
        help="Glob pattern used when a PATH is a directory (default: *.jsonl).",
    )
    parser.add_argument(
        "--max-mib",
        type=float,
        default=89.0,
        help="Maximum size per output shard in MiB (default: 89).",
    )
    parser.add_argument(
        "--keep-original",
        action="store_true",
        help="Keep the original file (default deletes it after successful split).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing <stem>-part-*.jsonl files if present.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be split, without writing files.",
    )
    args = parser.parse_args(list(argv))

    max_bytes = int(args.max_mib * MiB)
    paths = _iter_input_paths(args.paths, args.pattern)
    if not paths:
        print("No input files found.", file=sys.stderr)
        return 1

    split_count = 0
    skipped_count = 0

    for path in paths:
        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = 0

        if size_bytes <= max_bytes:
            skipped_count += 1
            continue

        print(f"Splitting {path} ({_format_mib(size_bytes)}) into <= {_format_mib(max_bytes)} parts...")
        out_paths = split_jsonl_file(
            path,
            max_bytes=max_bytes,
            keep_original=args.keep_original,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            split_count += 1
            continue

        for out_path in out_paths:
            try:
                out_size = out_path.stat().st_size
            except OSError:
                out_size = 0
            if out_size > max_bytes:
                raise RuntimeError(
                    f"Output shard exceeds max size: {out_path} is {_format_mib(out_size)} "
                    f"(max {_format_mib(max_bytes)})."
                )
        split_count += 1

    if args.dry_run:
        print(f"Dry run complete. Would split {split_count} file(s); skip {skipped_count} within limit.")
    else:
        print(f"Done. Split {split_count} file(s); skipped {skipped_count} within limit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
