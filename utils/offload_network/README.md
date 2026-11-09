# offload_orchestration — fleet manager for the fleet-offload cluster

## Queued isolated jobs over HTTPS

Use the new [offload_service worker and requester](offload_service/README.md) for
the queued, encapsulated workflow. It seals configured code/data at admission,
runs each job in a restricted Docker container, and returns verified retained
results through an authenticated API. `python -m offload_service serve --config
worker-home/worker.json --tunnel` starts both the worker and Cloudflare connector.
See that guide for installation, templates, tokens, resource limits and recovery.
For uploaded candidate packages, bundled/registered/generated inputs, autonomous
dependent jobs, portable testing checkpoints and planned verified result return,
use the opt-in [research workflow layer](research_workflows/README.md).
For one isolated testing job and independent results per candidate, use
[self-sufficient candidate batches](research_workflows/BATCHES.md).
For multi-model jobs, arbitrary comparators and a fully managed local offload
exercise, see [run batches](research_workflows/RUN_BATCHES.md).
The older SSH/fleet tooling documented below remains available for trusted host
commands; it is not the new service's sandbox or queue.

> Transferred into `marketmaker_v2/utils/offload_network`. For a safe local
> end-to-end exercise, run `python3 utils/offload_network/run_simulation.py`.
> It creates Windows/Linux/macOS-labelled worker directories, uses the real v2
> seal and runner, and performs no SSH or live-host operations. Live hosts are
> disabled examples in `hosts.json` until explicitly configured.

Single source of truth for: provisioning new Windows compute hosts, syncing
code to them, launching pipelines on the cluster, tracking running jobs,
collecting results to the external drive, and a dormant WireGuard fallback
in case Tailscale ever goes away.

**For day-to-day workflow ("where do I run X?", "how do I check capacity?",
"how do I clean up?")** see [**OPERATIONS.md**](../../OPERATIONS.md) (at the repo root).
This README focuses on *what's in this directory*; `OPERATIONS.md` at the repo root focuses on
*how to use it*.

## Directory layout

```
utils/offload_network/
├── README.md                          this file (what's where)
│  (note: OPERATIONS.md lives at the REPO ROOT, not here)
├── hosts.json                         host inventory (cores, paths, libemd, rsync_path)
│
├── fleet.py                           the CLI: status / run / jobs / kill / clean / rollup-summary / hdd-status / ops / network-discover
├── cluster_status.py                  per-host probe — fleet.py status delegates to it
├── remote_process_count.py            quick per-host ps counter helper
├── remote_ps.py                       run any PowerShell on a remote Windows host SAFELY
│
├── offload_service/                   queued HTTP API, Docker worker, client and tunnel launcher
├── v2/                                sealed-bundle format and legacy trusted SSH transport
│   └── (cli.py, seal.py, transport.py, launcher.py, runner.py, submit.py, result.py, fleet_adapter.py, drivers/, tests/)
│
├── archive/                           historical artifacts
│   └── v1_2026-06-07.tar.gz           the old rsync+ssh+nohup transport (~91 KB, ~1300 LOC) — archived 2026-06-07
│
├── host_bootstrap/                    fresh-host Windows setup (PS scripts, wg_fallback/, etc.)
│
├── fleet/                             shared state machine (state.py, paths.py, locked state.json IO)
│
└── lib/
    ├── __init__.py
    ├── remote.py                      safe SSH-to-Windows helpers (encode_ps, mkdir_remote, …)
    └── logging_helper.py              centralised logger (states/scopes/logs/<YYYY-MM-DD>/<script>.log)
```

State that's not in the repo (deliberate — secrets / runtime):

```
states/scopes/
├── state.json                         fleet.py job registry
├── state.lock                         state write lock
├── job_<id>_wrapper.sh                Mac-side keep-alive wrapper for each job
├── logs/run_<id>_<host>_<cohort>.log  per-job streaming output
├── logs/...
├── op_journal/                        resumable operation logs
├── remote_state_audit.json            remote probe cache
├── v2_bundles/                        bundled job manifests + batch state files
├── orchestrator/                      orchestrator persistence
└── wg/                                WireGuard keys + per-host wg0.conf (gitignored)
    ├── keys/{mac,kenne,scan-xeon,cdec,scan-new}.{priv,pub}
    ├── conf/{mac,kenne,scan-xeon,cdec,scan-new}.conf
    ├── inventory.json
    └── etc_hosts.fragment
```

## Quick reference

```bash
# probe every host (cores, CPU%, RAM, disk, libemd, running pipelines)
utils/offload_network/fleet.py status

# push code (not data) to a host or all of them
utils/offload_network/fleet.py sync kenne
utils/offload_network/fleet.py sync all

# launch a pipeline — auto-picks idle libemd host
utils/offload_network/fleet.py run --cohort bonds_dxy_nk

# launch on a specific host with custom args
utils/offload_network/fleet.py run --cohort ig_friendly --host kenne \
    --pipeline-args "--window-weeks 8 --windows-per-instrument 8 --batches 4 --workers-per-batch 8 --seed 42"

# what's running where?
utils/offload_network/fleet.py jobs

# stop a job (SIGTERM to the keep-alive wrapper)
utils/offload_network/fleet.py kill 7

# rsync remote results -> external drive (resume-safe, auto-verified per-file)
utils/offload_network/fleet.py collect 7                   # copy + verify; safe to re-run
utils/offload_network/fleet.py collect 7 --delete-remote   # same + rm remote AFTER verify
utils/offload_network/fleet.py collect 7 --verify-only     # skip rsync, just diff manifests

# what's actually on the remote? (streaming PowerShell, never hangs)
utils/offload_network/fleet.py manifest 7                  # raw `size<TAB>relpath`
utils/offload_network/fleet.py manifest 7 --diff           # only print missing/short files

# preview-then-delete stale results dirs
utils/offload_network/fleet.py clean kenne --age=7d        # dry-run
utils/offload_network/fleet.py clean kenne --age=7d --yes  # actually delete
```

See `OPERATIONS.md` (repo root) §4.5 + §7 for the full "collect was interrupted" / "remote PowerShell hung" playbooks.

## Adding a brand-new Windows host — canonical flow

1. **Get in via AnyDesk** (or RDP if you have it on the LAN).
2. **On the Mac, run the helper** — it generates the per-host SSH key and
   prints the PowerShell snippet to paste:
   ```bash
   utils/offload_network/setup_windows_host_macside.sh newhost
   ```
3. **Paste the printed snippet into elevated PowerShell on the remote.**
   That runs `setup_windows_host.ps1` which does, idempotently:
   - OpenSSH Server + `administrators_authorized_keys` + DefaultShell=PowerShell
   - Power: no sleep / no hibernate on AC
   - RDP + NLA + firewall rule (backup GUI access)
   - Wake-on-LAN
   - Python 3.12 + the three SSH-PATH lessons (see below)
   - h5py / numpy / scipy / pefile
   - MSYS2 + SuiteSparse + OpenBLAS + **rsync** + VC++ Redist
   - Tailscale (if you passed an auth key) — with 503-backend retry loop
   - WireGuard package (dormant) + optional config stage
   - Repo dir at `~/Downloads/fleet-offload/`
   - `Restart-Service sshd` so new SSH sessions inherit the updated env
4. **Press Enter on the Mac helper** when the remote finishes. The helper
   then `ssh -O exit`s the host (kills ControlMaster cache) and smoke-tests
   `ssh newhost python -V`.
5. **Add the host to `hosts.json`** (see schema below), then
   `fleet.py sync newhost` to push the code tree.
6. `fleet.py status` should now show the new host with `libemd ✓`.

## `hosts.json` schema

Required fields for any new Windows host:

```json
{
    "newhost": {
      "type": "ssh",
      "platform": "windows",                         // windows, linux, or macos
    "ssh_alias": "newhost",                          // matches ~/.ssh/config Host line
    "user": "kenne",                                 // remote username
    "repo": "C:/Users/kenne/Downloads/fleet-offload", // canonical repo root
    "cores": 32,                                     // logical cores (for fleet auto-pick)
    "has_libemd": true,                              // can it run cache generation?
    "has_iqfeed": false,                             // can it download from IQFeed?
    "msys64_bin": "C:/msys64/ucrt64/bin",            // ucrt64 bin (or C:/Users/.../msys64/ucrt64/bin)
    "rsync_path": "C:/msys64/usr/bin/rsync.exe",     // CRITICAL for fleet sync (see below)
    "results_root": "c_emd/results",                 // relative to repo
    "notes": "free-text"
  }
}
```

Optional:
- `"status": "pending-tailscale"` — fleet.py skips this host in sync/status
- `"external_drive": "/Volumes/..."` — only meaningful for the local `mac` entry

## Remote platform support

Every SSH host declares `platform` as `windows`, `linux`, or `macos`.
Omitting it preserves the original behaviour and means `windows`.

- Windows uses encoded PowerShell, `bootstrap.cmd`, Windows `tar.exe`, and
  MSYS path conversion for rsync.
- Linux and macOS use `sh -s` over SSH, `bootstrap.sh`, POSIX `tar`, `nohup`,
  `test`, `wc`, `mv`, and `rm`. Remote values are passed as quoted positional
  arguments rather than interpolated into scripts.
- Both paths use the same sealed manifest, blob hashes, runner, status JSON,
  result archive, retries, deadline handling, and cleanup safety guard.

The remote POSIX account needs OpenSSH, a POSIX shell, `tar`, `rsync`, and
Python 3. Set `python_executable` in the host entry if `python3` is not the
correct executable. The SSH host key and authentication should be configured
before submission; the utility does not weaken host-key checking.

## The three Python-on-SSH lessons (baked into setup_windows_host.ps1)

OpenSSH on Windows is finicky. Why this code is the way it is:

1. **Windows Store stubs hijack `python.exe`** — `C:\Users\<u>\AppData\Local\Microsoft\WindowsApps\python.exe` exists by default and silently swallows the command. The setup script `Remove-Item`s both `python.exe` and `python3.exe` from there.
2. **OpenSSH ignores user-scope PATH** — your interactive PowerShell sees a fresh PATH from User+Machine, but SSH sessions only see Machine PATH. The setup writes Python's path to `HKLM:\System\CurrentControlSet\Control\Session Manager\Environment` PATH.
3. **sshd caches the env at service start, and the Mac caches its SSH connection** — so a PATH change *after* sshd started doesn't show up in existing or pooled SSH sessions. The setup ends with `Restart-Service sshd -Force`, and the Mac-side helper does `ssh -O exit <alias>` plus removes any control-master sockets.

If `fleet.py status` shows a host as "reachable but no python", check those three in order.

## The three fleet-sync-rsync lessons (baked into fleet.py)

When syncing code to Windows over SSH:

1. **Windows OpenSSH has no rsync** — `pacman -S rsync` via MSYS2 supplies one. `setup_windows_host.ps1` phase 5 installs it. fleet.py passes `--rsync-path` per host.
2. **MSYS2 rsync interprets `C:` as a relative path component from `$HOME`** — `C:/Users/X/...` becomes `/c/Users/X/C:/Users/X/...`. fleet.py rewrites destinations from `C:/...` to `/c/...` before invoking rsync.
3. **`pathlib.Path` strips trailing slashes** — if `SYNC_PATHS` had `c_emd/python/` (trailing slash means "copy contents"), pathlib loses the slash and rsync copies *the directory itself* into the destination. Silent failure that looks like success and creates `c_emd/python/python/`. fleet.py re-appends the slash when the SYNC_PATHS entry had one.

## `remote_ps.py` — quick safe remote PowerShell from your shell

For one-off PowerShell calls (debugging, manual checks, ps liveness, log
tails) without re-discovering the `$_`-eaten-by-zsh bug each time:

```bash
# the $_ bug solved
utils/offload_network/remote_ps.py kenne '
  Get-Process | Where-Object { $_.WorkingSet -gt 200MB } |
      Select-Object Id, ProcessName, @{N="MB";E={[int]($_.WorkingSet/1MB)}} |
      Format-Table -AutoSize
'

# ps liveness for a list of PIDs
utils/offload_network/remote_ps.py kenne '
  $pids = @(1234,5678,9012)
  Get-Process -Id $pids -ErrorAction SilentlyContinue |
      Select-Object Id,ProcessName,CPU,StartTime | Format-Table -AutoSize
'

# stderr-dump pattern
utils/offload_network/remote_ps.py kenne '
  Get-ChildItem C:/path -Filter *.stderr.log | ForEach-Object {
      Write-Output ("--- " + $_.Name); Get-Content $_.FullName -Tail 20
  }
'

# script via file
utils/offload_network/remote_ps.py kenne -f local_script.ps1

# script via stdin
cat local_script.ps1 | utils/offload_network/remote_ps.py kenne
```

How it defeats the bug:
- Encodes the entire script as UTF-16-LE base64
- Ships it as `powershell -EncodedCommand <b64>`
- Mac shell, ssh, Windows command interpreter, and PowerShell parser never
  see your `$_`, em-dashes, smart quotes, or nested quotes raw

Also prepends `$ProgressPreference = 'SilentlyContinue'` so PowerShell doesn't
dump CLIXML progress noise into stdout (disable with `silence_progress=False`
in `lib/remote.ps()`).

## `lib/remote.py` — safe SSH-to-Windows helpers

Reusable building blocks for anything that needs to talk to a Windows host
without re-discovering the same gotchas:

```python
from lib import remote

remote.encode_ps(script)             # UTF-16-LE base64 wrap → -EncodedCommand
remote.ps(host, script)              # run a PS script on host, returns CompletedProcess
remote.mkdir_remote(host, *paths)    # idempotent, Windows-safe; replaces the cdec malformed-mkdir
remote.file_exists_remote(host, p)   # Test-Path wrapper
remote.scp_to(host, local, remote)   # auto-creates remote parent dir first
remote.invalidate_controlmaster(h)   # ssh -O exit + remove the socket file
remote.host_python_works(host)       # → (bool, "OK|<path>|<version>" or diagnostic)
```

Why this exists: every direct `subprocess.run(["ssh", host, "cmd /c mkdir foo"])`
in our code was a quoting bug waiting to happen. `encode_ps` defeats the
em-dash + smart-quote + nested-quotes problem by base64-wrapping the script
before it ever touches a shell.

## Auto-host-pick

`fleet run` without `--host` chooses:

1. Filter to hosts with libemd available and not in `pending-tailscale` state
2. Score each by `(-running_jobs_from_registry, cores)`
3. Pick the highest score (least-loaded; ties broken by core count)

This means today the order tends to be **kenne (128c)** → **cdec (32c)** →
**scan-xeon (32c)**. Override anything with `--host`.

If you want the auto-pick to factor in **live CPU%** (not just registry job
count), it's a 10-line change in `_pick_host` — call `cluster_status` first
and use its `cpu_pct`.

## Coexistence with the older `/tmp/run_*.sh` wrappers

Jobs launched before fleet existed (`/tmp/run_bonds_pipeline.sh`,
`/tmp/run_tier1_pipeline.sh`, …) continue to run unchanged. They're not in
the registry, so `fleet jobs` doesn't see them. New jobs go through
`fleet run`; their outputs land at the same external location.

## WireGuard fallback

Everything is **pre-staged but dormant**. See `wg_fallback/README.md` for the
short activation runbook (one Fritz!Box rule + 4 SSH commands, ~5 min).

## Limitations / non-goals

- No fault-tolerant restart. If a wrapper dies, the watcher will eventually
  rsync whatever the pipeline already wrote — you have to relaunch.
- No multi-host job (one cohort per host per job). Multi-host parallel cohorts
  would need an outer wrapper.
- No GPU scheduling (not needed for CPU-bound EMD compute).
- No web UI — JSON state + CLI is intentional for a one-operator cluster.

If the cluster grows past ~8 hosts or fault-tolerance becomes important,
switch to HashiCorp Nomad (Tailscale-friendly) or Ray/Dask for Python-native
distributed compute. Today's setup is the right size for what we're doing.
