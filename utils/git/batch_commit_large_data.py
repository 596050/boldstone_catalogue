#!/usr/bin/env python3
"""
Batch-commit large sets of data files in chunks that keep each commit under
an approximate size threshold (default ~50 MiB), then push after each commit.

Usage (from the repo root):

    python3 utils/git/batch_commit_large_data.py --max-batch-mib 90

By default this:
  - Detects all changes relative to HEAD (modified, added, deleted, untracked).
  - Automatically splits any file exceeding the per-file size limit
    (default 99 MiB) into numbered parts (e.g. file.part1.pdf, file.part2.pdf).
  - Groups non-deletion changes into batches where the sum of file sizes is
    below MAX_BATCH_BYTES (50 MiB by default).
  - Includes deletions in whichever batch they fall into without counting
    toward the size limit.
  - Runs without repository commit hooks. Use --run-commit-hooks to opt in.
  - Preserves existing staging in a local backup ref before regrouping the
    working-tree changes into size-limited batches.
  - Commits each batch with the message: "Add large batch of data".
  - Pushes the current branch to the "origin" remote after each commit.

Before any of that it fetches the remote branch, aborts if a commit already
waiting to be pushed contains a file above the remote's hard per-file limit
(GitHub's 100 MiB / GH001), and skips commits the remote already has.
Research governance is deliberately outside this Git utility. It does not run
portfolio refreshes, storage/layout validation, candidate admission, or any
other research gate before staging or committing. Storing files in Git does
not verify a research result. Independent reporting checks remain separate.

Notes:
  - --dry-run previews the working-tree batches without fetching, splitting,
    changing the index, committing, or pushing.
  - Git's own short-lived write locks are respected. Confirmed abandoned index
    locks are recovered automatically; no script lock or manual lease is used.
  - If a commit hook rejects a batch, the script returns that batch to the
    unstaged working tree so the next run does not require manual index repair.
  - Automatic splitting only ever inspects the WORKING TREE. A large file that
    was committed with a plain `git commit` bypasses it entirely and makes the
    whole branch unpushable; that case is detected by the history scan at
    startup, but fixing it requires rewriting the commits that carry the blob.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import argparse
import time
import json
import re
import stat
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from fnmatch import fnmatch
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


DEFAULT_MAX_BATCH_BYTES = 50 * 1024 * 1024  # 50 MiB per commit (approximate)
DEFAULT_MAX_FILE_BYTES = 99 * 1024 * 1024   # 99 MiB per file (under GitHub's 100 MiB limit)
# GitHub rejects any single file above this with GH001 at the pre-receive hook.
# It applies to the file size, not the compressed size, and no push option can
# bypass it -- the whole push is refused, including unrelated commits.
DEFAULT_REMOTE_FILE_LIMIT_BYTES = 100 * 1024 * 1024
DEFAULT_PUSH_RETRIES = 3
DEFAULT_PUSH_RETRY_DELAY_SECONDS = 5.0
DEFAULT_SSH_KEEPALIVE_INTERVAL_SECONDS = 15
DEFAULT_SSH_KEEPALIVE_COUNT_MAX = 8
DEFAULT_PUSH_PACK_THREADS = 1
DEFAULT_PUSH_COMPRESSION = 0
DEFAULT_PUSH_PACK_WINDOW = 0
DEFAULT_EXCLUDE_GLOBS = [
    "data/cache/**",
    "data/cache/*",
    "data/*.db",
    "data/*.db-shm",
    "data/*.db-wal",
    "data/*.state.json",
    "data/*.sqlite",
    "data/*.sqlite-shm",
    "data/*.sqlite-wal",
    "utils/external_storage/credentials/*.json",
    "**/*.lock",
    "**/RUN.lock",
]
COMMIT_MESSAGE = "Add large batch of data"
REMOTE_NAME = "origin"
HOOK_REJECT_MARKERS = (
    "RESEARCH_REPORTING_REJECTED",
    '"status": "REJECTED"',
    "new numerical performance report bypasses the finalizer",
)
# Paths the local reporting pre-commit hook reads from the Git index. Packing
# by size would otherwise commit a 90 MiB payload first and leave these
# untracked, which makes `git show :POLICY.json` fail.
COMMIT_HOOK_INDEX_PATHS = (
    "research/research_reporting_policy_v1/POLICY.json",
    "research/research_reporting_policy_v2/POLICY.json",
    "research/equity_full_minute_price_policy_20260905_v1/POLICY.json",
    "research/utility/research_reporting_v1/enforce.py",
    "research/utility/research_reporting_v1/independent.py",
    "research/utility/research_reporting_v1/reporting.py",
    "research/utility/research_reporting_v2/enforce.py",
    "research/utility/research_reporting_v4/enforce.py",
    "research/utility/research_reporting_v5/enforce.py",
    "research/utility/research_evaluation_v1/calculator.py",
    "research/utility/intraday_quote_reporting_v1/reporting.py",
    "research/utility/intraday_quote_evaluation_v1/calculator.py",
    "research/utility/intraday_quote_evaluation_v1/verify.py",
)

@dataclass
class Change:
    path: str
    kind: str  # "add", "modify", "delete"
    size_bytes: int

def run_git(
    args: List[str],
    capture: bool = True,
    check: bool = True,
    env: Optional[Dict[str, str]] = None,
) -> str:
    """Run a git command and optionally capture output."""
    cmd = ["git"] + args
    if capture:
        result = _retry_index_operation(
            lambda: subprocess.run(cmd, capture_output=True, text=True, env=env), 'git ' + args[0])
    else:
        result = subprocess.run(cmd, env=env)
    if check and result.returncode != 0:
        if capture:
            stderr = result.stderr.strip()
        else:
            stderr = "(see command output above)"
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    if capture:
        return result.stdout
    return ""


def _run_git_with_pathspec_input(
    args: List[str], paths: List[str]
) -> subprocess.CompletedProcess[bytes]:
    """Run Git with NUL-delimited pathspecs supplied over stdin.

    A path-count chunk can still exceed the operating system's ARG_MAX when
    the paths are long.  Git's pathspec-from-file interface keeps those paths
    out of argv entirely and the NUL form preserves every filename byte.
    """
    pathspec_input = b"".join(os.fsencode(path) + b"\0" for path in paths)
    return subprocess.run(
        [
            "git",
            *args,
            "--pathspec-from-file=-",
            "--pathspec-file-nul",
        ],
        input=pathspec_input,
        capture_output=True,
    )


def ensure_clean_index() -> None:
    """Save existing staging, then let the working-tree batch plan regroup it.

    The backup commit is reachable from a local ref, so even staged bytes that
    differ from the working tree remain recoverable. No working file is reset.
    """
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        return
    if result.returncode != 1:
        raise RuntimeError('Git could not read the index; see the Git error above.')
    if run_git(['ls-files', '--unmerged', '-z']):
        raise RuntimeError('The Git index has unresolved merge conflicts; resolve them before batching.')
    for state in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply'):
        if Path(run_git(['rev-parse', '--git-path', state]).strip()).exists():
            raise RuntimeError('Finish the in-progress Git operation before regrouping its staged changes: ' + state)
    tree = run_git(['write-tree']).strip()
    head = run_git(['rev-parse', 'HEAD']).strip()
    ref = 'refs/batch-commit/index-backups/' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
    commit = run_git(['commit-tree', tree, '-p', head, '-m', 'Preserve staging before working-tree data batching']).strip()
    run_git(['update-ref', ref, commit])
    run_git(['read-tree', '--reset', 'HEAD'])
    print(f'Saved existing staging in {ref}; batching current working-tree contents.\n'
          f'Recover a staged file with: git show {ref}:<path>')


def has_staged_changes() -> bool:
    """Return True when index contains staged changes."""
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    return result.returncode != 0


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


def get_remote_url(remote_name: str) -> str:
    """Return the configured push URL for a remote."""
    return run_git(["remote", "get-url", "--push", remote_name]).strip()


def _is_ssh_remote_url(url: str) -> bool:
    return url.startswith("ssh://") or "@" in url.split("://")[-1].split("/")[0]


def _with_ssh_keepalive_env(
    remote_url: str,
    keepalive_interval_seconds: int,
    keepalive_count_max: int,
) -> Optional[Dict[str, str]]:
    """
    Build an environment with SSH keepalive options for SSH remotes.

    For HTTPS remotes no environment override is needed.
    """
    if not _is_ssh_remote_url(remote_url):
        return None

    env = os.environ.copy()
    existing = env.get("GIT_SSH_COMMAND", "ssh")
    env["GIT_SSH_COMMAND"] = (
        f"{existing} -o ServerAliveInterval={keepalive_interval_seconds} "
        f"-o ServerAliveCountMax={keepalive_count_max} -o TCPKeepAlive=yes"
    )
    return env


def _remote_tracking_ref_exists(remote_name: str, branch: str) -> bool:
    ref = f"refs/remotes/{remote_name}/{branch}"
    result = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref])
    return result.returncode == 0


def get_branch_divergence(remote_name: str, branch: str) -> Tuple[int, int]:
    """
    Return (ahead, behind) counts for local branch vs remote tracking branch.

    If the remote tracking branch does not exist locally yet, return (0, 0).
    """
    if not _remote_tracking_ref_exists(remote_name, branch):
        return (0, 0)

    output = run_git(
        ["rev-list", "--left-right", "--count", f"{remote_name}/{branch}...{branch}"]
    ).strip()
    if not output:
        return (0, 0)

    behind_str, ahead_str = output.split()
    return (int(ahead_str), int(behind_str))


def _ahead_commit_hashes(remote_name: str, branch: str) -> List[str]:
    """Return unpushed commits in oldest-first order."""
    if not _remote_tracking_ref_exists(remote_name, branch):
        return []
    out = run_git(["rev-list", "--reverse", f"{remote_name}/{branch}..{branch}"]).strip()
    if not out:
        return []
    return [line for line in out.splitlines() if line.strip()]


def fetch_remote_branch(remote_name: str, branch: str) -> bool:
    """
    Refresh refs/remotes/<remote>/<branch> before reasoning about divergence.

    Without this, both the ahead/behind counts and the unpushed-commit list come
    from a tracking ref that may be arbitrarily stale (a sibling session pushed,
    or an earlier run of this script pushed and then died).  The list then
    contains commits the remote already has, and pushing one of those rewinds
    the remote -- a permanent non-fast-forward that no retry can fix.
    """
    result = subprocess.run(
        ["git", "fetch", "--quiet", remote_name, branch],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"Warning: could not fetch {remote_name}/{branch}; divergence will be "
            "computed from a possibly stale tracking ref.\n"
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    return True


def _is_ancestor(commit: str, ref: str) -> bool:
    """Return True when `commit` is already contained in `ref`."""
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, ref]
    ).returncode == 0


def classify_push_failure(output: str) -> Optional[str]:
    """
    Return a human-readable reason when a push failure is permanent.

    Retrying a permanent failure can never succeed; it only buries the real
    error behind several seconds of backoff.  Returns None for failures that
    are plausibly transient (network drop, timeout), which are worth retrying.
    """
    lowered = output.lower()

    if (
        "non-fast-forward" in lowered
        or "fetch first" in lowered
        or "behind its remote counterpart" in lowered
    ):
        return (
            "non-fast-forward -- the remote already contains commits this refspec "
            "would rewind. Re-run (the fetch at startup will re-derive the unpushed "
            "list), or push the branch tip rather than an older commit."
        )

    if (
        "gh001" in lowered
        or "exceeds github's file size limit" in lowered
        or "large files detected" in lowered
    ):
        return (
            "a file in the pushed history exceeds the remote's per-file size limit. "
            "The blob is already committed, so it must be removed from the commits "
            "that contain it -- splitting the working-tree copy is not enough."
        )

    if "pre-receive hook declined" in lowered:
        return "the remote's pre-receive hook rejected the push."

    if "permission denied" in lowered or "authentication failed" in lowered:
        return "authentication/permission failure talking to the remote."

    return None


def _run_push_streaming(
    push_args: List[str], env: Optional[Dict[str, str]]
) -> Tuple[int, str]:
    """
    Run a push, streaming git's progress live while also capturing it.

    The output has to be captured so failures can be classified, but git writes
    progress using carriage returns with no trailing newline -- reading by line
    would show the operator nothing until a multi-minute transfer finished.
    Reading available chunks via read1() keeps the live progress intact.
    """
    proc = subprocess.Popen(
        ["git"] + push_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    chunks: List[str] = []
    if proc.stdout is not None:
        while True:
            raw = proc.stdout.read1(4096)
            if not raw:
                break
            text = raw.decode("utf-8", errors="replace")
            chunks.append(text)
            sys.stderr.write(text)
            sys.stderr.flush()
    proc.wait()
    return proc.returncode, "".join(chunks)


def find_oversized_blobs(
    rev_range: str, limit_bytes: int
) -> List[Tuple[str, int, str]]:
    """
    Return (blob_sha, size_bytes, path) for blobs in rev_range above limit_bytes.

    split_oversized_files() only ever inspects the working tree, so a file that
    was committed directly -- bypassing this script -- is invisible to it and
    silently makes the whole branch unpushable.  Scanning the objects the push
    would actually upload catches that locally, before the transfer.
    """
    rev_list = subprocess.run(
        ["git", "rev-list", "--objects", rev_range],
        capture_output=True,
        text=True,
    )
    if rev_list.returncode != 0 or not rev_list.stdout.strip():
        return []

    check = subprocess.run(
        [
            "git",
            "cat-file",
            "--batch-check=%(objecttype) %(objectsize) %(objectname) %(rest)",
        ],
        input=rev_list.stdout,
        capture_output=True,
        text=True,
    )

    oversized: List[Tuple[str, int, str]] = []
    for line in check.stdout.splitlines():
        fields = line.split(" ", 3)
        if len(fields) < 4 or fields[0] != "blob":
            continue
        try:
            size = int(fields[1])
        except ValueError:
            continue
        path = fields[3].strip()
        if size > limit_bytes and path:
            oversized.append((fields[2], size, path))

    oversized.sort(key=lambda item: item[1], reverse=True)
    return oversized


def _format_size(num_bytes: float) -> str:
    """Render a byte count at a sensible unit, so small limits don't print as '0 MiB'."""
    for unit, scale in (("MiB", 1024 * 1024), ("KiB", 1024)):
        if num_bytes >= scale:
            return f"{num_bytes / scale:.1f} {unit}"
    return f"{int(num_bytes)} B"


def _commits_introducing_blob(blob_sha: str, rev_range: str) -> List[str]:
    """Return `git log --oneline` entries in rev_range that add/remove blob_sha."""
    result = subprocess.run(
        ["git", "log", "--oneline", f"--find-object={blob_sha}", rev_range],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def ensure_history_within_remote_file_limit(
    remote_name: str, branch: str, limit_bytes: int
) -> None:
    """Abort with an actionable report if the pending push carries an oversized blob."""
    if _remote_tracking_ref_exists(remote_name, branch):
        rev_range = f"{remote_name}/{branch}..{branch}"
    else:
        rev_range = branch

    oversized = find_oversized_blobs(rev_range, limit_bytes)
    if not oversized:
        return

    sys.stdout.flush()  # keep the report below the progress lines already printed
    print(
        f"Error: {len(oversized)} file(s) in the commits about to be pushed exceed the "
        f"remote's {_format_size(limit_bytes)} per-file limit.\n"
        "The remote refuses the ENTIRE push for these -- including every unrelated "
        "commit on the branch -- and no retry or push option can bypass it.\n",
        file=sys.stderr,
    )
    for blob_sha, size, path in oversized:
        print(f"  {_format_size(size)}  {path}", file=sys.stderr)
        for line in _commits_introducing_blob(blob_sha, rev_range):
            print(f"      introduced by {line}", file=sys.stderr)

    print(
        "\nThese blobs are already committed, so splitting the working-tree copy is not\n"
        "enough: they must be removed from the commits that contain them. Rewrite those\n"
        "commits so they carry `<name>.partN<ext>` parts instead of the whole file\n"
        "(this script splits automatically for files it commits itself), then re-run.\n"
        "Verify a split with a sha256 round-trip before deleting the original, and check\n"
        "for consumers of the pre-split path first -- splitting deletes it.",
        file=sys.stderr,
    )
    sys.exit(1)


def push_refspec(
    refspec: str,
    push_retries: int,
    push_retry_delay_seconds: float,
    force_with_lease: bool,
    ssh_keepalive_interval_seconds: int,
    ssh_keepalive_count_max: int,
    push_pack_threads: int,
    push_compression: int,
    push_pack_window: int,
) -> None:
    remote_url = get_remote_url(REMOTE_NAME)
    push_env = _with_ssh_keepalive_env(
        remote_url=remote_url,
        keepalive_interval_seconds=ssh_keepalive_interval_seconds,
        keepalive_count_max=ssh_keepalive_count_max,
    )

    # Large binary datasets typically compress poorly; lower pack CPU overhead
    # keeps long SSH sessions more stable on flaky links.
    push_args = [
        "-c",
        f"pack.threads={push_pack_threads}",
        "-c",
        f"core.compression={push_compression}",
        "-c",
        f"pack.window={push_pack_window}",
        "push",
        "--progress",
    ]
    if force_with_lease:
        push_args.append("--force-with-lease")
    push_args.extend([REMOTE_NAME, refspec])

    attempts = max(1, push_retries)
    for attempt in range(1, attempts + 1):
        returncode, output = _run_push_streaming(push_args, push_env)
        if returncode == 0:
            return

        # A non-fast-forward or an oversized file is deterministic: the same
        # push will be refused every time, so fail immediately with the reason
        # rather than sleeping through the retry budget first.
        permanent = classify_push_failure(output)
        if permanent is not None:
            raise RuntimeError(f"git push {refspec} rejected -- {permanent}")

        if attempt >= attempts:
            break

        backoff = push_retry_delay_seconds * (2 ** (attempt - 1))
        print(
            f"Push failed (attempt {attempt}/{attempts}), looks transient. "
            f"Retrying in {backoff:.1f}s...",
            file=sys.stderr,
        )
        time.sleep(backoff)

    raise RuntimeError(f"git push {refspec} failed after {attempts} attempt(s)")


def push_branch(
    branch: str,
    push_retries: int,
    push_retry_delay_seconds: float,
    force_with_lease: bool,
    ssh_keepalive_interval_seconds: int,
    ssh_keepalive_count_max: int,
    push_pack_threads: int,
    push_compression: int,
    push_pack_window: int,
) -> None:
    push_refspec(
        refspec=branch,
        push_retries=push_retries,
        push_retry_delay_seconds=push_retry_delay_seconds,
        force_with_lease=force_with_lease,
        ssh_keepalive_interval_seconds=ssh_keepalive_interval_seconds,
        ssh_keepalive_count_max=ssh_keepalive_count_max,
        push_pack_threads=push_pack_threads,
        push_compression=push_compression,
        push_pack_window=push_pack_window,
    )


def preflight_remote_sync(
    branch: str,
    push_retries: int,
    push_retry_delay_seconds: float,
    force_with_lease: bool,
    ssh_keepalive_interval_seconds: int,
    ssh_keepalive_count_max: int,
    push_pack_threads: int,
    push_compression: int,
    push_pack_window: int,
    skip_fetch: bool = False,
    remote_file_limit_bytes: int = DEFAULT_REMOTE_FILE_LIMIT_BYTES,
) -> None:
    """
    Ensure we do not keep creating commits while old ones are still unpushed.
    """
    # Do this BEFORE computing divergence: a stale tracking ref yields an
    # unpushed list containing commits the remote already has, and pushing one
    # of those is a permanent non-fast-forward.
    if not skip_fetch:
        print(f"Fetching {REMOTE_NAME}/{branch} to refresh divergence...")
        fetch_remote_branch(REMOTE_NAME, branch)

    ahead, behind = get_branch_divergence(REMOTE_NAME, branch)

    if behind > 0 and not force_with_lease:
        print(
            f"Error: local '{branch}' is behind {REMOTE_NAME}/{branch} by {behind} commit(s).\n"
            "Pull/rebase first, or rerun with --force-with-lease if you explicitly "
            "intend to overwrite remote history.",
            file=sys.stderr,
        )
        sys.exit(1)

    if ahead <= 0:
        return

    # Catch an already-committed oversized blob here, rather than after
    # uploading a pack the remote is going to refuse in full.
    ensure_history_within_remote_file_limit(
        REMOTE_NAME, branch, remote_file_limit_bytes
    )

    print(
        f"Branch already has {ahead} unpushed commit(s); pushing existing commits before batching..."
    )
    commits = _ahead_commit_hashes(REMOTE_NAME, branch)
    if not commits:
        commits = [branch]

    remote_ref = f"{REMOTE_NAME}/{branch}"
    have_remote_ref = _remote_tracking_ref_exists(REMOTE_NAME, branch)

    for idx, commit in enumerate(commits, start=1):
        if commit == branch:
            label = branch
            refspec = branch
        else:
            label = commit[:12]
            refspec = f"{commit}:refs/heads/{branch}"

            # Each successful push advances the tracking ref, so this also makes
            # a re-run after a partial failure resume instead of rewinding.
            if have_remote_ref and _is_ancestor(commit, remote_ref):
                print(
                    f"Skipping existing commit {idx}/{len(commits)} ({label}): "
                    f"already on {remote_ref}."
                )
                continue

        print(f"Pushing existing commit {idx}/{len(commits)} ({label})...")
        try:
            push_refspec(
                refspec=refspec,
                push_retries=push_retries,
                push_retry_delay_seconds=push_retry_delay_seconds,
                force_with_lease=force_with_lease,
                ssh_keepalive_interval_seconds=ssh_keepalive_interval_seconds,
                ssh_keepalive_count_max=ssh_keepalive_count_max,
                push_pack_threads=push_pack_threads,
                push_compression=push_compression,
                push_pack_window=push_pack_window,
            )
        except RuntimeError as exc:
            print(
                f"Error: could not push existing local commit {idx}/{len(commits)} before batching.\n{exc}",
                file=sys.stderr,
            )
            sys.exit(1)

def discover_changes(path_prefixes: List[str]) -> Dict[str, Change]:
    """
    Discover all changes relative to HEAD:
      - modifications and additions from `git diff --name-status -z HEAD`
      - deletions from the same
      - untracked files from `git ls-files --others --exclude-standard -z`
    """
    changes: Dict[str, Change] = {}

    diff_args = ["diff", "--name-status", "--no-renames", "-z", "HEAD"]
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
            if not path:
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


def exclude_changes_by_glob(
    changes: Dict[str, Change], exclude_globs: List[str]
) -> Dict[str, Change]:
    """Drop changed paths that match any shell-style glob."""
    if not exclude_globs:
        return changes

    filtered: Dict[str, Change] = {}
    excluded = 0
    for path, change in changes.items():
        if any(fnmatch(path, pattern) for pattern in exclude_globs):
            excluded += 1
            continue
        filtered[path] = change

    if excluded:
        print(
            f"Excluded {excluded} changed path(s) via --exclude-glob: "
            f"{', '.join(exclude_globs)}"
        )

    return filtered


def _safe_filesize(path: str) -> int:
    """Size the Git entry itself, never the target of a compatibility symlink."""
    try:
        return os.lstat(path).st_size
    except OSError:
        return 0


def split_oversized_file(path: str, max_file_bytes: int) -> List[str]:
    """
    Split a file that exceeds max_file_bytes into numbered parts.

    Given ``research/data/report.pdf`` the parts are named
    ``research/data/report.part1.pdf``, ``research/data/report.part2.pdf``, etc.

    Returns the list of part paths created on disk.  The original file is
    removed after a successful split.
    """
    if max_file_bytes < 1:
        raise ValueError('The split size must be at least one byte.')
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError(f'Only regular working-tree files can be split: {path}')
    file_size = os.path.getsize(path)
    num_parts = math.ceil(file_size / max_file_bytes)

    root, ext = os.path.splitext(path)
    part_paths: List[str] = []

    with open(path, "rb") as src:
        for i in range(1, num_parts + 1):
            part_path = f"{root}.part{i}{ext}"
            with open(part_path, "wb") as dst:
                remaining = max_file_bytes
                while remaining > 0:
                    chunk = src.read(min(remaining, 8 * 1024 * 1024))  # 8 MiB read buffer
                    if not chunk:
                        break
                    dst.write(chunk)
                    remaining -= len(chunk)
            part_paths.append(part_path)

    os.remove(path)
    return part_paths


def split_oversized_files(
    changes: Dict[str, Change], max_file_bytes: int
) -> Dict[str, Change]:
    """
    Find files exceeding max_file_bytes, split them into parts, and return
    an updated changes dict with the original entry replaced by entries for
    each part.
    """
    updated: Dict[str, Change] = {}

    for path, change in changes.items():
        if change.kind == "delete" or change.size_bytes <= max_file_bytes:
            updated[path] = change
            continue

        print(
            f"Splitting oversized file: {path} "
            f"({change.size_bytes / (1024*1024):.1f} MiB) ..."
        )
        part_paths = split_oversized_file(path, max_file_bytes)
        print(f"  -> created {len(part_paths)} part(s)")

        # Register a deletion for the original path (in case it was tracked).
        updated[path] = Change(path=path, kind="delete", size_bytes=0)

        for pp in part_paths:
            size = _safe_filesize(pp)
            updated[pp] = Change(path=pp, kind="add", size_bytes=size)

    return updated


def validate_file_sizes(changes: Dict[str, Change], max_batch_bytes: int) -> None:
    """Ensure no single file exceeds the configured batch size cap."""
    too_large: List[Tuple[str, int]] = []
    for change in changes.values():
        if change.kind == "delete":
            continue
        if change.size_bytes > max_batch_bytes:
            too_large.append((change.path, change.size_bytes))

    if too_large:
        print(
            "Error: some files still exceed the configured per-commit size cap "
            f"({max_batch_bytes / (1024*1024):.1f} MiB):",
            file=sys.stderr,
        )
        for path, size in too_large:
            print(f"  {path} ({size / (1024*1024):.2f} MiB)", file=sys.stderr)
        print(
            "Increase --max-batch-mib, or ensure oversized files can be split "
            "under that cap.",
            file=sys.stderr,
        )
        sys.exit(1)


def prepend_commit_hook_index_batch(
    changes: Dict[str, Change],
) -> Tuple[Optional[List[Change]], Dict[str, Change]]:
    """Pull hook policy/checker paths into a first batch when they changed."""
    batch = [changes[path] for path in COMMIT_HOOK_INDEX_PATHS if path in changes]
    if not batch:
        return None, changes
    remaining = {
        path: change
        for path, change in changes.items()
        if path not in COMMIT_HOOK_INDEX_PATHS
    }
    return batch, remaining


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
    # Keep logical chunks bounded for diagnostics and transient-path retries.
    # The pathspecs themselves are streamed over stdin, so their aggregate
    # encoded size is not constrained by the operating system's ARG_MAX.
    paths: List[str] = []
    deletions: List[str] = []
    skipped_missing = 0
    for change in batch:
        # Remove the exact index entry. git add cannot address a tracked child
        # after its former directory has become a compatibility symlink.
        if change.kind == "delete":
            deletions.append(change.path)
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
    chunk_size = 5000
    for start in range(0, len(deletions), chunk_size):
        payload = b''.join(os.fsencode(p) + b'\0' for p in deletions[start:start + chunk_size])
        result = _retry_index_operation(lambda: subprocess.run(
            ['git', 'update-index', '--force-remove', '-z', '--stdin'],
            input=payload, capture_output=True), 'stage deletions')
        if result.returncode:
            raise RuntimeError('git update-index failed: ' + os.fsdecode(result.stderr or b''))
    if not paths:
        return
    for start in range(0, len(paths), chunk_size):
        chunk = paths[start : start + chunk_size]
        # Use a direct subprocess call so we can gracefully handle the case
        # where all paths in the chunk are ignored by .gitignore (git exits
        # non‑zero in that case but this is not a real error for our purposes).
        result = _retry_index_operation(
            lambda: _run_git_with_pathspec_input(["--literal-pathspecs", "add", "-A"], chunk), 'git add')
        if result.returncode != 0:
            stderr = os.fsdecode(result.stderr or b"").strip()
            if "ignored by one of your .gitignore" in stderr:
                # All paths in this chunk are ignored; nothing to stage.
                # Log once and continue with remaining chunks.
                print(
                    "Skipping chunk with only .gitignored paths during git add.",
                    file=sys.stderr,
                )
                continue
            if "did not match any files" in stderr or "is beyond a symbolic link" in stderr:
                # Either a path disappeared between discovery and staging, or
                # one of its ancestor directories got externalized (symlinked
                # to the external drive, e.g. by a concurrent sibling session
                # or scheduled job) in that same window. Both are transient,
                # per-path staging failures, not reasons to abort the whole
                # batch. Retry with the offending paths stripped; loop in
                # case each retry only reveals the next offender.
                remaining = list(chunk)
                skipped: set = set()
                for _ in range(len(chunk)):
                    retry = _retry_index_operation(lambda: _run_git_with_pathspec_input(
                        ["--literal-pathspecs", "add", "-A"], remaining), 'git add')
                    if retry.returncode == 0:
                        break
                    retry_stderr = os.fsdecode(retry.stderr or b"").strip()
                    offenders = set(
                        re.findall(r"pathspec '([^']+)' did not match any files", retry_stderr)
                    ) | set(
                        re.findall(r"pathspec '([^']+)' is beyond a symbolic link", retry_stderr)
                    )
                    if not offenders:
                        raise RuntimeError(f"git add failed: {retry_stderr}")
                    skipped |= offenders
                    remaining = [p for p in remaining if p not in offenders]
                    if not remaining:
                        break
                if skipped:
                    print(
                        f"Skipped {len(skipped)} path(s) during git add "
                        f"(missing or beyond a symbolic link): {', '.join(sorted(skipped))}",
                        file=sys.stderr,
                    )
                continue
            raise RuntimeError(f"git add failed: {stderr}")


def unstage_batch(batch: List[Change]) -> None:
    """Return this script's paths to an unstaged state after a failed commit."""
    paths = sorted({change.path for change in batch})
    chunk_size = 5000
    for start in range(0, len(paths), chunk_size):
        chunk = paths[start : start + chunk_size]
        result = _retry_index_operation(lambda: _run_git_with_pathspec_input(
            ["--literal-pathspecs", "reset", "--quiet", "HEAD"], chunk), 'git reset')
        if result.returncode != 0:
            stderr = os.fsdecode(result.stderr or b"").strip()
            raise RuntimeError(f"git reset failed: {stderr}")


def _retry_index_operation(operation, label):
    """Retry native Git contention; never create a separate script lock."""
    for attempt in range(31):
        result = operation()
        detail = os.fsdecode(result.stderr or b'')
        if result.returncode == 0 or '.lock' not in detail or 'index' not in detail or attempt == 30:
            return result
        if _clear_stale_index_lock():
            continue
        print(f'{label}: Git index is busy; retrying in 2s ({attempt + 1}/30).', file=sys.stderr)
        time.sleep(2)
    return result


def _lock_has_no_owner(lock_path: Path, repo_root: Path) -> bool:
    """Inspect this lock and Git processes in this checkout, not other repos.

    Git can close its index-lock fd just before publishing it, so an empty
    open-file query alone is insufficient: also check Git process cwd paths.
    If ownership cannot be inspected, retain the native lock.
    """
    try:
        owners = subprocess.run(['lsof', '-t', '--', str(lock_path)],
                                capture_output=True, text=True, timeout=5)
        if owners.returncode not in (0, 1) or owners.stdout.strip() or owners.stderr.strip():
            return False
        processes = subprocess.run(['ps', '-axo', 'pid=,comm='],
                                   capture_output=True, text=True, timeout=5)
        if processes.returncode:
            return False
        pids = []
        for line in processes.stdout.splitlines():
            fields = line.strip().split(None, 1)
            if len(fields) == 2 and Path(fields[1]).name == 'git':
                pids.append(fields[0])
        if pids:
            cwd = subprocess.run(['lsof', '-a', '-p', ','.join(pids), '-d', 'cwd', '-Fpn'],
                                 capture_output=True, text=True, timeout=5)
            if cwd.returncode not in (0, 1) or cwd.stderr.strip():
                return False
            for line in cwd.stdout.splitlines():
                if line.startswith('n') and Path(line[1:]).resolve().is_relative_to(repo_root):
                    return False
    except (OSError, subprocess.TimeoutExpired):
        return False
    return True


def _clear_stale_index_lock() -> bool:
    """Recover a confirmed abandoned native index lock, including worktrees."""
    paths = subprocess.run(['git', 'rev-parse', '--show-toplevel', '--git-path', 'index'],
                           capture_output=True, text=True)
    if paths.returncode or len(paths.stdout.splitlines()) != 2:
        return False
    root, index = paths.stdout.splitlines()
    lock_path = Path(os.path.abspath(index) + '.lock')
    try:
        before = lock_path.lstat()
        if not stat.S_ISREG(before.st_mode):
            return False
        if not _lock_has_no_owner(lock_path, Path(root).resolve()):
            return False
        after = lock_path.lstat()
        if any(getattr(before, key) != getattr(after, key)
               for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')):
            return False
        lock_path.unlink()
    except OSError:
        return False
    print(f'Removed abandoned Git index lock: {lock_path}', file=sys.stderr)
    return True


def _commit_batch(batch: List[Change], *, bypass_commit_hooks: bool) -> None:
    """Create one commit for a staged batch, keeping hook output on the exception."""
    commit_args = []
    if bypass_commit_hooks:
        # --no-verify alone still runs prepare-commit-msg and post-commit hooks.
        # A per-command setting leaves the installed hook files/config intact.
        commit_args.extend(['-c', 'core.hooksPath=' + os.devnull])
    commit_args.append('commit')
    commit_args.extend(["-m", COMMIT_MESSAGE])
    last_detail = ""
    for attempt in range(1, 31):
        result = subprocess.run(
            ["git", *commit_args], capture_output=True, text=True
        )
        if result.stdout:
            sys.stdout.write(result.stdout)
            if not result.stdout.endswith("\n"):
                sys.stdout.write("\n")
        if result.stderr:
            sys.stderr.write(result.stderr)
            if not result.stderr.endswith("\n"):
                sys.stderr.write("\n")
        if result.returncode == 0:
            return
        last_detail = (result.stderr or result.stdout or "").strip()
        if "index.lock" not in last_detail:
            break
        print(
            f"index.lock busy; retrying git commit in 2s ({attempt}/30)",
            file=sys.stderr,
        )
        time.sleep(2)
        _clear_stale_index_lock()
    raise RuntimeError(f"git commit -m {COMMIT_MESSAGE} failed: {last_detail}")


def _hook_rejected(error: BaseException) -> bool:
    text = str(error)
    return any(marker in text for marker in HOOK_REJECT_MARKERS)


def commit_and_push_batches(
    batches: List[List[Change]],
    branch: str,
    push_retries: int,
    push_retry_delay_seconds: float,
    force_with_lease: bool,
    ssh_keepalive_interval_seconds: int,
    ssh_keepalive_count_max: int,
    push_pack_threads: int,
    push_compression: int,
    push_pack_window: int,
    bypass_commit_hooks: bool = False,
) -> None:
    _clear_stale_index_lock()
    if not batches:
        print("No changes to commit.")
        return

    deferred: List[Change] = []
    idx = 0
    while idx < len(batches):
        batch = batches[idx]
        total_batches = len(batches)
        print(f"\n=== Processing batch {idx + 1}/{total_batches} ===")
        _clear_stale_index_lock()
        batch_size = sum(
            c.size_bytes for c in batch if c.kind != "delete"
        )
        print(
            f"Staging {len(batch)} paths "
            f"(approx {batch_size / (1024*1024):.2f} MiB of data)..."
        )
        stage_batch(batch)
        if not has_staged_changes():
            print(
                f"No staged changes for batch {idx + 1}; skipping commit/push.",
                file=sys.stderr,
            )
            idx += 1
            continue

        print(f"Committing batch {idx + 1}/{total_batches}...")
        head_before_commit = run_git(["rev-parse", "HEAD"]).strip()
        try:
            _commit_batch(batch, bypass_commit_hooks=bypass_commit_hooks)
        except RuntimeError as exc:
            if run_git(["rev-parse", "HEAD"]).strip() == head_before_commit:
                unstage_batch(batch)
                print(
                    "Commit failed; returned this batch to the unstaged working tree.",
                    file=sys.stderr,
                )
            if _hook_rejected(exc) and not bypass_commit_hooks:
                if len(batch) > 1:
                    print(
                        "Reporting hook rejected a multi-path batch; "
                        "retrying each path in its own commit.",
                        file=sys.stderr,
                    )
                    batches[idx : idx + 1] = [[change] for change in batch]
                    continue
                print(
                    "Deferring hook-rejected path: " + batch[0].path,
                    file=sys.stderr,
                )
                deferred.append(batch[0])
                idx += 1
                continue
            raise

        print(f"Pushing batch {idx + 1}/{total_batches} to {REMOTE_NAME}/{branch}...")
        try:
            push_branch(
                branch=branch,
                push_retries=push_retries,
                push_retry_delay_seconds=push_retry_delay_seconds,
                force_with_lease=force_with_lease,
                ssh_keepalive_interval_seconds=ssh_keepalive_interval_seconds,
                ssh_keepalive_count_max=ssh_keepalive_count_max,
                push_pack_threads=push_pack_threads,
                push_compression=push_compression,
                push_pack_window=push_pack_window,
            )
        except RuntimeError as exc:
            print(
                f"\nError: push for batch {idx + 1} failed.\n"
                f"{exc}\n"
                "The commit is created locally but not pushed. "
                "Fix the network/remote issue and rerun this script (it will attempt "
                "to push existing local commits before creating new ones), "
                "or push manually.",
                file=sys.stderr,
            )
            sys.exit(1)
        idx += 1

    if deferred:
        print(
            f"\nDeferred {len(deferred)} path(s) rejected by the reporting hook:",
            file=sys.stderr,
        )
        for change in deferred:
            print(f"  {change.path}", file=sys.stderr)
        raise RuntimeError(
            f"{len(deferred)} path(s) remain uncommitted because the reporting "
            "hook rejected them; other batches were committed and pushed."
        )


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
        "--exclude-glob",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "Shell-style path glob to exclude from discovery, splitting, and "
            "batching. Repeat as needed, for example "
            "--exclude-glob 'data/scanner*.db*'."
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
    parser.add_argument(
        '--run-commit-hooks', action='store_true',
        help='Opt in to repository commit hooks. By default this storage command runs without commit-hook gates.',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview changes, required splits and batch counts without fetching, editing files or the index, committing or pushing.',
    )
    parser.add_argument(
        "--max-file-mib",
        type=float,
        default=DEFAULT_MAX_FILE_BYTES / (1024 * 1024),
        help=(
            "Maximum MiB per individual file. Files exceeding this are "
            "automatically split into numbered parts (e.g. file.part1.pdf). "
            "If set above --max-batch-mib, --max-batch-mib is used as the "
            "effective split limit. "
            f"Default: {DEFAULT_MAX_FILE_BYTES / (1024*1024):.0f} MiB."
        ),
    )
    parser.add_argument(
        "--push-retries",
        type=int,
        default=DEFAULT_PUSH_RETRIES,
        help=(
            "How many times to attempt each push before failing. "
            f"Default: {DEFAULT_PUSH_RETRIES}."
        ),
    )
    parser.add_argument(
        "--push-retry-delay-sec",
        type=float,
        default=DEFAULT_PUSH_RETRY_DELAY_SECONDS,
        help=(
            "Seconds to wait between push retries. "
            f"Default: {DEFAULT_PUSH_RETRY_DELAY_SECONDS:.1f}."
        ),
    )
    parser.add_argument(
        "--force-with-lease",
        action="store_true",
        help=(
            "Use `git push --force-with-lease` instead of a normal fast-forward "
            "push. Only use this when you intentionally need to rewrite remote history."
        ),
    )
    parser.add_argument(
        "--ssh-keepalive-interval-sec",
        type=int,
        default=DEFAULT_SSH_KEEPALIVE_INTERVAL_SECONDS,
        help=(
            "For SSH remotes, seconds between keepalive probes while pushing. "
            f"Default: {DEFAULT_SSH_KEEPALIVE_INTERVAL_SECONDS}."
        ),
    )
    parser.add_argument(
        "--ssh-keepalive-count-max",
        type=int,
        default=DEFAULT_SSH_KEEPALIVE_COUNT_MAX,
        help=(
            "For SSH remotes, number of unanswered keepalive probes before "
            "disconnect. Default: "
            f"{DEFAULT_SSH_KEEPALIVE_COUNT_MAX}."
        ),
    )
    parser.add_argument(
        "--push-pack-threads",
        type=int,
        default=DEFAULT_PUSH_PACK_THREADS,
        help=(
            "Override `pack.threads` for pushes. Lower values reduce CPU spikes "
            "during object packing. Default: "
            f"{DEFAULT_PUSH_PACK_THREADS}."
        ),
    )
    parser.add_argument(
        "--push-compression",
        type=int,
        default=DEFAULT_PUSH_COMPRESSION,
        help=(
            "Override `core.compression` for pushes (-1..9). "
            "Use 0 for large binary files to reduce packing time. Default: "
            f"{DEFAULT_PUSH_COMPRESSION}."
        ),
    )
    parser.add_argument(
        "--push-pack-window",
        type=int,
        default=DEFAULT_PUSH_PACK_WINDOW,
        help=(
            "Override `pack.window` for pushes. Lower values reduce delta-search "
            "work for large binaries. Default: "
            f"{DEFAULT_PUSH_PACK_WINDOW}."
        ),
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help=(
            "Do not fetch the remote branch before computing divergence. Only for "
            "offline use: a stale tracking ref makes the unpushed-commit list wrong "
            "and can produce unfixable non-fast-forward pushes."
        ),
    )
    parser.add_argument(
        "--remote-file-limit-mib",
        type=float,
        default=DEFAULT_REMOTE_FILE_LIMIT_BYTES / (1024 * 1024),
        help=(
            "Hard per-file size limit enforced by the remote. Commits about to be "
            "pushed are scanned for blobs above this and the run aborts locally with "
            "the offending paths. Default: "
            f"{DEFAULT_REMOTE_FILE_LIMIT_BYTES / (1024*1024):.0f} (GitHub's limit)."
        ),
    )
    parser.add_argument(
        "--strict-research-guard",
        action="store_true",
        help=(
            "Deprecated compatibility option; research governance is no longer a "
            "Git commit gate and this option has no effect."
        ),
    )
    parser.add_argument(
        "--ignore-research-guard",
        action="store_true",
        help=(
            "Deprecated compatibility option; research governance is no longer a "
            "Git commit gate and this option has no effect."
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])

    for name in ('max_batch_mib', 'max_file_mib', 'remote_file_limit_mib'):
        value = getattr(args, name)
        if not math.isfinite(value) or value * 1024 * 1024 < 1:
            raise ValueError('--' + name.replace('_', '-') + ' must be a finite size of at least one byte.')
    max_batch_bytes = int(args.max_batch_mib * 1024 * 1024)
    max_file_bytes = int(args.max_file_mib * 1024 * 1024)

    if args.strict_research_guard or args.ignore_research_guard:
        print(
            "Note: research-guard options are retired compatibility no-ops; Git "
            "batching no longer runs research governance.",
            file=sys.stderr,
        )
    if args.push_retries < 1:
        print("Error: --push-retries must be >= 1.", file=sys.stderr)
        sys.exit(1)
    if args.push_retry_delay_sec < 0:
        print("Error: --push-retry-delay-sec must be >= 0.", file=sys.stderr)
        sys.exit(1)
    if args.ssh_keepalive_interval_sec < 1:
        print("Error: --ssh-keepalive-interval-sec must be >= 1.", file=sys.stderr)
        sys.exit(1)
    if args.ssh_keepalive_count_max < 1:
        print("Error: --ssh-keepalive-count-max must be >= 1.", file=sys.stderr)
        sys.exit(1)
    if args.push_pack_threads < 1:
        print("Error: --push-pack-threads must be >= 1.", file=sys.stderr)
        sys.exit(1)
    if args.push_compression < -1 or args.push_compression > 9:
        print("Error: --push-compression must be between -1 and 9.", file=sys.stderr)
        sys.exit(1)
    if args.push_pack_window < 0:
        print("Error: --push-pack-window must be >= 0.", file=sys.stderr)
        sys.exit(1)
    if args.remote_file_limit_mib <= 0:
        print("Error: --remote-file-limit-mib must be > 0.", file=sys.stderr)
        sys.exit(1)

    remote_file_limit_bytes = int(args.remote_file_limit_mib * 1024 * 1024)

    branch = get_current_branch()
    if not args.dry_run:
        _clear_stale_index_lock()
        preflight_remote_sync(
            branch=branch,
            push_retries=args.push_retries,
            push_retry_delay_seconds=args.push_retry_delay_sec,
            force_with_lease=args.force_with_lease,
            ssh_keepalive_interval_seconds=args.ssh_keepalive_interval_sec,
            ssh_keepalive_count_max=args.ssh_keepalive_count_max,
            push_pack_threads=args.push_pack_threads,
            push_compression=args.push_compression,
            push_pack_window=args.push_pack_window,
            skip_fetch=args.skip_fetch,
            remote_file_limit_bytes=remote_file_limit_bytes,
        )
        ensure_clean_index()
    if not args.run_commit_hooks:
        print('Repository commit hooks are disabled for this batching command; --run-commit-hooks opts in.')

    print("Discovering changes relative to HEAD...")
    effective_exclude_globs = [*DEFAULT_EXCLUDE_GLOBS, *args.exclude_glob]

    changes = exclude_changes_by_glob(
        discover_changes(args.paths), effective_exclude_globs
    )
    if not changes:
        print("No changes detected; nothing to do.")
        return

    if args.paths:
        print(f"Found {len(changes)} changed paths under: {', '.join(args.paths)}")
    else:
        print(f"Found {len(changes)} changed paths.")

    effective_max_file_bytes = min(max_file_bytes, max_batch_bytes)
    if effective_max_file_bytes < max_file_bytes:
        print(
            "Note: --max-file-mib is larger than --max-batch-mib; "
            f"using {effective_max_file_bytes / (1024*1024):.1f} MiB as the "
            "effective split limit.",
            file=sys.stderr,
        )

    # A split limit at or above the remote's hard per-file limit would let this
    # script commit a file the remote then refuses, recreating by hand exactly
    # the situation the history scan exists to catch.
    if effective_max_file_bytes >= remote_file_limit_bytes:
        # 90% of the limit, which for GitHub's 100 MiB is exactly the 90 MiB
        # part size this repo's existing split artifacts already use.
        clamped = max(1, int(remote_file_limit_bytes * 0.9))
        print(
            f"Note: effective split limit "
            f"({effective_max_file_bytes / (1024*1024):.1f} MiB) is at or above the "
            f"remote's {remote_file_limit_bytes / (1024*1024):.0f} MiB per-file limit; "
            f"clamping to {clamped / (1024*1024):.1f} MiB so committed files stay "
            "pushable.",
            file=sys.stderr,
        )
        effective_max_file_bytes = clamped

    if args.dry_run:
        preview = {}
        splits = []
        for path, change in changes.items():
            if change.kind != 'delete' and change.size_bytes > effective_max_file_bytes:
                count = math.ceil(change.size_bytes / effective_max_file_bytes)
                splits.append({'path': path, 'bytes': change.size_bytes, 'parts': count})
                root, ext = os.path.splitext(path)
                preview[path] = Change(path, 'delete', 0)
                for i in range(count):
                    part = f'{root}.part{i + 1}{ext}'
                    preview[part] = Change(part, 'add', min(effective_max_file_bytes,
                                                         change.size_bytes - i * effective_max_file_bytes))
            else:
                preview[path] = change
        print(json.dumps({'dry_run': True, 'branch': branch,
                          'changed_paths': len(changes),
                          'symlinks': sum(c.kind != 'delete' and os.path.islink(c.path) for c in changes.values()),
                          'deletions': sum(c.kind == 'delete' for c in changes.values()),
                          'estimated_batches': len(batch_changes(preview, max_batch_bytes)),
                          'max_batch_bytes': max_batch_bytes, 'required_working_tree_splits': splits,
                          'commit_hooks': 'ENABLED' if args.run_commit_hooks else 'DISABLED',
                          'remote_checked': False, 'files_or_index_modified': False}, indent=2))
        return

    changes = split_oversized_files(changes, effective_max_file_bytes)
    # Splitting can turn an oversized untracked file into part files that may
    # already exist at HEAD, so re-discover actual diffs before batching.
    changes = exclude_changes_by_glob(
        discover_changes(args.paths), effective_exclude_globs
    )
    if not changes:
        print("No effective changes detected after splitting; nothing to do.")
        return

    validate_file_sizes(changes, max_batch_bytes)

    hook_batch = None
    if args.run_commit_hooks:
        hook_batch, changes = prepend_commit_hook_index_batch(changes)
    batches = batch_changes(changes, max_batch_bytes)
    if hook_batch:
        batches = [hook_batch] + batches
        print(
            f"Committing {len(hook_batch)} local-hook index path(s) first so "
            "later batches can read the reporting policy from Git."
        )
    print(
        f"Planned {len(batches)} batch(es) with per-commit limit of "
        f"{max_batch_bytes / (1024*1024):.1f} MiB."
    )

    commit_and_push_batches(
        batches=batches,
        branch=branch,
        push_retries=args.push_retries,
        push_retry_delay_seconds=args.push_retry_delay_sec,
        force_with_lease=args.force_with_lease,
        ssh_keepalive_interval_seconds=args.ssh_keepalive_interval_sec,
        ssh_keepalive_count_max=args.ssh_keepalive_count_max,
        push_pack_threads=args.push_pack_threads,
        push_compression=args.push_compression,
        push_pack_window=args.push_pack_window,
        bypass_commit_hooks=not args.run_commit_hooks,
    )
    print("\nAll batches committed and pushed successfully.")


if __name__ == "__main__":
    main()
