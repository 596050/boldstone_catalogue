# Large-data batch commits

Run from the repository root with system Python; no virtual environment or
third-party Python packages are needed:

```sh
python3 utils/git/batch_commit_large_data.py --max-batch-mib 90
```

This commits working-tree changes in batches and pushes each commit to the
configured `origin` branch. Files larger than the effective size cap are split
into numbered parts using the existing splitter; the original is removed after
splitting. Symlinks are committed as links and their targets are never split.
Tracked children removed by a directory-to-symlink move are removed directly
from the index, so relocated research bundles can be committed normally.

Repository **commit hooks are opt-in** for this utility. The default command
sets `core.hooksPath` only for each `git commit`; it does not edit Git config or
installed hooks. Use `--run-commit-hooks` to run them. Git storage does not verify
scientific results: run the independent reporting checks separately before
making research performance claims. Existing remote authentication, remote file
limits, fast-forward rules and the configured pre-push hook still apply.

There is no script lock, manual lease, research admission check or requirement
to manually clear existing staging. If staging is present, its exact tree is
saved in a local `refs/batch-commit/index-backups/...` ref before the working-tree
changes are regrouped. Those refs are not pushed by this command. The backup
ref is printed, and a previous staged file can be recovered with
`git show <backup-ref>:<path>`. An unfinished Git merge/rebase/cherry-pick must
be completed before its staged content can be regrouped.

Git retains its own locks for writing the index and refs. The script retries
index contention and removes an abandoned index lock only after inspecting its
open-file owner and Git processes in that checkout. A Git process in another
repository does not block recovery. Linked worktrees use their own actual index
path. Active or uninspectable locks remain intact; no process is killed and no
repository file is unlocked by changing permissions.

Preview without fetching, splitting, staging, committing or pushing:

```sh
python3 utils/git/batch_commit_large_data.py --max-batch-mib 90 --dry-run
```

Optional positional paths restrict the scope. `--exclude-glob` adds exclusions;
the existing defaults exclude credentials, mutable data caches and lock files.
Run one batching process per checkout: each batch stages and commits through
the shared Git index. Changes to this script apply to newly started processes.
