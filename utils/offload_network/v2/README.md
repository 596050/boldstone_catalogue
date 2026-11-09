# v2 sealed-bundle offload orchestration

Phase 1 + Phase 4 of the v2 plan. Every job ships as a single sealed
archive (code + data + manifest + bootstrap). Results pulled back
automatically as a single archive when the run exits.

## Files

```
v2/
├── manifest.py    SealedManifest, SealedBlob, ResultSpec, HostSpec dataclasses
├── seal.py        build_seal / verify_seal / extract_seal
├── transport.py   push_seal / pull_result / remote_run (rsync + ssh helpers)
├── runner.py      runs INSIDE the extracted seal on the remote
├── launcher.py    extract + spawn detached bootstrap from submitter
├── result.py      pull + unpack result archive
├── submit.py      submit_one / submit_many — full lifecycle
├── cli.py         `python -m v2 build|submit|verify <args>`
├── example_manifest.json
└── tests/test_seal.py    7 unit tests (round-trip + tamper detection + local end-to-end)
```

## Lifecycle

```
SealedManifest (declared)
   │
   ▼ build_seal()
sealed archive  ← single tar.gz (or tar.zst if `zstandard` installed)
   │              with hashed blobs + bootstrap.cmd + runner.py
   ▼ push_seal()
remote: <host.remote_workdir>/<job_id>.tar.gz
   │
   ▼ launcher.launch() — extract + spawn bootstrap.cmd detached
remote: <host.remote_workdir>/<job_id>/
            ├── manifest.json
            ├── runner.py
            ├── bootstrap.cmd
            ├── blobs/...     ← extracted inputs
            ├── outputs/...   ← entrypoint writes here
            ├── status.json   ← runner writes phase progress
            ├── run.log
            └── <job_id>.result.tar.gz   ← packed by runner at exit
   │
   ▼ poll status.json until phase == exited
   ▼ pull_result.fetch_and_unpack() — single rsync of result.tar.gz
local: <manifest.result.local_dir>/...     ← extracted result files
```

## Integrity

- Every blob is sha256'd at build time; sha goes into the canonical
  manifest that is embedded in the archive.
- The remote runner re-verifies blob shas after extraction (catches
  partial extracts / disk corruption).
- The seal file itself is sha256'd; submitters can verify integrity
  with `python -m v2 verify <seal.tar.gz>` or `verify_seal(...)`.
- Tampering one byte of the archive → verify_seal raises `SealError`.

## Quick start

```bash
# Build a seal locally
python -m v2 build  example_manifest.json --out ./build

# Submit (build + push + run + pull + cleanup)
python -m v2 submit example_manifest.json --out ./build

# Verify a seal's contents
python -m v2 verify ./build/job-2026-06-06T123456Z-abc123.tar.gz
```

Programmatic:

```python
from v2.manifest import SealedManifest
from v2.submit import submit_one

manifest = SealedManifest.from_path("example_manifest.json")
out = submit_one(manifest, bundle_out_dir="./build")
print(out["timings"], out["result"]["extracted_to"])
```

## Concurrency

`submit_many(manifests, max_workers=8, max_parallel_per_host=2)` runs
multiple jobs in parallel with a per-host throttle. Each job is its
own submit_one and is fully independent — a failure does not cancel
others.

## Compression choices

- **Seal push** (`push_seal`): rsync with `-a` only. The archive is
  already compressed; `-z` would only burn CPU.
- **Result pull** (`pull_result`): rsync with `-az`. Results are tiny
  and mostly text — compression pays off.
- The sealed archive itself defaults to `tar.gz` (works with stock
  Windows `tar`). For better ratio install the `zstandard` package
  on the submitter and set `archive_format: "tar.zst"` in the
  manifest — but the remote `tar` must also support zstd (Windows
  bsdtar usually does on recent builds).

## Status JSON

The runner writes `status.json` at each lifecycle step:

```
{phase: starting}      ← manifest loaded
{phase: running, run_started_at, argv}
{phase: exited, exit_code, elapsed_s, result_archive, result_summary}
{phase: failed, stage, error}
```

`submit_one` polls this and treats `exited` / `failed` /
`exited_pack_failed` as terminal.

New runner and generic/random-window driver reports use `time.monotonic()` for
`elapsed_s` and include `elapsed_clock: "time.monotonic"`. Cache-copy reports use
the same clock for `copy_elapsed_s`, identified by `copy_elapsed_clock`.
Wall-clock corrections therefore do not change these elapsed intervals.
UTC event timestamps remain observations of the wall clock; they are not rebuilt
from elapsed time or reordered when that clock moves backwards.

`submit_one` also uses monotonic time for local phase durations and its existing
deadline boundary. Its `timings.elapsed_clock` identifies those local durations;
`started_at` remains a wall-clock epoch timestamp. `remote_elapsed_clock` is copied
from the remote receipt independently and remains `None` for an unlabelled older
receipt. `total_s` keeps its previous boundary before remote cleanup, with cleanup
reported separately. A polling deadline still preserves remote work and evidence.
Old sealed runners, receipts and cached durations retain their original clock
semantics; rebind and remeasure references before claiming runtime improvement.

## Not yet built (future phases)

- **Phase 2** PyInstaller frozen runtime → ship `runner.exe` so the
  remote needs zero Python setup.
- **Phase 3** content-addressed dedup → ship 5 KB instead of 8 GB
  when a cache is already on the remote.
- **Phase 5** evidence record → audit trail joining manifest+result
  into a sealed evidence JSON.

## Tests

```bash
python3 -m unittest v2.tests.test_seal -v
```

7 tests cover: manifest validation, JSON round-trip, seal build +
verify + extract, tamper detection (1-byte flip → sha mismatch), and
a fully local end-to-end run where `runner.py` executes a script and
packs the result archive (no SSH required).
