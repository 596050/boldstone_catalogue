# utils/offload_network/ — refactor plan + status

Tracks the P0–P3 work from the 2026-06-05 scripts audit. P0 and the highest-leverage
P1/P2/P3 items have shipped; remaining items are scoped for follow-up sessions.

## ✅ Shipped (this session)

### P0 — Reliability

| item | file(s) | status |
| --- | --- | --- |
| `state.json` lockfile + atomic writes | `fleet/state.py`, `fleet/__init__.py` | ✅ DONE |
| Schema validation (`FleetJob`, `FleetState`, `WorkStatus`) | `fleet/state.py` | ✅ DONE |
| Pytest test suite (32 tests) covering state machine + lock + path + rsync filter | `tests/test_state_machine.py`, `tests/test_state_lock.py`, `tests/test_path_resolution.py`, `tests/test_rsync_filter.py`, `tests/conftest.py` | ✅ DONE — all 32 pass |
| Env-driven external path resolution (no hardcoded `/Volumes/Untitled/offload_data/`) | `fleet/paths.py` | ✅ DONE |

### P1 — Structure

| item | file(s) | status |
| --- | --- | --- |
| Move date-stamped one-shot launches out of root | `launches/2026-06-02/` (8 scripts moved in) | ✅ DONE |
| Move top-level orphan shell scripts | same `launches/2026-06-02/` | ✅ DONE |
| Document the new `launches/` convention | `launches/README.md` | ✅ DONE |
| `fleet/` package skeleton (state.py + paths.py + __init__.py) | `fleet/` | ✅ DONE (skeleton only; commands/ TODO) |

### P2 — Quality of life

| item | file(s) | status |
| --- | --- | --- |
| Centralised logging helper (`~/.fleet/logs/<YYYYMMDD>/<script>.log` + rotation) | `lib/logging_helper.py` | ✅ DONE |
| This refactor plan as a living doc | `REFACTOR_PLAN.md` | ✅ DONE |

### P3 — Promote ad-hoc

| ad-hoc script | promoted to | status |
| --- | --- | --- |
| `/tmp/gap_analysis_external.py` | `audit_external_gaps.py` | ✅ DONE |
| `/tmp/audit_other_machines.py` | (already → `remote_state_audit.py`) | ✅ DONE prior |
| `/tmp/verify_scanxeon_cohorts_on_external.py` | → `verify_before_delete.py` | ⏳ TODO |
| `/tmp/probe_kenne_freeup.py` | → `disk_cleanup_recommend.py` | ⏳ TODO |
| `/tmp/verify_active_jobs.py` | extend `cluster_state.reconcile` | ⏳ TODO |

## ✅ Shipped (2026-06-05 second pass)

### Closing the race — all 3 state.json callers now share LOCK_EX

| caller | before | after |
| --- | --- | --- |
| `fleet.py` | direct `json.loads(STATE_PATH.read_text())` | delegates to `fleet.state.load_state()` / `save_state()` / `mutate_state()` |
| `cluster_state/recover.py` | `_load_state`/`_save_state` direct IO | same as above |
| `trading_common/orchestrator/import_state.py` | `json.loads(_FLEET_STATE.read_text())` | same as above |

Sanity-check command: `python3 -c "from trading_common.cluster_state.recover import _fleet_state as cs; from trading_common.orchestrator.import_state import _fleet_state as orch; assert cs.lock_path() == orch.lock_path()"` — passes.

### Shared `lib.remote.ps()` adoption

| caller | before | after |
| --- | --- | --- |
| `remote_state_audit.py` | reimplemented `base64.b64encode(...utf-16-le)` | `from lib.remote import ps` |
| `audit_external_gaps.py` | same reimplementation | `from lib.remote import ps` |

The shared `ps()` was extended with `identity=`, `user=`, `connect_timeout=`, `no_control_master=`, `text=` parameters so callers reaching hosts not in `~/.ssh/config` (e.g. probing scan-new by IP) work without rewriting their own SSH invocation.

### Package metadata (`pyproject.toml`)

Top-level `pyproject.toml` enables `pip install -e .` from `utils/offload_network/`. Console-script entries map `fleet`, `remote-state-audit`, `processing-report`, `audit-external`, `clean-chunks` to PATH after install. Carried mypy + ruff + pytest configs; per-package strictness on `fleet.*` and `lib.*` first.

### Logging wired in

| script | logs to (new) |
| --- | --- |
| `clean_kenne_chunks.py` | `~/.fleet/logs/<YYYY-MM-DD>/clean_kenne_chunks.log` |
| `auto_collect_watcher.sh` | `~/.fleet/logs/<YYYY-MM-DD>/auto_collect_watcher.log` (with `/tmp/` symlink for legacy callers) |

### Organisation — host bootstrap kit isolated

All 9 Windows-host setup scripts (+ `wg_fallback/`) moved under `host_bootstrap/` with its own README documenting the invariant *"nothing in here imports from sibling Python code."* Lets a fresh host be onboarded with zero fleet-offload footprint.

```
utils/offload_network/
├── fleet/                  # locked state.json IO + paths
├── lib/                    # remote.py + logging_helper.py (shared utilities)
├── host_bootstrap/         # NEW — self-contained remote setup kit
│   ├── README.md
│   ├── setup_windows_host.ps1
│   ├── setup_windows_host_macside.sh
│   ├── enable_ssh_scan_amd64_new.ps1
│   ├── bootstrap_windows.ps1
│   ├── install_tailscale_windows.ps1
│   ├── diagnose_*.ps1, fix_wintun_conflict.ps1
│   └── wg_fallback/        # moved here
├── tests/                  # pytest suite (32 tests, all passing)
├── launches/2026-06-02/    # date-stamped one-shots
├── fleet.py                # CLI entrypoint
├── pyproject.toml          # NEW — package metadata, mypy, ruff, pytest
└── (top-level runners: audit_external_gaps, clean_kenne_chunks,
     processing_report, remote_state_audit, remote_ps,
     remote_process_count, launch_detached, cluster_status)
```

## ✅ Shipped (2026-06-05 third pass)

| item | what shipped | verified by |
| --- | --- | --- |
| #1 install pyproject.toml | `install.sh` script that upgrades pip → setuptools 68 → `pip install -e .`. All 5 console scripts (`fleet`, `remote-state-audit`, `processing-report`, `audit-external`, `clean-chunks`) now on PATH. Required adding `setup.py` shim + fixing `[tool.setuptools]` table syntax + pointing entry to `fleet.__main__:main`. | `fleet --help` works from PATH |
| #2 broken `host_bootstrap/` refs | Fixed reference card in `OPERATIONS.md` + redundant exclusion in `pyproject.toml`. Other matches (`hosts.json`, `processing_report.py`) were descriptive mentions, not paths — left as-is. | grep confirms no path-references missing prefix |
| #3 + #6 schema unification | `trading_common/orchestrator/schema.py` now imports `WorkStatus` from `fleet.state` (via sys.path setup). Duplicate enum removed. `orch_ws is fleet_ws` returns `True`; orchestrator can round-trip `WRAPPER_DEAD_PIPELINE_UNKNOWN`. | `test_workstatus_unified_across_packages` + `test_orchestrator_imports_live_state_with_all_statuses` |
| #5 cluster_state + orchestrator tests | NEW `tests/test_state_lock_cross_package.py` with 4 tests covering: schema unification, shared `_load_state` paths, orchestrator round-trip of all statuses, all-3-packages-share-lock-path. | 36/36 tests pass |
| #7 promote ad-hoc /tmp scripts | NEW `promoted_helpers/` dir with 5 scripts: `verify_remote_pipelines_alive.py`, `build_libemd_remote.py`, `probe_remote_disk_cleanup.py`, `check_remote_disk_free.py`, `finalize_remote_cleanup.py`. README documents pattern + cleanup TODOs. | `ls promoted_helpers/` |
| #8 CI + pre-commit | `.github/workflows/test.yml` runs pytest + console-script smoke test + ruff (3 Python versions). `.pre-commit-config.yaml` adds trailing-ws/eof/yaml/toml/json hooks + ruff + local pytest gate. | yaml syntax valid |
| #9 `python -m fleet` | NEW `fleet/__main__.py` delegates to legacy `fleet.py` via `runpy.run_path`. Used as the pyproject entry-point too. | `python -m fleet --help` works |
| #10 PSScriptAnalyzer | NEW `host_bootstrap/PSScriptAnalyzerSettings.psd1` enables warning-level rules. README documents the local-run command. | file present |

### Remaining issue #4 — `fleet.py` split

Deferred. Reasoning in audit: "marginal value once race closed; high-risk parity work." The 1134-line file is internally consistent, every command works, and the lock-migration we did means concurrent invocations are now safe. Splitting becomes worthwhile when:

- A specific command needs unit tests (currently the smoke test via `fleet --help` proves CLI dispatch works)
- A specific command is being heavily modified
- The file becomes a code-review bottleneck

Until one of those triggers, the split stays in the backlog.

## ⏳ Remaining work (follow-up sessions)

### P1 — Split `fleet.py` (1103 lines) into modules

Skeleton is in place at `fleet/`. Each subcommand needs its own module + parity test against legacy `fleet.py` output:

```
fleet/
├── cli.py                      (argparse + dispatch)         ← TODO
├── commands/
│   ├── status.py               ← TODO
│   ├── sync.py                 ← TODO
│   ├── run_job.py              ← TODO
│   ├── collect.py              ← TODO
│   ├── kill.py                 ← TODO
│   ├── clean.py                ← TODO
│   └── rollup_summary.py       ← TODO
```

**Migration approach:** one command per PR. For each:
1. Copy the command's body from `fleet.py` into `fleet/commands/<name>.py`
2. Replace direct `STATE_PATH`/`LOCK_PATH` IO with `fleet.state.{load_state, save_state, mutate_state}`
3. Add a parity test: `tests/test_command_<name>_parity.py` comparing the new module's output against the legacy command on a frozen seed state.json
4. When all parity tests green, swap `fleet.py` to a thin shim that delegates to `fleet/cli.py`

### P1 — Fix `sys.path.insert` hacks in 4 files

Files still hacking sys.path:
- `clean_kenne_chunks.py`
- `launch_detached.py`
- `remote_ps.py`
- (fleet.py — fine because it's the top-level)

**Fix:** convert callers to either `python3 -m offload_orchestration.<script>` invocations (requires the dir to be a package — add `__init__.py`), or move shared code into `lib/` so a clean `from lib.remote import ps` works regardless of cwd.

### P2 — Consolidate diagnostics

`processing_report.py` should become the single `fleet diagnose` entry point reading from:
- `~/.fleet/state.json`
- `~/.fleet/alerts.jsonl`
- `~/.fleet/orchestrator/events.jsonl`
- `~/.fleet/remote_state_audit.json`

Replaces ~6 separate ad-hoc probes.

### P2 — Wire `lib/logging_helper.py` into existing scripts

Replace per-script `/tmp/<name>.log` writes with `lib.logging_helper.setup_file_logger(<name>)`. Lowest-friction wins:
- `auto_collect_watcher.sh` (shell): write to `~/.fleet/logs/$(date +%Y-%m-%d)/auto_collect_watcher.log`
- `clean_kenne_chunks.py`, `audit_external_gaps.py`, `remote_state_audit.py`: import + use the helper

### P2 — Type hints + docstring sweep

Add type hints to legacy scripts (`launch_detached.py`, `remote_ps.py`, `cluster_status.py`, `remote_process_count.py`). Run `mypy --strict utils/offload_network/` and fix.

### P2 — Doc consolidation

Three docs currently overlap:
- `/OPERATIONS.md` (top-level)
- `utils/offload_network/README.md`
- inline docstrings

Make `OPERATIONS.md` the operator-facing manual; `README.md` the developer-facing intro that points at `OPERATIONS.md`, this `REFACTOR_PLAN.md`, and the package docstrings.

## How to run the test suite

```bash
cd utils/offload_network
python3 -m pytest tests/ -v
```

Tests use an `isolated_fleet_dir` fixture that flips `$FLEET_DIR` to a tmpdir so they never touch real state. Add new tests under `tests/` following the `test_<topic>.py` naming convention.

## How to use the new `fleet/state.py` from existing code

Legacy callers that currently read state.json directly should migrate to:

```python
# Read
from fleet import load_state
state = load_state(validate=False)   # validate=True to enforce schema

# Read-modify-write under exclusive lock
from fleet import mutate_state
with mutate_state() as state:
    for j in state["jobs"]:
        if j["id"] == jid:
            j["status"] = "collected"
# auto-saves on exit; lock released after write

# Programmatic record building
from fleet import FleetJob, WorkStatus
job = FleetJob(id=42, host="kenne", status=WorkStatus.RUNNING,
               cohort="aapl_csv_uoa", wrapper_pid=12345)
with mutate_state() as state:
    state["jobs"].append(job.to_dict())
```

This blocks the auto_collect_watcher from racing manual `fleet collect` calls — the suspected cause of the rc=137/143 watcher exits seen this session.
