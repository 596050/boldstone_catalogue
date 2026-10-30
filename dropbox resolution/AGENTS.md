# Instructions for the local coding agent

Build the Boldstone local Dropbox cleanup application described in `instructions/01_LOCAL_IMPLEMENTATION_RUNBOOK.md`. Read the actual source manifests and last checkpoint, not only this summary.

## Non-negotiable boundaries

- This pack is an implementation handover. The only shipped executable is `bootstrap.py`, an offline verifier/importer. Proposed `boldstone` commands and live executors remain to be implemented and tested.
- Preserve the **350 existing batch IDs and exact CSV memberships**, their original order and historical statuses. The next untouched batch is **M004**. S02 previously failed; J001-J003 and I00 remain partial; H01 retains seven holds.
- Do not replay historical operations. Preserve the 203 recent completed rename exclusions, 54 already-absent historical duplicate targets, 67 original-ID absence dispositions and 1,813 keeper/replacement protection records.
- No production Dropbox writes without correct account/root, exact approval, safe preflight, required verified backup and independent verification. Read-only is the default.
- Never bypass H01, locks, permissions, administrator policies, sharing/history uncertainty, or a failed integrity check. Do not implement force/ignore-hold/permanent-delete/folder-delete options.
- Use native Dropbox file IDs and discover actual namespace/API paths. Historical connector `ns:...//...` strings are not executable native paths to copy blindly.
- Keep current metadata, binary integrity, historical evidence, identity decisions and operation verification as separate facts.
- Code can orchestrate image review, but it cannot infer design aliases, finishes, quantities or real-installation provenance from filenames alone. Model proposals never authorize file mutations.
- Do not upload private images to an external model without explicit permission. A local human review interface must work without external model access.
- Keep the live state database outside the Dropbox sync directory. Preserve original inputs and append-only events.

## Build order

1. Verify this pack, inspect CSV headers and source history. Run the offline bootstrap and tests.
2. Implement typed imports, immutable state, native account/root validation, read-only census, metadata audit, binary download/QA, and a fake Dropbox adapter.
3. Import `supplemental_identity/` as additional historical source evidence for a new I00 consolidation attempt. The 29+18+14 rows overlap; they are not a unique unresolved total. Do not silently change the old partial status.
4. Implement exact-manifest approval, preflight, intent journal, crash reconciliation and independent verifier before live mutation code.
5. Implement R/X/C/Q/G with their gates, then V/T/Z01. Enforce per-batch limits.
6. Pass the acceptance tests using synthetic data and a separately approved disposable Dropbox sandbox. Report untested account-specific behavior.
7. Only then perform specifically requested, bounded production reviews or exact approved child mutations. Save a checkpoint after each batch.

## Definition of done

All original files have traceable evidence/disposition; every claimed mutation has a receipt or explicitly recovered/uncertain attribution plus independent state verification; every required retained/replacement image is reviewed to its stated scope; every error/hold remains visible; restarting after any API call cannot silently duplicate a destructive action.

Stop and report specific missing authority or evidence instead of guessing. Do not report a failed test or a retained deletion hold as successful cleanup merely because the attempt ended.
