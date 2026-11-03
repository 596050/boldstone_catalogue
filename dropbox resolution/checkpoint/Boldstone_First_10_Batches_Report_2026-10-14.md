# Boldstone cleanup: first ten batch checkpoint

**14 October 2026. Run FIRST10-20261014T143738Z.**

## Result

The exact first ten entries in the small-batch register were processed: S01, S02, H01, J001, J002, J003, I00, M001, M002 and M003.

**Six review/control tasks are closed; four batches remain partial. No Dropbox file was renamed, moved, deleted, overwritten, converted or uploaded.** “Closed” includes a completed failed retrieval test and a completed review that retained all deletion holds. It does not mean those underlying capabilities or deletions succeeded.

The other 340 allocated review/control batches retain their prior status and scope.

## Batch results

| Order | Batch | Scope | Result |
|---:|---|---|---|
| 1 | S01 | Checkpoint controls | Complete. Source checksums, protected IDs, exclusions and historical evidence boundaries saved. |
| 2 | S02 | One BMP and one JPG | Test complete, retrieval failed. Both native GETs failed at DNS resolution before image bytes were obtained. |
| 3 | H01 | Seven held duplicate candidates | Hold review complete. All seven targets and six keepers remain present; the earlier safety block remains unresolved. |
| 4 | J001 | Five existing JPG/source associations | Partial. Current metadata and historical QA reconciled; fresh decode and dimensions blocked. |
| 5 | J002 | Five existing JPG/source associations | Partial. Current metadata and historical QA reconciled; fresh decode and dimensions blocked. |
| 6 | J003 | Three existing JPG/source associations | Partial. Current metadata and historical QA reconciled; fresh decode and dimensions blocked. |
| 7 | I00 | Historical identity-register consolidation | Partial. Nine known folder cases consolidated; the complete earlier case-level register was not recovered. |
| 8 | M001 | Abstract Cave Paintings: 13 IDs | Complete. All current metadata recorded; all byte sizes match; 13 filename no-ops. |
| 9 | M002 | Acanthus: 81 IDs | Complete. All current metadata recorded; all byte sizes match; 81 filename no-ops. |
| 10 | M003 | Ammonite: first 100 allocated IDs | Complete as metadata review. All sizes match; 99 filename no-ops and one held stale-prefix exception. |

## S01: replay prevention and source protection

The saved controls include 377 original checksum entries, 1,813 distinct protected keeper/replacement IDs, 54 already-absent historical duplicate targets, 203 completed rename IDs, 67 original absence dispositions and seven previously blocked targets.

These are checkpoint-based controls. They are not a claim that all 1,813 protected IDs were freshly read in this run. Historical approvals, names, hashes and evidence levels remain intact. Newly retrieved historical inputs are separately identified by the package checksum manifest.

## M001-M003: current metadata verification

The three fixed scopes contain **194 distinct IDs**. Every ID was resolved through a fresh detailed Dropbox metadata response, recording exact current name, display/namespace path, immediate parent folder, bytes, revision, client/server modification times, reported MIME type and observation timestamp.

| Check | Result |
|---|---:|
| Scoped IDs found | 194 / 194 |
| Byte sizes matching baseline | 194 / 194 |
| Current revisions recorded | 194 / 194 |
| Current filenames matching their historical proposals | 194 / 194 |
| Filenames requiring no further change in these scopes | 193 |
| Held naming exceptions | 1 |
| New rename jobs | 0 |

One Ammonite asset, `id:cnqzTNngPVsAAAAAAAyjYQ`, now sits in `Ammonite/Ammonite Small White` but still starts with `ammonite__`. Its name matches the earlier proposal for its old parent, not the more specific current parent. It is already an H01 held duplicate target. No rename proposal was made executable and no new change was applied.

The stable collision suffix on another Ammonite file, `__asset-2d0094f383`, was retained rather than simplified. Matching byte sizes do not establish binary equivalence, and this review did not establish sculpture identity or in-situ coverage.

Across all first-ten workstreams, **208 distinct IDs have detailed current metadata records**. This count includes the 194 scoped metadata IDs, H01 and S02 overlaps. The 13 JPG listing checks overlap some of those records and must not be added as a disjoint population.

## S02 and J001-J003: binary limitation

Native metadata and temporary download-link metadata were returned for the assigned BMP and JPG. One actual GET per file failed with `ConnectionError` caused by a DNS `NameResolutionError`. No source image bytes were available, and no file was decoded. Signed download credentials are omitted from the saved evidence.

A fresh, complete Cup Ring and Spiral listing returned 30 files with `has_more=false`. The 13 existing replacement JPGs match their expected IDs, filenames, paths and byte sizes. Their listed bytes total **10,590,893**.

The earlier verification worksheet was recovered as extracted file text. It provides historical source/JPG mappings, dimensions, hashes and recorded PSNR values for all 13 JPGs, dated 13 October 2026. Those values were carried forward as **historical evidence only**. The one current server JPG hash obtained in S02 matches the historical value; the other 12 server hashes were not recollected.

**J001-J003 remain partial:** no fresh JPEG decoding, dimension check or source/replacement visual-equivalence test was completed. No JPG was reconverted or overwritten, and no BMP original was removed. Source absences and historical conversion events remain historical facts, not operations performed now.

## H01: seven deletion holds retained

All seven targets and six distinct designated keepers were freshly resolved at their recorded paths. Their pair sizes and same-immediate-folder relationship match.

The earlier connector safety-block result remains unresolved. Empty permission objects are not affirmative deletion authority. Fresh content hashes, complete revision-history/restriction checks and sharing checks were not certified in this run. Older hash/sharing fields remain explicitly dated prior evidence.

**No deletion request was resubmitted.** Closing the hold-review task does not make the seven targets eligible for execution.

## I00: incomplete source recovery, no invented identity decisions

The consolidation contains nine unique known folder-label cases, linked to stable folder IDs and their allocated identity batches. The earlier folder-naming audit was recovered and its 419 folder records were preserved. Of these, 307 contain historical identity-risk topics.

Those 307 rows are **risk context, not 307 unresolved sculpture identities**. One historically resolved four-component arrangement was preserved separately, with no new visual verification or inferred linkage to unknown case IDs.

The complete older case-level queue was not recovered. The known nine wording flags must not replace the historical queue previously reported with other counts. A source-completeness exception records this gap. Consequently **I00 is partial**, and no sculpture/component identity was resolved in this run.

## Evidence and workbook

The revised workbook retains all six original planning worksheets and all 350 original scopes. The Batch Register has ten updated statuses and appended attempt fields. Partial batches have no completion timestamp. New sheets include Run Summary, First 10 Results, Metadata Review, Existing JPG QA, Held Candidates, Known Identity Queue, Identity Source Gaps, Historical Identity Evidence, Binary Test and Run Sources and Controls.

The CSV/JSON evidence includes each checkpoint, 194 scoped metadata reviews, 208 normalized detailed metadata records, seven held-pair reviews, 13 JPG association checks, the identity subset/source gap, preserved control sets and the append-only run ledger.

Live metadata logs are normalized transcriptions of connector responses, not native raw Dropbox exports. Observation timestamps identify recording time. Source modified timestamps and prior verification dates are retained separately.

Principal sources:
- The unchanged `Boldstone_Small_Batch_Plan_2026-10-14.zip` and its exact per-batch CSV manifests.
- Original census, keeper, absence and rename registers preserved in the plan and checkpoint controls.
- Fresh `Dropbox.get_file_metadata` results for the 208 detailed IDs.
- Fresh `Dropbox.list_folder` for Cup Ring and Spiral; 30 files, pagination exhausted.
- `Boldstone_Continuation_Verified_2026-10-13.xlsx`, JPG Rechecks and historical resolved composition, recovered through Files text.
- `Boldstone_Image_Naming_and_Duplicate_Audit.xlsx`, Image rename plan and Folder naming, recovered from the authorized Library file.
- Historical RETRY-006 safety-block evidence, preserved without resubmission.

## Resume point

**The next untouched allocated batch is M004**, the next fixed 100 Ammonite IDs. Do not replay M001-M003 as rename jobs.

Resume J001-J003 only after actual authorized source/JPG bytes can be retrieved and decoded. Resume I00 from the complete historical case-level register. Retain H01 holds unless legitimately resolved, and perform all applicable current checks before any future authorized mutation.

The full-library cleanup and exhaustive visual audit remain unfinished.
