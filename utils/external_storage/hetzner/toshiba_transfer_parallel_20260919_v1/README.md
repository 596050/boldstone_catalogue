# Parallel large-batch transfer — 19 September 2026

Second job against the **same** Restic repository
`sftp://u670499@u670499.your-storagebox.de:23/market-data-v1`
(id `e14c2837a2d7b298aa9d151bfa8c1e4f68bbb74eca622edb2aa0ed5984e327fb`),
carrying the 8 large network-bound batches: **125,100 files / 1,153,755,145,636 bytes (1.154 TB)**.

[PLAN.json](PLAN.json) is derived from `toshiba_transfer_20260916_v1/PLAN.json`; batch
definitions, paths, prior counts, census binding and volume UUID are copied unchanged.
`derived_from` records the source plan hash and exactly which groups were excluded.
Job A retains all 45 planned batches and its 36 completed receipts are untouched.

## Why this job exists

Job A stopped on `toshiba-fred-7887b862` — 535,143 files in a *single* exFAT directory.
Measured on the idle drive:

| Operation | Result |
|---|---|
| `listdir` of 534,810 entries | 43 s (one sequential pass) |
| open+read 100 random files **by name** | **4.267 s/file** (0.2 files/s) |

exFAT has no directory index, so every open-by-name linearly scans a ~68 MB directory
table. `iostat` showed ~4,600 IOPS x 4 KB = 18 MB/s of metadata churn delivering ~5 KB/s
of payload. At 4.267 s/file that batch costs **26+ days of lookup overhead alone**,
independent of network or Restic. Staging it elsewhere does not help: any copy must
perform the same lookups.

## Concurrency is not possible on this volume

Running this job while Job A worked `fred` was attempted and **failed**: it sat 15 minutes
in uninterruptible kernel I/O wait (`UN`), 0.15 s CPU, 0-byte inventory, never enumerating
a file. Lowering Job A's I/O priority with `taskpolicy -b` changed nothing, ruling out
queue starvation — the block is a **volume-wide exFAT metadata lock** held continuously by
`fred`'s scan. Evidence: the same directory listing took **33 s** with `fred` running and
**0.25 s** with it stopped, a 132x difference.

So the drive is held by one job at a time. Job A was stopped cleanly (SIGINT to Restic,
exit 130, `STOPPED_INCOMPLETE`, no snapshot marked complete) and its stale repository lock
removed with `restic unlock`, which removes only locks it proves stale.

## Measured throughput

| Path | Rate |
|---|---|
| Source read, sequential, uncontended | 45-64 MB/s |
| Source read, sequential, contended | 25.3 MB/s |
| Link, single stream | 6.94 MB/s (55.6 Mbps) |
| Link, 4 parallel streams | 6.92 MB/s (no gain) |
| Link, 8 parallel streams | 10.23 MB/s (81.9 Mbps) |
| Job A, `sftp.connections=2` | 1.45 MB/s |
| **This job, `sftp.connections=8`** | **4.46 MB/s (3.1x)** |

Neither disk nor link was the limit at 1.45 MB/s. 1.154 TB at 4.46 MB/s is **~3 days**.

## Differences from the validated code

Exactly two one-line changes, both deliberate:

```text
transfer_job.py:42   sb = module('storage_box', HERE / 'storage_box.py')   # was HERE.parent
storage_box.py:259   "-o", "sftp.connections=8"                            # was 2
```

The first gives this job its own utility copy so the **shared
`../storage_box.py` is byte-identical** — its sha256 still matches the
`storage_utility_sha256` recorded in Job A's `LAUNCH.json`. Identities are in
[LAUNCH.json](LAUNCH.json).

Profile `market-data-parallel` duplicates the `market-data` credentials and points at the
same repository. It exists **only** to hold its own `operation.lock`: the job takes
`flock(LOCK_EX|LOCK_NB)` on the profile directory, so two jobs sharing one profile abort
immediately. Restic backups themselves take *shared* repository locks, so concurrent
writers are safe — the exFAT lock, not Restic, is what prevents it here.

## Operating

```sh
python3 utils/external_storage/hetzner/toshiba_transfer_parallel_20260919_v1/transfer_job.py status
```

Resume after an interruption with `run`; completed batches are revalidated against one
current remote listing and are not recopied.

**No Toshiba originals are deleted by this job** and no source metadata is modified.

## After this job

Resume Job A for `fred`:

```sh
python3 utils/external_storage/hetzner/toshiba_transfer_20260916_v1/transfer_job.py run
```

Its ~1.19 GB of already-uploaded `fred` data persists in the repository and replays
through Restic deduplication in minutes; only the ~26-day lookup cost remains. Run
`restic unlock` first if an interrupted run left a stale lock. The two jobs' snapshots
together cover all 45 planned batches; a final catalogue and all-pack readback should be
taken across both once `fred` completes.
