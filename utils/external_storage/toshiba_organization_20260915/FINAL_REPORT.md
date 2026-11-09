# Toshiba data organization completed

Verified preservation of **960,167 files / 1,536,385,004,218 logical bytes**.

`/Volumes/Toshiba 2TB/marketmaker` was removed using empty-directory removal only. `/Volumes/Toshiba 2TB/marketmaker_v2` remains in place; it is empty and ready for removal.

**No payload files were deleted.** Local repositories under `/Users/tprice/Developer` remain in place.

## Data folders

| Folder | Files | Logical GB |
| --- | ---: | ---: |
| `raw_price_data/iqfeed_archive` | 68,745 | 725.613052 |
| `raw_price_data/price_views` | 19,744 | 374.040669 |
| `other_data/retained_marketmaker_v2` | 87,469 | 182.488889 |
| `other_data/research` | 139,933 | 140.153418 |
| `other_data/non_price_provider_archive` | 540,550 | 41.827587 |
| `raw_price_data/recovered_project_sources` | 28,760 | 39.036509 |
| `raw_price_data/iqfeed_macro_market` | 10,776 | 13.011758 |
| `other_data/retained_marketmaker` | 57,531 | 8.806915 |
| `raw_price_data/ibkr_adr_home_fx_bbo_v1` | 14 | 4.870163 |
| `other_data/legacy_ibkr_files` | 2,473 | 4.581674 |
| `raw_price_data/ibkr` | 3,176 | 1.464950 |
| `raw_price_data/ig` | 47 | 0.390131 |
| `raw_price_data/embedded_source_archives` | 2 | 0.071445 |
| `other_data/macroeconomics` | 489 | 0.019064 |
| `other_data/non_price_legacy` | 171 | 0.006037 |
| `other_data/raw` | 1 | 0.001479 |
| `raw_price_data/yahoo` | 278 | 0.001243 |
| `other_data/forward` | 4 | 0.000012 |
| `other_data/.DS_Store` | 1 | 0.000006 |
| `other_data/logs` | 2 | 0.000001 |
| `other_data/migration` | 1 | 0.000001 |

Price views and retained project caches may duplicate observations in the raw archives. Folder totals are non-overlapping physical files, not counts of unique observations.

## Preservation evidence

All 2,604 planned moves have before/after receipts. Final independent traversal found 0 missing files and 0 missing directories; 0 files changed after their move inventories. 2,762 selected content checksums matched.

The original live census differs from the immediate move inventories by 0 added files and 4 changed files; 0 original files were missing. See `reconciliation/` for the exact differences.

Every file path, length, mtime and non-empty file inode; directory namespace; selected full or head/tail SHA256 samples. Same-volume renames preserve payload extents. Not a full payload hash or independent backup.

Archives and disk images remain intact. Their interiors were not all independently enumerated. OS-managed `.Spotlight-V100` and `.Trashes` were inaccessible and untouched; system folders and manuals remain at the drive root.

## Finding original paths

`data_paths.json` contains the current physical locations and the exact original-to-current `path_relocations` map. `PLANNED_FILES.jsonl.gz` and the per-move receipts retain file-level paths. Historical receipt bytes were not rewritten.

Use `utils.data_paths.resolve_relocated_path(old_path, require_exists=True)` to resolve an original Toshiba path. Legacy code that opens literal old paths needs this explicit mapping before it runs.

## Concurrent replay incident

One active price replay failed when its source directory moved between file reads. Its failure log and partial local outputs were preserved; no source payload was deleted. The mover was corrected to retain a fence for the full lifetime of an observed reader process. The original replay remains incomplete, with 87 surviving output files separately hashed in place. A replacement replay added explicit relocation handling and checkpoints. Storage maintenance retained its verified checkpoint at session 800. Replacement replay maintenance status: `RESUMED_PROGRESS_VERIFIED`. See `LIVE_READER_INCIDENT.json`, `INTERRUPTED_REPLAY_OUTPUTS.json` and `CHECKPOINT_MAINTENANCE.json`; no research result is claimed by this storage operation.

## Runtime checks and remaining limitations

All 981 registered dataset directories were checked against their pre-move availability; no new missing paths were found. The 29 pre-existing registry status mismatches remain recorded, and the unused `testing_minute_cache` location was absent both before and after. Frozen specification bytes and their literal price-directory declarations were verified. Standalone imports require the legacy `ib_gateway` package, which is unavailable in the direct repository import environment; this check does not establish complete runtime readiness. See `LIVE_PATH_VERIFICATION.json`.

The worker-image supervisor was restored with its backing-image path translated. The archived image currently refuses a normal remount with `Resource temporarily unavailable`; its files remain preserved. No forced detach, filesystem repair, replacement image or lock-file deletion was used to bypass that failure. See `WORKER_GUARD_STATUS_AFTER.json` and `WORKER_IMAGE_ATTACH_VERBOSE.log`.

## Capacity and backup

Drive free space before publishing this evidence bundle: 476,577,792 bytes. Organization retains caches and duplicates, so it does not materially reclaim capacity. No Hetzner upload or independently restored backup was performed by this operation.

The on-drive migration folder contains this report, the final registry, and a compressed copy of the local organization records. The evidence bundle is metadata and scripts, not a backup of the price payloads.
