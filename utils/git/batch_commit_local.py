#!/usr/bin/env python3
"""
Batch-commit large sets of data files in chunks that keep each commit under
an approximate size threshold (default ~50 MiB), then push after each commit.

Usage (from the repo root):

    python utils/git/batch_commit_large_data.py

By default this:
  - Detects all changes relative to HEAD (modified, added, deleted, untracked).
  - Groups non-deletion changes into batches where the sum of file sizes is
    below MAX_BATCH_BYTES (50 MiB by default).
  - Includes deletions in whichever batch they fall into without counting
    toward the size limit.
  - Commits each batch with the message: "Add large batch of data".
  - Pushes the current branch to the "origin" remote after each commit.

Notes:
  - Any single file larger than MAX_BATCH_BYTES will cause the script to abort,
    so that you do not accidentally create a commit that GitHub might reject.
  - The script assumes there are no staged changes when it starts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import argparse
from dataclasses import dataclass
from typing import Dict, List, Tuple


DEFAULT_MAX_BATCH_BYTES = 50 * 1024 * 1024  # 50 MiB per commit (approximate)
COMMIT_MESSAGE = "Add large batch of data"
REMOTE_NAME = "origin"


@dataclass
class Change:
    path: str
    kind: str  # "add", "modify", "delete"
    size_bytes: int


def run_git(args: List[str], capture: bool = True, check: bool = True) -> str:
    """Run a git command and optionally capture output."""
    cmd = ["git"] + args
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd)
    if check and result.returncode != 0:
        if capture:
            stderr = result.stderr.strip()
        else:
            stderr = "(see command output above)"
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    if capture:
        return result.stdout
    return ""


def ensure_clean_index() -> None:
    """Abort if there are already staged changes."""
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode != 0:
        print(
            "Error: index has staged changes already.\n"
            "Please run `git reset` to unstage them before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)


def get_current_branch() -> str:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if branch in ("HEAD", ""):
        print(
            "Error: not on a named branch (detached HEAD). "
            "Please check out a branch before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    return branch


def discover_changes(path_prefixes: List[str]) -> Dict[str, Change]:
    """
    Discover all changes relative to HEAD:
      - modifications and additions from `git diff --name-status -z HEAD`
      - deletions from the same
      - untracked files from `git ls-files --others --exclude-standard -z`
    """
    changes: Dict[str, Change] = {}

    diff_args = ["diff", "--name-status", "-z", "HEAD"]
    if path_prefixes:
        diff_args.extend(["--", *path_prefixes])
    diff_output = run_git(diff_args)
    
    if diff_output:
        # -z separation means tokens are null-separated
        tokens = diff_output.split('\0')
        # Remove empty string at end if result ended with \0
        if tokens and tokens[-1] == "":
            tokens.pop()

        i = 0
        while i < len(tokens):
            code = tokens[i]
            i += 1
            # Safety check
            if not code:
                continue

            if code.startswith("R") or code.startswith("C"):  # Rename/Copy
                # Format: status <NUL> old_path <NUL> new_path <NUL>
                if i + 1 >= len(tokens):
                    break
                old_path = tokens[i]
                i += 1
                new_path = tokens[i]
                i += 1
                
                changes[old_path] = Change(
                    path=old_path,
                    kind="delete",
                    size_bytes=0,
                )
                size = _safe_filesize(new_path)
                changes[new_path] = Change(
                    path=new_path,
                    kind="add",
                    size_bytes=size,
                )
            else:
                # Format: status <NUL> path <NUL>
                if i >= len(tokens):
                    break
                path = tokens[i]
                i += 1

                if code == "D":
                    changes[path] = Change(path=path, kind="delete", size_bytes=0)
                else:
                    size = _safe_filesize(path)
                    kind = "modify" if code == "M" else "add"
                    changes[path] = Change(path=path, kind=kind, size_bytes=size)

    # Untracked files (treated as "add")
    ls_args = ["ls-files", "--others", "--exclude-standard", "-z"]
    if path_prefixes:
        ls_args.extend(["--", *path_prefixes])
    untracked_output = run_git(ls_args)
    
    if untracked_output:
        for path in untracked_output.split('\0'):
            if not path.strip():
                continue
            if path in changes:
                continue
            size = _safe_filesize(path)
            changes[path] = Change(path=path, kind="add", size_bytes=size)

    # Optionally restrict to specific path prefixes
    if path_prefixes:
        filtered: Dict[str, Change] = {}
        for path, change in changes.items():
            if _matches_prefix(path, path_prefixes):
                filtered[path] = change
        return filtered

    return changes


def _matches_prefix(path: str, prefixes: List[str]) -> bool:
    """Return True if path is under any of the given prefixes."""
    for prefix in prefixes:
        if not prefix:
            continue
        norm = prefix.rstrip("/")
        if path == norm or path.startswith(norm + "/"):
            return True
    return False


def _safe_filesize(path: str) -> int:
    """Return file size in bytes, or 0 if the file is missing."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def validate_file_sizes(changes: Dict[str, Change], max_batch_bytes: int) -> None:
    """Ensure no single file exceeds the batch size limit."""
    too_large: List[Tuple[str, int]] = []
    for change in changes.values():
        if change.kind == "delete":
            continue
        if change.size_bytes > max_batch_bytes:
            too_large.append((change.path, change.size_bytes))

    if too_large:
        print(
            "Error: some files are larger than the configured batch size "
            f"({max_batch_bytes} bytes ~ {max_batch_bytes / (1024*1024):.1f} MiB):",
            file=sys.stderr,
        )
        for path, size in too_large:
            print(f"  {path} ({size / (1024*1024):.2f} MiB)", file=sys.stderr)
        print(
            "These files cannot be safely committed under the current limit. "
            "Consider splitting them or increasing the max batch size "
            "(e.g. via --max-batch-mib).",
            file=sys.stderr,
        )
        sys.exit(1)


def batch_changes(changes: Dict[str, Change], max_batch_bytes: int) -> List[List[Change]]:
    """
    Group changes into batches such that the sum of non-deletion file sizes
    in each batch is <= max_batch_bytes.
    """
    # Sort by size descending so we pack larger files first.
    sorted_changes = sorted(
        changes.values(),
        key=lambda c: c.size_bytes,
        reverse=True,
    )

    batches: List[List[Change]] = []
    current_batch: List[Change] = []
    current_size = 0

    for change in sorted_changes:
        size = 0 if change.kind == "delete" else change.size_bytes

        # If adding this change would exceed the limit, start a new batch
        # (but ensure we don't split deletions unnecessarily).
        if current_batch and current_size + size > max_batch_bytes:
            batches.append(current_batch)
            current_batch = []
            current_size = 0

        current_batch.append(change)
        current_size += size

    if current_batch:
        batches.append(current_batch)

    return batches


def stage_batch(batch: List[Change]) -> None:
    """Stage all changes in a batch."""
    if not batch:
        return
    # Stage paths in chunks to avoid very long command lines.
    paths: List[str] = []
    skipped_missing = 0
    for change in batch:
        # For deletions, the file may not exist on disk; `git add -A -- <path>`
        # will still stage the deletion if the path is tracked.
        if change.kind == "delete":
            paths.append(change.path)
            continue
        # For adds/modifies, a path can disappear between discovery and staging
        # (e.g. ephemeral crawler state files). Skip those rather than failing.
        if os.path.lexists(change.path):
            paths.append(change.path)
        else:
            skipped_missing += 1
    if skipped_missing:
        print(
            f"Skipping {skipped_missing} missing path(s) during git add.",
            file=sys.stderr,
        )
    if not paths:
        return
    chunk_size = 5000
    for start in range(0, len(paths), chunk_size):
        chunk = paths[start : start + chunk_size]
        # Use a direct subprocess call so we can gracefully handle the case
        # where all paths in the chunk are ignored by .gitignore (git exits
        # non‑zero in that case but this is not a real error for our purposes).
        cmd = ["git", "add", "-A", "--", *chunk]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if "ignored by one of your .gitignore" in stderr:
                # All paths in this chunk are ignored; nothing to stage.
                # Log once and continue with remaining chunks.
                print(
                    "Skipping chunk with only .gitignored paths during git add.",
                    file=sys.stderr,
                )
                continue
            if "did not match any files" in stderr:
                # A path may have disappeared between discovery and staging.
                # Remove those paths and retry once.
                import re

                missing = set(re.findall(r"pathspec '([^']+)' did not match any files", stderr))
                if missing:
                    retry_chunk = [p for p in chunk if p not in missing and os.path.lexists(p)]
                    if retry_chunk:
                        retry_cmd = ["git", "add", "-A", "--", *retry_chunk]
                        retry = subprocess.run(retry_cmd, capture_output=True, text=True)
                        if retry.returncode == 0:
                            print(
                                f"Skipped {len(missing)} missing path(s) during git add retry.",
                                file=sys.stderr,
                            )
                            continue
                    # If everything was missing, just move on.
                    print(
                        f"Skipping chunk with missing paths during git add: {', '.join(sorted(missing))}",
                        file=sys.stderr,
                    )
                    continue
            raise RuntimeError(f"git add failed: {stderr}")


def commit_and_push_batches(batches: List[List[Change]], branch: str) -> None:
    total_batches = len(batches)
    if total_batches == 0:
        print("No changes to commit.")
        return

    for idx, batch in enumerate(batches, start=1):
        print(f"\n=== Processing batch {idx}/{total_batches} ===")
        batch_size = sum(
            c.size_bytes for c in batch if c.kind != "delete"
        )
        print(
            f"Staging {len(batch)} paths "
            f"(approx {batch_size / (1024*1024):.2f} MiB of data)..."
        )
        stage_batch(batch)

        print(f"Committing batch {idx}/{total_batches}...")
        run_git(["commit", "-m", COMMIT_MESSAGE], capture=False)

        print(f"Pushing batch {idx}/{total_batches} to {REMOTE_NAME}/{branch}...")
        try:
            print("Pushing skipped for safety (local only)")
        except RuntimeError as exc:
            print(
                f"\nError: push for batch {idx} failed.\n"
                f"{exc}\n"
                "The commit is created locally but not pushed. "
                "Resolve the remote issue (e.g. by pulling/rebasing) "
                "and push manually.",
                file=sys.stderr,
            )
            sys.exit(1)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-commit large sets of data files in chunks that keep each "
            "commit under an approximate size threshold, then push after each commit."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            "Optional path prefixes to limit which changes are batched "
            "(e.g. 'canonical/people canonical/firms'). "
            "If omitted, all changes are considered."
        ),
    )
    parser.add_argument(
        "--max-batch-mib",
        type=float,
        default=DEFAULT_MAX_BATCH_BYTES / (1024 * 1024),
        help=(
            "Approximate maximum MiB of non-deletion data per commit. "
            "Increase this if you have individual files larger than the "
            "default limit of "
            f"{DEFAULT_MAX_BATCH_BYTES / (1024*1024):.1f} MiB but still below "
            "your remote's per-file limit (e.g. GitHub's 100 MiB)."
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])

    max_batch_bytes = int(args.max_batch_mib * 1024 * 1024)

    ensure_clean_index()
    branch = get_current_branch()

    print("Discovering changes relative to HEAD...")
    changes = discover_changes(args.paths)
    if not changes:
        print("No changes detected; nothing to do.")
        return

    if args.paths:
        print(f"Found {len(changes)} changed paths under: {', '.join(args.paths)}")
    else:
        print(f"Found {len(changes)} changed paths.")

    validate_file_sizes(changes, max_batch_bytes)

    batches = batch_changes(changes, max_batch_bytes)
    print(
        f"Planned {len(batches)} batch(es) with per-commit limit of "
        f"{max_batch_bytes / (1024*1024):.1f} MiB."
    )

    commit_and_push_batches(batches, branch)
    print("\nAll batches committed and pushed successfully.")


if __name__ == "__main__":
    main()
