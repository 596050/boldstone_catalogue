# Offload failure audit and Toshiba acquisition status

11 September 2026. This is a diagnostic audit, not a runtime repair or a new
model-performance experiment. No production code, research history, downloaded
payload, credentials, worker configuration or startup service was modified.

## Outcome

- Existing suite: **481 passed, 13 skipped** ([BASELINE.xml](BASELINE.xml)). This
  includes 422 offload/transport tests and 59 economic/IQFeed collector tests.
- Additional failure-focused scenarios: **five offload defects reproduced**.
  A sixth scenario reproduces the IQFeed collector's exit on transient SQLite
  contention ([FINAL_FAULTS.xml](FINAL_FAULTS.xml)). These tests deliberately assert
  the desired recovery behavior and currently fail; they are not passing checks.
- Existing genuine research evidence: **PASS**, 26 retained objects verified,
  six local-origin records and eleven original candidate files unchanged, and all
  five produced native result files matched their previous exact SHA-256 hashes.
  The blocked branch still has no fabricated native output
  ([GENUINE_RECHECK.json](GENUINE_RECHECK.json)). No models were fitted or run again.
- Economic releases: fresh full verifier **PASS** on 97 retained HTTP responses
  and 91 derived artifacts; all 9,246 captured advertised vintage selections
  present ([DOWNLOADS_VERIFIED.json](DOWNLOADS_VERIFIED.json)).
- IQFeed: **not complete and currently paused**, after a live database lock timeout
  during this audit. The incident and the inspector's role are detailed below.

## Confirmed offload defects

| Priority | Failure | Reproduction and impact | Runtime location |
| --- | --- | --- | --- |
| High | Interrupted upload initialization cannot resume | Hard-exit between empty `.part` creation and metadata publication; reopening the store and retrying `begin` raises `FileExistsError`. Same-object retries remain stuck. | `research_workflows/objects.py:148` |
| High | Compressed retention is charged expanded storage | A 3 MiB compressible capsule yields less than 100 KiB total returned archives but a 2 MiB source store rejects collection. Expanded bytes are included in the physical capacity reservation even in archive-only mode. The separate expanded-content verification ceiling should remain intact. | `research_workflows/client.py:211` |
| High | Temporary collection space shortage becomes a permanent attention hold | Simulated free space above the project's 1 MiB reserve but below the collector's 16 MiB reserve raises `ValueError`; source sync classifies it as non-transient. Restoring space does not resume collection without manual `retry-transfer`. | `research_workflows/client.py:215`, `project_queue.py:358` |
| Medium | Disk-full during download finalization discards the local completed transfer | After the archive is moved into a temporary extraction directory, failure writing `RECEIVED.json` causes temporary-directory cleanup to delete that local archive. The worker still retains the verified original, but retry requires a full download again. | `research_workflows/client.py:159` |
| Medium | Successful upload commit leaves duplicate bytes after a crash | Hard-exit after object promotion but before upload cleanup; repeated `commit` sees committed state and returns without removing its redundant `.part` and metadata. Evidence is intact, but abandoned copies consume the worker budget. | `research_workflows/objects.py:183`, `objects.py:209` |

These tests use real loopback HTTP, actual synthetic subprocess execution and
`os._exit` where specified. They do not simulate electrical power loss or prove
native Windows/Linux host behavior. No Docker or external worker was launched in
this audit. Existing opt-in Docker/native-research tests remain skipped.

The central `research_workflows/project.json` still has an empty `workers` map.
No persistent source sync or worker startup service is running. Durable queue
logic is not the same as an installed, supervised multi-machine deployment.

Recommended repair order: recover upload initialization, correct compressed
physical reservations and transient space classification, then make download
finalization and committed-upload cleanup restartable. Preserve immutable
identities, negative results, all original archives and ACK-after-publication.

## IQFeed live incident and current state

At the first check, PID 87916 was active, its lock file was open, and its log was
advancing. The status showed 5,790 unfinished requests; later exports showed
5,703 unfinished requests. Both samples reported 253,419,144 parsed rows retained
in completed jobs; no-data probes advanced the queue without adding price rows.

At 23:55 UTC on 10 September, the diagnostic inspector opened the 74 MB live
SQLite queue in `mode=ro` and tried to read the job table. The read was much slower
than expected. Sampling showed the inspector blocked in SQLite `pread`; it held
a reader transaction. Read-only SQLite access can still block a writer's commit
in this queue's DELETE-journal mode. The inspector appears to have triggered the
collector's 30-second lock timeout. This was not an intentional live fault test.

The collector reported `PAUSED_ERROR: OperationalError: database is locked` at
23:57:48 UTC, saved its manifest, and then exited. Its final traceback points to
`archive.py:799`, committing a RUNNING transition before the next request.
The inspector was stopped with SIGTERM after SIGINT did not promptly release the
read. Neither the downloader process nor its locks were forcibly stopped/deleted.
No restart was performed; permission to resume the unchanged queue was requested.

The retained [reader sample](reader-sample.txt) and
[collector sample](downloader-sample.txt) establish the filesystem-read stalls.
The revised `inspect_downloads.py` uses exported manifests/status for queue
inspection and never opens the live IQFeed database. The full IQFeed payload
reverification was not run, to avoid further heavy reads on the busy drive.

An isolated fake-feed test now reproduces collector termination when a temporary
reader outlasts its SQLite busy timeout (scaled to 20 ms versus a 150 ms reader).
The collector handles its cooperative file lock separately but does not retry
SQLite `OperationalError`. Its error path also exports from the still-open
transaction, so the one saved RUNNING marker is not evidence of an active job
after process exit. Pending plus RUNNING remains the useful unfinished total.

Final exported request counts, cutoff **9 September 2026**:

| State | Requests |
| --- | ---: |
| Complete | 5,210 |
| Complete with recorded anomalies | 83 |
| No data | 16,563 |
| Not authorized | 99 |
| Split parent, retained evidence | 89 |
| Pending | 5,702 |
| Last saved RUNNING transition; process has exited | 1 |
| Total | 27,747 |

All 5,703 unfinished requests are minute requests for dated futures contracts.
The 253.4 million parsed rows are not unique independent market observations:
continuous, back-adjusted and individual-contract histories overlap. Response
completion does not establish inception/calendar completeness. The 83 anomalous
responses retain their flags; they are not silently repaired.

There is actual gold-contract, oil, Treasury-futures, dollar, rates, market-breadth,
MOVE and VIX-futures data. VIX cash (`VIX.XO`), related Cboe indices/yield indices,
continuous gold (`QGC#`, `QGC#C`), spot-gold minute data and some dated contracts
have explicit entitlement denials. No-data includes deliberately enumerated
unlisted/unsupported expiry candidates, not necessarily missing real trades.

The Toshiba mount identity and writable flag matched the central registry. About
61 GiB was free, versus the collector's 20 GiB reserve. The collector code still
matched its sealed archive binding. No shadow local data directory was created.

## Economic-release archive

The separate HTTP acquisition queue is finished with recorded limitations:
81 complete, seven blocked HTTP requests, one failed supplementary document, and
two split-parent failures whose smaller child vintage requests succeeded.

All 14 current-vintage series are present: headline/core CPI, PPI and PCE variants,
payrolls, claims, breakeven inflation and financial conditions. There are 19,653
current-history rows. All 9,246 advertised series-specific ALFRED vintage dates
were acknowledged across 31 successful chunks. The 1,020,380 interval rows across
those chunks include repeats and must not be called unique observations.

Fresh verification at **00:02:28 UTC, 11 September** passed source/derived hashes,
gzip/ZIP integrity, source-to-derived bytes, schemas, row counts and exact vintage
selections. Its receipt was written here, not into the source archive.

The captured CPI/PPI/PCE numeric series stop at the **July 2026 observation period**.
Capture date alone does not imply later releases are present. Seven direct BLS
calendar/archive pages returned HTTP 403; CME's supplementary methodology page
failed with an HTTP/2 transport error. Consensus forecasts and FedWatch odds are
not downloaded. This is a sealed snapshot, not an automatic daily refresh or a
complete intraday point-in-time economic-event dataset.

## Reproduce and cleanup

From the repository root, with a Python environment providing pytest:

```sh
PYTHONPATH=.:utils/offload_network python -m pytest -o addopts='' -q \
  utils/offload_network/research_workflows/validation/failure_audit_20260911/test_fault_audit.py
```

The expected current result is six reproduced recovery failures, not six passes.
`FAULTS.xml` records the first five offload reproductions. `FAULTS_CONFIRMED.xml`
also preserves an initial missing-host-field error in the new fake-feed fixture;
that harness error was corrected before `FINAL_FAULTS.xml` reproduced the actual
SQLite contention failure. No failing runtime was patched or failures hidden.

Owned synthetic worker stores and temporary test files are disposable; the source
tests, XML receipts, readback evidence, status snapshots and diagnostic samples
remain here. `CLEANUP.json` records cleanup once all owned processes have exited.
