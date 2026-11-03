# Boldstone Dropbox cleanup: complete stable-ID census

**Checkpoint date: 14 October 2026. This continuation was read-only.**

## Result

The complete current file-ID listing of `BOLDSTONE MASTER/Products/01 Wall Sculptures` has now been traversed to the end. Fifteen pages returned 8,377 distinct file IDs; the final response had `has_more=false` and an empty cursor.

Every one of the 8,431 original media IDs has been tested for presence in that snapshot. This advances the previous 579-ID reconciliation coverage by testing the remaining 7,852 original IDs. It does not claim that those additional files have been renamed, decoded, visually inspected or individually checked for current paths and byte sizes.

| Measure | Count |
|---|---:|
| Original media IDs | 8,431 |
| Original IDs present in the root snapshot | 8,364 |
| Original IDs absent from the root snapshot | 67 |
| Post-baseline current IDs | 13 |
| Total distinct current file IDs | 8,377 |
| Census pages, pagination exhausted | 15 |
| Previously executed rename IDs still present | 203 |
| Remote file mutations in this continuation | 0 |

The two independent balances are exact:

`8,364 present originals + 67 absent originals = 8,431 original media IDs`

`8,364 present originals + 13 post-baseline IDs = 8,377 current file IDs`

The baseline distinguishes 8,425 images and six videos. The new current-file total is not described as an image or sculpture count.

## The 67 original-ID absences

| Original family | Absent original IDs | Evidence and interpretation |
|---|---:|---|
| Ammonite | 34 | Earlier verified stable-ID deletion log; current snapshot confirms absence. All 25 distinct designated keeper IDs are present. |
| Abstract Cave Paintings | 10 | Historical duplicate targets absent; unique historical/renamed filenames and folders match earlier DELETE event paths. |
| Acanthus | 2 | Historical duplicate targets absent; matching earlier DELETE event paths. |
| Cup Ring and Spiral: duplicate targets | 8 | Historical duplicate targets absent; matching earlier DELETE event paths. |
| Cup Ring and Spiral: BMP source associations | 13 | Original BMP IDs absent; 13 existing JPG IDs linked through historical names/paths and ADD-before-DELETE event sequences. |
| **Total** | **67** | **34 prior stable-ID deletion records, 20 additional event-path duplicate associations and 13 BMP/JPG associations.** |

All 67 have a recorded log or activity-history association. The evidence levels are intentionally not collapsed into one universal “verified deletion” status.

The 34 Ammonite records come from the earlier stable-ID execution log. For the other 33, the native activity-event payload supplies the path, name, operation and timestamp, but not the stable ID. The linkage to a baseline ID is reconstructed from the unique historical or renamed filename and folder. These associations are useful supporting evidence, not native event-ID proofs.

“Absent” means absent from the scanned subtree. This continuation did not search the whole Dropbox account for outside restores or relocations, and did not inspect every file's revision history.

Six targeted activity-history pages were inspected: one for Abstract Cave Paintings, one for Acanthus and four for Cup Ring and Spiral. The evidence register retains 46 relevant ADD/DELETE events. Older activity history still had more pages; full history exhaustion is not claimed.

## The 13 existing JPG replacements

All 13 post-baseline IDs are existing Cup Ring and Spiral JPGs associated with earlier BMP work on 13 October. They were not uploaded or converted in this continuation.

Their observed byte sizes total **10,590,893 bytes**. The associated original BMP records total **46,452,030 bytes**. These are evidence-register totals, not storage savings produced now.

The source-to-JPG table records original BMP ID, current JPG ID and path, observed size and modification times, and supporting historical event associations. No new binary decoding, dimension checks, image-equivalence review or source/replacement hash verification was completed. Historical conversion evidence remains in the unchanged previous package.

Of the original 671 BMP records, 642 original IDs remain present in the new snapshot. This is a baseline-BMP ID-presence count, not a newly verified population of files currently encoded as BMP.

## Historical duplicate proposal reconciled for presence

All 2,069 historical target IDs were compared with the complete snapshot, without replaying any actions.

| Current ID relationship | Target records |
|---|---:|
| Target and original designated keeper both present | 2,015 |
| Target absent; original designated keeper present | 52 |
| Target and original keeper absent; keeper linked to existing JPG | 2 |
| **Historical target records accounted for** | **2,069** |

There are 1,799 distinct original keeper IDs in the historical proposal; 1,797 are present. The other two are Cup Ring and Spiral BMP source IDs associated with present JPG replacements.

Consequently, 54 historical duplicate-target IDs are already absent. They must not be treated as new deletion work. The two absent-target/absent-keeper relationships are explicitly linked through their associated keeper replacements, rather than falsely marked as keeper-present.

The 2,015 surviving target-and-keeper pairs still require fresh same-immediate-folder, size, content-hash, sharing and revision/restriction checks before any permitted deletion. Presence is not proof that the relationship is still a byte-identical same-folder duplicate. The previously blocked seven-file deletion batch was not resubmitted.

Original historical hash, approval, status and keeper fields are preserved in the full duplicate-presence CSV; new presence fields are appended, not substituted for old evidence.

## Previously completed 203 renames

All 203 previously executed file IDs remain in the new root snapshot. Their exact filename, path and byte-size verification remains the evidence from the earlier execution pass. This continuation rechecks presence only.

No rename manifest was replayed. No file was renamed, moved, overwritten, deleted, uploaded or converted in this pass. The local workbook, reports and evidence exports are the newly created outputs.

## Download/processing status

A fresh request obtained metadata and a temporary link for a known Ammonite BMP. The actual source-byte GET failed with a ConnectionError before usable image content was retrieved. No source image was decoded or transformed, and no original BMP was removed. Temporary download credentials are not included as durable links.

## Workbook and evidence package

The new workbook is an **additive census checkpoint**, not a replacement for the earlier detailed execution records. Its 11 worksheets contain the summary, reading notes, all original IDs, all current IDs, 67 absence exceptions, 13 historical JPG associations, all 2,069 duplicate-target presence records, 64 baseline-family groups, page ledger, selected activity events, and the 203 prior-rename presence recheck.

Family counts group original IDs by baseline family membership. They do not independently certify that every present file remains at its original family path.

The evidence files contain normalized stable-ID transcriptions of the tool responses, not native raw Dropbox audit exports. Page capture times identify when each transcription was saved. The cursor listing reflects the state from the first listing request, not a sequence of independent fresh snapshots.

The accompanying ZIP includes the full, unchanged `Boldstone_Approved_Renames_Executed_203_2026-10-14.zip`, which retains the earlier workbooks, original inventory, deletion/rename records and rollback information.

### Principal sources

- `Boldstone_Wall_Sculpture_Reconciliation.xlsx`, Asset inventory: original 8,431 media records.
- Original cleanup checkpoint and historical duplicate ledger: 2,069 distinct target IDs.
- `Boldstone_Verified_Deletions_2026-10-14(1).csv`: 34 prior Ammonite deletion IDs and 25 distinct keepers.
- Prior 203-renames execution package and verified rename CSV.
- Live `Dropbox.list_folder` root file snapshot: 15 pages, final `has_more=false`.
- Targeted live `Dropbox.list_restore_events` responses, with native event/ID association limits retained.
- `evidence/new_jpg_metadata_normalized.json` and the 13-row JPG association CSV.
- `evidence/download_probe.json`.

## Remaining work

The root stable-ID census is now complete. The broader cleanup is not.

The next execution phase is current filename/path/byte-size reconciliation for present IDs, followed by controlled outstanding filename changes and fresh duplicate-content/restriction validation. Historical deletion targets that are already absent must stay out of mutation batches.

Remaining BMPs and the historical JPG associations require actual source/replacement integrity checks. Existing JPG destinations must never be overwritten merely because a BMP shares their stem. Component naming and individual/finish in-situ coverage still require examination of actual images, including group and generated scenes.

The earlier complete folder census is preserved but was not repeated during this file-only continuation. Neither folder presence nor filename wording substitutes for a visual audit.
