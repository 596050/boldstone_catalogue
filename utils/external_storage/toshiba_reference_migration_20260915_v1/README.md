# Toshiba folder deletion and reference migration — 15 September 2026

`/Volumes/Toshiba 2TB/marketmaker_v2` was removed at **14:42:33 UTC**, after its contents had been relocated and its empty state checked. The operation was `rmdir`. The external `marketmaker` folder was already removed by the preceding organization. Both repositories under `/Users/tprice/Developer/` remain intact.

The independent preservation comparison found **all 960,167 original project files**, with **zero missing files** and **zero changes to logical size, modification time, or nonempty-file inode identity**. This verifies the relocation at file-metadata level; it is not a new full-payload checksum verification. See [the deletion receipt](EXTERNAL_V2_REMOVAL.json) and [the preservation result](FINAL_DATA_PRESERVATION.json).

## Current data locations

| Purpose | Toshiba directory | Files in the verified census | Logical bytes |
| --- | --- | ---: | ---: |
| Price sources, associated metadata and retained price representations | `raw_price_data/` | 131,543 | 1,158,499,920,862 |
| Economic releases, non-price providers, derived data, models, research and retained project material | `other_data/` | 828,630 | 377,991,159,733 |

These two directories do not overlap. The price directory includes **374,040,669,029 bytes of retained price views**; its total is not a count of independent raw observations. The remaining nine files in the full census are volume-root/system files. The census includes the earlier migration publication and the new storage identity marker.

The main IQFeed archive is `raw_price_data/iqfeed_archive/`. Market-price series previously under `macroeconomics/` are now in `raw_price_data/iqfeed_macro_market/`; economic releases are in `other_data/macroeconomics/economic_releases/`. FRED, EIA, SEC, CFTC and other non-price provider archives are in `other_data/non_price_provider_archive/`. Retained external-v2 material is in `other_data/retained_marketmaker_v2/`.

## Files and manifests updated

Both repository-root `data_paths.json` files now agree, including the storage identity, current canonical target, **2,517 logical location mappings**, **2,604 verified relocation prefixes**, three parent-container lookup aliases and the completed deletion state. Volume UUID: `087E2AA1-5151-322D-8C09-9852ECD979B5`. [Registry validation](FINAL_REGISTRY_VALIDATION.json) records the final registry checksum and every registered dataset's current location.

The source changes cover **2,629 ordinary Python source files**, the shared data/manifest readers, the legacy registry generator and the census/query pipeline. Full logical paths now resolve through the registry when their contents span the price and other-data directories. The resolver handles historical absolute paths and relative manifest references, checks the mounted storage identity, rejects recreated old-path shadows and does not substitute a missing source. Retired-input checks still apply after relocation. The registry generator preserves prior dataset keys and storage mappings.

All **981 dataset registrations and their prior states** were retained. Every one of the **288 entries marked `local_directory`** is present. Of 693 previously marked `missing_external`, 29 directories exist and 664 are absent from the census. These retained status disagreements and absent legacy registrations are not files lost during this reorganization. The named `testing_minute_cache` source also remains unavailable; no placeholder was created.

The published [current data manifest](../../../research/utility/toshiba_data_manifest_20260913_v1/README.md) selects **`run_09_organized_complete_20260915`**: **960,182 files**, **23,264 directories**, and **1,536,499,590,095 logical bytes**, observed from **14:44:13 to 15:14:23 UTC**. Eleven fresh source catalogues reconcile to **27,749 macro acquisition records** and **10,766 payload references present, zero missing**. Original compressed source catalogues keep their bytes; generated catalogue views use current locations. The original scan's eleven transient directory timeouts were resolved by recorded supplemental reads before publication.

## Historical references and recovery

The [combined reference verification](FINAL_REFERENCE_RECONCILIATION.json) accounts for **154,066 distinct source files** and checks **8,706,198 current-location reference occurrences**. This includes both local repositories, `/Users/tprice/marketmaker-research-data`, compressed local metadata and **all 126,263 on-drive candidates**. Four malformed historical JSON records were retained and indexed as text. Eleven AppleDouble sidecars were identified and hashed; five small sealed metadata TAR files had 35 regular members indexed without extraction. There are no unaccounted candidate-read errors.

Historical receipts, research capsules, original data catalogues and previous censuses retain their original paths, hashes, timestamps and evidence identities. Their indexed current-location counterparts bind back to original document hashes and JSON pointers or text offsets. Current authority files supersede their earlier observed versions in the combined counts. An indexed reference can describe a historical missing input or a prospective output; it does not certify that every referenced object exists.

From a repository root, translate an individual old path or create a separate current-location view:

```bash
python3 utils/external_storage/relocated_references.py resolve \
  '/Volumes/Toshiba 2TB/marketmaker/iqfeed_archive/minute' --require-exists

python3 utils/external_storage/relocated_references.py view \
  '/path/to/a/retained/manifest.json' --output /tmp/current-manifest-view.json

python3 research/utility/toshiba_data_manifest_20260913_v1/query.py \
  --prefix macroeconomics/ --summary
```

The last command searches **both** destinations of the former macroeconomics directory: 11,265 files and 13,030,821,970 bytes. Use manifest queries for a whole old directory that was split; a parent lookup alias alone does not represent the union of its extracted children. All 2,604 relocation prefixes passed round-trip checks.

The on-drive handoff is `other_data/migration/toshiba_reference_migration_20260915_v1/`. Its compressed bundle contains the current manifest, reference indexes, path registry and helpers, implementation snapshots, earlier source backups and verification receipts. `PUBLICATION.json` alongside the bundle records its full read-back checksum and files added after the census. `DATA_LAYOUT.md` at the volume root points to this handoff. The preceding organization bundle remains unchanged.

## Verification and retained limits

The source-reader test run passed 232 tests and exposed one incorrect test boundary; the corrected five-test group then passed, accounting for all **233 distinct checks**. The final five-test rerun also passed. All updated Python files parse, all 2,629 ordinary source hashes match their final edit receipts, and the before/after source ZIP members were read back and hashed. [Implementation inventory](FINAL_IMPLEMENTATION_INVENTORY.json), test logs and the original failed test output are retained. Two historical runtime source copies encountered during the broad edit were restored byte-for-byte and recorded separately; frozen model source files were not edited. The original core resolver backup is explicitly labelled as reconstructed from inverse edits rather than a directly captured snapshot.

The live orchestrator's dynamic path lookup resolves to the current `other_data` location. The worker sparsebundle path is updated, but its pre-existing mount failure remains unresolved; image contents were preserved and no forced filesystem repair was attempted. This work does not claim a new research result or worker readiness.

The census is live and non-atomic. `.Spotlight-V100` and `.Trashes` remain inaccessible. General archive/database interiors, disk-image filesystems, row-level/date completeness and full payload integrity are outside this verification. The 2,762 sampled payload hashes from the preceding organization remain a separate, narrower checksum check. Publication files written after 15:14:23 UTC are listed in the publication receipt rather than retroactively inserted into the sealed census. The recovery bundle is metadata and code, not a second copy of the price payloads or a deployed Hetzner backup.
