# Hetzner plan for the organized Toshiba folders

Prepared **15 September 2026**. Use **one BX21 5 TB Storage Box**, initially in Falkenstein (`fsn1`), containing **one encrypted Restic repository** at `market-data-v1`. Preserve both existing folder trees and their manifests. No further source reorganization or deduplication-by-deletion is needed.

Hetzner's public price feed, fetched at **18:51 UTC**, lists **EUR 10.90/month before applicable VAT**, or EUR 0.0175/hour, for BX21 in Germany or Finland. The plan includes 5 TB, unlimited traffic and 20 provider snapshot slots. Actual account pricing is checked with the existing script's `plans` command before ordering. [Product specification](https://www.hetzner.com/storage/storage-box/bx21/), [public price feed](https://website-price-api.hetzner.com/api/v1/products/ROBOT_1334), [saved price receipt](PRICE_RECEIPT.json).

## Capacity and source selection

| Selected source | Files used for sizing | Logical size |
| --- | ---: | ---: |
| `/Volumes/Toshiba 2TB/raw_price_data/` | 131,543 | 1,158.500 GB |
| `/Volumes/Toshiba 2TB/other_data/` | 828,634 | 378.182 GB |
| `/Volumes/Toshiba 2TB/DATA_LAYOUT.md` | 1 | 1,169 bytes |
| **Selected total** | **960,178** | **1,536.682 GB / 1.537 TB** |

This uses the independently verified `run_09_organized_complete_20260915` census, completed at 15:14 UTC, plus the five separately recorded publication files. The source roots and volume identity were checked again at 18:51 UTC; a new recursive census was not run. The full census also includes nine volume/system files outside these selected paths. [Exact sizes, source identities and command arguments](PLAN.json), [current source checks](SOURCE_PREFLIGHT.json).

The selected collection occupies about **30.7% of a nominal 5 TB allocation**, leaving **3.46 TB before repository overhead, retained versions and future growth**. A 1 TB Box is too small without relying on unmeasured compression. Budget the complete file lengths: Restic's compression and content deduplication may reduce storage, but no saving is assumed. The 374.041 GB of `price_views/` stays included; those representations are not additional independent price observations. Existing copies, partial acquisitions, failed-attempt evidence, models and retained project material remain included.

The separate small catalogue backup described below adds some metadata beyond this selected total. Begin reviewing capacity at 70% usage and plan expansion before 80%; this is a proposed operating threshold, not an automatic deletion rule.

## What would be stored remotely

The Box's actual SSH location would be **`/home/market-data-v1/`**, containing Restic's encrypted repository files. The folder tree below is the **view inside a backup snapshot and after restoration**, not a set of plaintext CSV folders visible through SFTP:

```text
Volumes/Toshiba 2TB/
├── raw_price_data/
│   ├── iqfeed_archive/
│   ├── iqfeed_macro_market/
│   ├── ibkr/ and ibkr_adr_home_fx_bbo_v1/
│   ├── ig/ and yahoo/
│   ├── recovered_project_sources/
│   ├── embedded_source_archives/
│   └── price_views/
├── other_data/
│   ├── macroeconomics/economic_releases/
│   ├── non_price_provider_archive/
│   ├── research/, derived/, models/ and evidence/
│   ├── retained_marketmaker/
│   ├── retained_marketmaker_v2/
│   └── migration/
└── DATA_LAYOUT.md
```

The illustration shows the main directories; uploads select their entire trees. Restic preserves separate filenames and snapshot versions while sharing identical content chunks. Restore either a complete tree, one provider, one dataset or individual files. [Restic backup behavior](https://restic.readthedocs.io/en/stable/040_backup.html), [restoration](https://restic.readthedocs.io/en/stable/050_restore.html).

A plain SFTP/rsync copy could instead expose `raw_price_data/` and `other_data/` directly on the Box. That would be a different storage method from the existing encrypted backup script. The recommended first deployment uses Restic for preservation and selective recovery; a browsable working subset can be designed separately if needed.

The Toshiba registry remains the authority for its local files. The remote catalogue should identify each retained object by **repository ID, completed snapshot ID, path within that snapshot and original file hash**. Do not replace filesystem paths in historical evidence with SFTP URLs or change historical source clocks. On a replacement machine or disk, restore and verify files first, then explicitly register that storage identity.

## Initial upload and recovery

The existing [storage utility](../storage_box.py) already implements setup, encrypted upload, completed-snapshot tagging, integrity checks and selective recovery. Its source matches the version covered by the retained 14-test local validation. The current setup preview and root/identity checks passed; no authenticated remote test has run.

After a Box/profile is configured and a small live upload/restore trial succeeds, the initial upload preview is:

```bash
python3 utils/external_storage/hetzner/storage_box.py upload \
  '/Volumes/Toshiba 2TB/raw_price_data' \
  '/Volumes/Toshiba 2TB/other_data' \
  '/Volumes/Toshiba 2TB/DATA_LAYOUT.md' \
  --group organized-data --require-mount '/Volumes/Toshiba 2TB' --dry-run
```

The transfer uses SFTP over SSH port 23 and reads the selected sources directly; it does not build another 1.5 TB staging archive. Remove `--dry-run` for transfer only after the source boundary and credentials are ready. Completed immutable files can be archived immediately. For a consistent baseline, checkpoint active databases and coordinate writers to any images or mutable files. A readable live file alone is not proof of an application-consistent snapshot. Unreadable/incomplete backups stay marked pending.

For the initial 1.537 TB, network-only transfer arithmetic gives approximately **7.1 days at 20 Mbps**, **34.1 hours at 100 Mbps**, or **6.8 hours at 500 Mbps**. These are estimates, not measured throughput: file count, local reads, encryption, retries and source contention can add time, while compression may reduce transmitted bytes. Initial full verification also reads stored data back over the network.

```bash
python3 utils/external_storage/hetzner/storage_box.py verify --read-data
python3 utils/external_storage/hetzner/storage_box.py snapshots --group organized-data
python3 utils/external_storage/hetzner/storage_box.py ls SNAPSHOT_ID
python3 utils/external_storage/hetzner/storage_box.py recover SNAPSHOT_ID \
  --subtree '/Volumes/Toshiba 2TB/raw_price_data/iqfeed_archive/minute' \
  --target '/Volumes/Recovery Disk/iqfeed-minute-restored'
```

Replace `SNAPSHOT_ID` with the completed ID recorded by the successful upload. The target must be new/empty; recovery verifies restored contents. A full restore without `--subtree` recreates `TARGET/Volumes/Toshiba 2TB/...`. Reconcile the initial snapshot's file list against its source inventory, retain the repository ID and encryption password independently, and keep the Toshiba copy through remote verification and restore validation.

## Regular updates and using the data

Use separate snapshot groups in the **same repository**:

| Group | Contents | Proposed cadence |
| --- | --- | --- |
| `organized-data` | Complete selected roots | Initial baseline, then coordinated periodic baselines |
| `price-batches` | Newly completed IQFeed/broker price acquisitions and their receipts | After each completed session; shorter closed tick batches if needed |
| `macro-batches` | Original economic responses, revisions and supplied vintage metadata | Daily and around relevant releases |
| `catalogue` | Current manifest, path registry, batch-to-snapshot index and storage recovery instructions | After each verified batch publication |

The wrapper uses `backup --force`, so backing up both complete roots rereads about 1.54 TB even when little needs uploading. Frequent jobs should select **only finalized acquisition batches**. The current collectors need incremental cursor/revision handling and an explicit batch catalogue before this can become a reliable scheduled service; adding a timer to a fixed-cutoff collector would not do that.

Each batch should keep its original response, source parameters, source/release/vintage clocks where available, local capture times, sizes, SHA-256 values and collector identity. Close and hash the files, upload the batch, verify that batch through selective recovery, and publish its completed snapshot binding in the catalogue. Advance the archived watermark only afterward. Run whole-repository stored-data checks initially and periodically, rather than rereading the entire repository after every small batch.

**A `price-batches` or `macro-batches` snapshot contains only its selected batch.** `recover latest --group price-batches` cannot reconstruct the complete archive. Full recovery needs the retained baseline plus every subsequently committed batch named in the catalogue. Keep every unique batch snapshot until another verified retained baseline includes its data. No automatic pruning is proposed initially. Hetzner's provider snapshots provide another rollback mechanism within the same Box, consume the same quota and are not an independent backup. [Snapshot storage accounting](https://docs.hetzner.com/storage/storage-box/snapshots/).

Collection and research run on the existing host or a separate compute server. A Storage Box cannot run uploaded collector scripts. Restore the needed datasets to a worker's local SSD for backtests; keep live SQLite databases, active disk images and memory-mapped calculations on a local filesystem. [Hetzner SSH service](https://docs.hetzner.com/storage/storage-box/access/access-ssh-rsync-borg/).

The Toshiba currently has **167 MiB free**, so new acquisitions need a separate staging/cache disk or host. The initial archive upload itself does not require duplicate payload space on Toshiba. This plan does not assume that the local originals can be deleted immediately after upload.

## Current deployment state

**Prepared and checked locally:** measured folder plan, live public pricing, existing tool compatibility, setup preview, mounted-volume identity and selected root checks. No Storage Box profile was found on this machine. No Box was ordered, remote connection attempted, data uploaded, schedule installed or source files changed. The remaining deployment steps are listed explicitly in [PLAN.json](PLAN.json).
