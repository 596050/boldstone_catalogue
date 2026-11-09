# Project-authoritative offload return and recovery

Implementation: fleet-offload-orchestration 0.6.0. Date: 11 September 2026.

## Implemented

- Central source policy in `research_workflows/project.json`, persistent local
  SQLite outbox metadata, frozen workflow/worker/origin bindings, bounded retries,
  source and bulk disk budgets, and operator-visible integrity holds.
- `enqueue`, `sync [--watch]`, `queue`, `retry-transfer`, `publish` and `origin` CLI
  commands. Planner `--project-config` seals the central default attempt budget;
  explicit per-job budgets remain authoritative.
- Append-only per-job records under originating candidates, including negative,
  failed and missing-data results. Native result trees and historical paths/hashes
  are not rewritten. Source-owned origins are never supplied by worker code.
- Shared object-level deduplication, archive-only source retention, complete
  streamed file/hash verification, and bounded local on-demand read views.
- Prior execution attempts are included in new workflow deliveries; interrupted
  retries are bounded and require worker-confirmed termination. A disconnected
  machine is not presumed dead and work is never automatically reassigned.
- File/directory flushes before publication, resumable transfer and publication,
  and ACK after central verification plus every local-origin record.

## Validation evidence

- `FINAL_SUITE.xml`: 422 passed, 13 skipped. Offload tests, legacy v2 tests, private
  SSH forwarding tests and authenticated Cloudflare gateway unit tests. Skips are
  opt-in Docker/native-research-image or unavailable upstream-fixture cases.
- `RELEASE_CHECKS.xml`: 49 passed, 3 skipped after lock/compaction scope guards.
- `COMPRESSED_FINAL.xml`: 21 focused recovery/retention tests passed. These include
  real loopback HTTP and subprocess work, abrupt requester `os._exit`, lost admission
  and ACK replies, source queue reopen, worker-store restart, interruption-only retry,
  partial-download HTTP range recovery, publication disk-full, missing drive,
  identity conflicts, forbidden origins, archive corruption, bounded read cache,
  previous attempt retention and interrupted expanded-cache removal.
- `ALIAS_AND_RECOVERY.xml`: focused rerun after handling an OS path alias outside
  the project while continuing to reject symlinks inside the research tree.
- `INSTALLED_SMOKE.json`: installed-wheel CLI exercise outside the checkout;
  package source/assets byte comparison, central planning, enqueue, independent
  worker execution, sync/collection, origin readback, queue status and worker init.
  Its synthetic temporary stores, worker and server are cleaned automatically.
- `GENUINE_RETURN.json`: all six existing genuine Treasury model-development
  testing jobs filed into their candidate directory. Exact native result bytes
  read back for all five produced results; no fake result for the blocked branch.
  Original candidate files and newly published records remained unchanged during
  compaction. No new model execution or performance reinterpretation occurred.

An initial broad-suite invocation lacked the two legacy standalone test import
paths; `REGRESSION.xml` retains that collection error. The corrected environment
passed (`REGRESSION_FINAL.xml`, then later full-suite receipts). The installed
smoke initially caught macOS `/var` versus `/private/var` origin resolution; the
resolver was corrected and given an alias regression check, without weakening
the no-symlinks-inside-research boundary.

## Space measurements and retained evidence

The genuine collection's shared repository measured 1,183,318,016 allocated bytes
before lossless compaction and 77,070,336 afterward (about 93.5% less). Logical
retained bytes were 6,338,280 after compaction. Allocated bytes include Toshiba's
filesystem allocation overhead; these are measurements of this repository, not
a forecast of compression ratios for other data. Every exact archive remains.
Only verified redundant expansions were removed, recoverable from those archives.
Five requested native result read views plus their metadata used 45,056 allocated
source-local bytes in this exercise. No global/source dataset cleanup was run.

The original complete archive and source/Toshiba research data remain unchanged.
The source candidate now contains `OFFLOAD_RETURN.md` and per-job records. The
older manual report/frozen-model retention remains valid; this turn did not refit
or rerun the actual Treasury candidate to produce a new market-performance result.

## Deployment boundary

Recovery scenarios were locally exercised with explicitly trusted synthetic
subprocess jobs. The genuine evidence comes from the earlier isolated Linux Docker
run on this Mac and was reverified here; it is not a new remote-host execution test.
Windows/Linux native host tests and arbitrary machine/disk power-loss survival
have not been demonstrated in this turn. CI includes the added recovery suite.

The central project config contains no active endpoints or credentials. No worker,
source daemon, public tunnel, startup service or automatic failover was installed
or left running. Configure authorized worker endpoints, then supervise source
`sync --watch` and worker `serve` with their persistent stores to resume unattended
after reboot. Worker resource admission remains independently configured.

This is durable resumable processing, not replicated high availability. Backups
are required for permanent disk loss. Remote evidence is not automatically expired;
capacity guards stop admission/transfers rather than silently discarding results.

`CLEANUP.json` records removal of the dedicated 435 MiB temporary validation
directory after all owned processes stopped. Synthetic stores and intermediate
builds were discarded; the tested release wheel, test receipts, compact research
records and genuine evidence remain retained. The installed smoke separately
confirmed automatic cleanup of its temporary worker/source stores.
