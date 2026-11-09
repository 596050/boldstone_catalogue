# Toshiba raw-source transfer to Hetzner — 16 September 2026

The user-supplied project API token authenticated successfully. Storage Box
**652565**, named **market-data**, is active in **Falkenstein (fsn1)**. It is the
planned **BX21**: 5,497,558,138,880 bytes of capacity. The account bills in USD:
**$13/month net, $15.60 including 20% VAT**, with no setup fee. Account evidence is
in [ACCOUNT_PREFLIGHT.json](ACCOUNT_PREFLIGHT.json).

The encrypted Restic repository is
`sftp://u670499@u670499.your-storagebox.de:23/market-data-v1`, with immutable ID
`e14c2837a2d7b298aa9d151bfa8c1e4f68bbb74eca622edb2aa0ed5984e327fb`.
The dedicated SSH key, Restic password and connection profile are outside Git at
`~/.config/marketmaker-storagebox/market-data/`. The API token was read from the
existing `.env` assignment without being displayed, copied into these records,
or passed in command-line arguments. Uploads and recovery use the dedicated SSH
key and do not need the API token.

The live trial passed for eight actual price/macro files (400,343 bytes),
including an all-pack integrity check and matching restored SHA-256 hashes.
A second test restored the full preservation-record batch through a separate
local recovery profile: **10 files / 296,945,610 bytes**, all matching source
hashes and the previously recorded preservation-archive hash. See
[PRESERVATION_RECOVERY.json](PRESERVATION_RECOVERY.json). The large temporary Mac
restore copy was removed after validation to retain working space. The separate
profile is a portability test, not an independent hardware backup of credentials.
All **16 storage tests** passed after the live connection and lock-contention
fixes. [VALIDATION_CURRENT.json](VALIDATION_CURRENT.json) records the latest
observed running process, code identities and the limits of completed checks.

## Live state and scope

[STATE.json](STATE.json) records the current phase, process ID, batch, progress,
completed batches and any error. A successful trial is recorded separately in
[LIVE_TRIAL.json](LIVE_TRIAL.json). The full transfer is complete only when all
45 planned batches are reconciled and [FULL_READBACK.json](FULL_READBACK.json)
reports a successful read of every remote pack. Trial success does not establish
bulk-transfer completion.

The selected roots are:

```text
/Volumes/Toshiba 2TB/raw_price_data
/Volumes/Toshiba 2TB/other_data/macroeconomics
/Volumes/Toshiba 2TB/other_data/non_price_provider_archive
/Volumes/Toshiba 2TB/other_data/non_price_legacy
/Volumes/Toshiba 2TB/other_data/raw
/Volumes/Toshiba 2TB/other_data/legacy_ibkr_files
/Volumes/Toshiba 2TB/other_data/migration
/Volumes/Toshiba 2TB/DATA_LAYOUT.md
```

The 15 September verified census contains **675,233 files / 1,205,041,839,154
bytes** beneath these roots. Later preservation-publication files are additional;
each batch gets a fresh inventory. [PLAN.json](PLAN.json) partitions the selected
roots without overlaps, includes hidden files and empty directories, and keeps
all price representations. The prior manifest is hash-bound, and every prior
file must still be present when its batch starts. Metadata changes are recorded.

The active worker disk image and other retained research/runtime trees are
outside this raw-source transfer. The earlier 1.537 TB whole-drive preservation
plan also included those trees; it is a broader scope.

## Execution and recovery

From `/Users/tprice/Developer/marketmaker_v2`:

```sh
python3 utils/external_storage/hetzner/toshiba_transfer_20260916_v1/transfer_job.py status
```

If an interrupted job is no longer running, resume its existing plan:

```sh
python3 utils/external_storage/hetzner/toshiba_transfer_20260916_v1/transfer_job.py run
```

The job holds a process lock. Completed batches retain exact snapshot IDs and
are checked against the remote repository before reuse. An unfinished batch is
retried with Restic deduplication. Source files are reread; no staging copy is
created on Toshiba. Progress logs, before/after inventories, remote listings and
batch receipts stay under this directory. A fixed recovery catalogue is itself
uploaded before the final all-pack readback.

The launch in [LAUNCH.json](LAUNCH.json) runs under `caffeinate` with system and
disk sleep prevention. Keep this Mac running and Toshiba connected. The first
attempt stopped when the concurrent recovery test held a shared repository lock
needed by completion tagging. Its receipts, launch state and exact utility code
are retained under `attempt_history/`. Completion tagging now waits up to five
minutes for that lock without force-unlocking it. A real contention regression
test passed, and attempt 2 resumed the verified batches rather than recopying them.

Attempt 2 completed 12 batches (492 files / 307,730,465 bytes) before its source
inventory encountered an unsigned 64-bit file ID that did not fit SQLite's
signed integer column. This was an empty `cycle.lock` file whose synthesized
exFAT ID also changes between reads. Attempt 3 stores ordinary IDs as exact text;
empty files are compared by path, type, zero length and mtime, with observed IDs
still retained in the manifests. Four regression tests and fresh before/after
inventories of the affected 171-file folder passed. The failed run and exact
code are preserved under `attempt_history/attempt_02_*`. Completed snapshots
are now revalidated through one current remote listing when resuming.

For a captured folder, take its snapshot ID and source path from
`batches/<group>/COMPLETE.json` or the final
[REMOTE_SOURCE_CATALOG.json](REMOTE_SOURCE_CATALOG.json):

```sh
python3 utils/external_storage/hetzner/storage_box.py recover SNAPSHOT_ID \
  --target "/Volumes/Recovery Disk/recovered-folder" \
  --subtree "/Volumes/Toshiba 2TB/PATH_FROM_BATCH_RECEIPT"
```

Recovery verifies the restored contents. Use a new/empty target with enough
space. Each batch is a separate snapshot: **`latest` alone does not select the
entire archive**. The main [storage utility guide](../README.md) covers snapshot
listing, individual files, restore resumption and replacement-computer setup.

## Preservation boundaries

The job checks the registered Toshiba volume UUID and identity marker. It stops
on unreadable entries, open write handles in a selected batch, missing prior
files, remote path/type/size differences, or source metadata changes during the
batch. Before/after size, mtime and stable inode agreement is a live metadata check;
empty-file synthesized IDs are retained but excluded from comparison as above.
This is not an atomic filesystem snapshot or proof against a writer that restores
the same metadata. Restic's full readback verifies stored encrypted content.

**No Toshiba originals are deleted by this job.** Final source removal remains
pending complete remote verification, recovery validation, an independently
retained usable copy of recovery credentials, and a final source/reference
review. Current filesystem references still point to the retained Toshiba
files; SFTP repository URLs are not substituted for paths expected by readers.
No collector schedule or new IQFeed/macro acquisition is started by this job.

## Initial connection fixes

The new hostname was initially negative-cached by the local router. A temporary
process-scoped SSH route used the published DNS address while retaining the
original host name and strict verification against
[Hetzner's published Ed25519 fingerprint](https://docs.hetzner.com/storage/storage-box/general/).
It expires after one hour and is bypassed once normal DNS resolves. System DNS
and hosts settings were not changed. Evidence: [DNS_FALLBACK.json](DNS_FALLBACK.json).

Live access also exposed a quoting bug: Restic parses each `-o` argument as CSV,
so the nested quotes in SSH's `UserKnownHostsFile` option needed CSV encoding.
The utility now encodes that argument correctly. The new test exercises the
installed Restic parser and reproduces the previous failure; the earlier local
SFTP test had substituted its own server command. The original utility is
retained as [storage_box_before_live_fix.py](storage_box_before_live_fix.py).
