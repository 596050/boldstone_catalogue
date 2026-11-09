# promoted_helpers/ — patterns rescued from ad-hoc /tmp scripts

These started life as `/tmp/*.py` scripts thrown together during the
2026-06-04/05 cluster bring-up. Each embodies a reusable pattern worth
keeping; they've been moved into the repo under stable names to prevent
the "institutional knowledge vanishes" problem flagged in REFACTOR_PLAN.md.

Promoted as-is — they still hardcode hosts/paths from the original session.
**TODO before relying on any of them**: parameterise hosts via `hosts.json`,
swap inline SSH+base64 patterns for `from lib.remote import ps`, add
argparse where appropriate.

| script | what it does | original pattern |
| --- | --- | --- |
| `verify_remote_pipelines_alive.py` | For each "running" job on a remote, samples the cohort dir size at T and T+30s to detect whether the pipeline is actually producing or just stale-marked. Surfaces wrapper-dead-but-children-alive cases. | Used 2026-06-05 to find that kenne jobs 48 + 49 were producing despite dead wrappers. |
| `build_libemd_remote.py` | SSH+make wrapper that compiles `libemd.dll` on a remote with PATH explicitly set to `C:\msys64\ucrt64\bin`. | Used to build libemd on scan-new after `fleet.py sync`. |
| `probe_remote_disk_cleanup.py` | Enumerates all `*_chunks/`, temp dirs, pip cache, etc. on a remote and reports sizes — what's safe to delete vs. what's source data. | Used to find 9-15 GB cleanup opportunities on kenne. |
| `check_remote_disk_free.py` | Minimal disk-free probe via lib.remote.ps. Use this from a watcher to fire `disk_pressure_collect` before things crash. | Used as a smoke check after every cleanup pass. |
| `finalize_remote_cleanup.py` | Coordination script for "stop processing + migrate uniques + delete bulk" workflow. Last-stage cleanup. | Used 2026-06-05 to drain cdec's fleet-offload dir. |

## Pattern: how to clean each up before relying on it

```python
# BEFORE (ad-hoc /tmp script — what's in here now):
import sys, subprocess, base64, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib.remote import ps
script = "..."
r = subprocess.run([...long ssh invocation...])

# AFTER (using the shared lib):
from lib.remote import ps
r = ps("kenne", script, identity="~/.ssh/id_ed25519_kenne",
       user="kenne", connect_timeout=15)
```

## Why these aren't tested yet

These are operator tools that fundamentally talk to remote machines. Mocking
SSH for unit tests is high-effort, low-value. Smoke-test them by hand on a
real remote when relying on them; promote individual functions into
`lib/remote.py` if they become hot.
