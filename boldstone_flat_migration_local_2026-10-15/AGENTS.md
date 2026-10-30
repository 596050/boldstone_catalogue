# Implementation brief: Boldstone flat-folder migration

Read `instructions/LOCAL_FLAT_MIGRATION_RUNBOOK.md` completely before coding. The user explicitly wants:

```text
01 Wall Sculptures / Family / Member-or-Combination [Texture] [Colours-or-Surface-Effects] [In Situ] / actual images
```

Exactly one folder depth after Family. This overrides previous deeper physical-layout proposals. Do not add Images, Originals, Working, Generated, Web Ready, Process or SKU subfolders. Do not rename the existing wall root. Preserve family names exactly.

## Sources and scope

Use the exact CSVs in `inputs/flat_plan/`. The folder proposal has 347 unique target leaves, 74 provisional review leaves, 63 family/group headings, 422 unique observed folder IDs and 425 source mapping rows. It is not a file-level move manifest. All live file memberships, revisions, hashes and actual type classifications must come from a fresh complete authenticated snapshot.

The mapping rows comprise 63 RETAIN FAMILY controls, 356 FLAT GROUP PROPOSAL direct-file routes, three ROOT-FILE HOLDING PROPOSAL direct-file routes, two empty-wrapper controls and one VIDEO EXCEPTION. The three family-root rules intentionally repeat family IDs. Do not deduplicate by ID alone or route all descendants according to a parent rule.

Use the new `FLAT-FAM-*` packages in `rules/Family_Migration_Index.csv`. Keep all old 350 batch IDs and memberships unchanged. Preserve the old local implementation ZIP as historical evidence. Keep its useful state/recovery safeguards, but do not let old layout proposals override this one.

## Build and test

Implement a local, resumable, read-only-by-default application using the official Dropbox API. The supplied offline helper is NOT the live executor. The source schema and CLI contract are implementation requirements, not completed production code. Use a fake adapter and disposable authorized test directory before writing in the production library. Record actual test results; do not claim a live test from an offline fixture.

Bind the correct account, root folder ID and namespace context. Obtain source files by stable IDs. Validate ancestry and destination allowlists. Store tokens in the OS credential store and the active database/backups/logs outside Dropbox synchronization. Do not automatically mount, unshare or transfer ownership to bypass a blocker.

Collect a fully paginated file-and-folder inventory. Save raw evidence and normalize current parent relationships. Compare observed source IDs with the proposal and classify new, missing, externally relocated, renamed and changed objects. Capture all file types, hidden/unusual names and direct files in every family. Do not invent current counts from the saved 14/15 October checkpoints.

## Decisions

Keep route approval distinct from physical identity verification. Source-label targets can be approved for organization without a universal visual claim. Flagged targets may be accepted explicitly as provisional storage, with unresolved status preserved; or held. Do not guess members, quantities, texture, finishes, actual manufactured variants or installation provenance. A semantic split needs exact file IDs, evidence and a versioned target amendment.

The agent cannot approve its own production operations. Show an exact manifest and obtain operator authorization bound to its checksum. The user's request for local instructions is not a pre-signed approval file. Do not silently mark the supplied decision template approved.

## Operations

Prefer an existing known source folder already at the final path as the canonical leaf. Reuse/rename a contributing source folder only when its entire descendant set can safely travel together. Otherwise create the canonical leaf and route files individually. An unrelated object at a desired path is a conflict, not automatic permission to adopt it.

Match files by immediate parent ID, never nearest-name or inherited ancestor rules. Nested Fingerprint groups and Wall Circle source/web-ready series each have their own routes. Keep original ancestry and inherited provenance even after containers disappear.

Pool files, not folder names. Multiple source folders can share a canonical leaf without removing a single image. Preserve every distinct file ID, even for byte-identical copies. Keep basenames and extensions by default. Resolve known filename collisions with explicit deterministic ID-derived suffixes in the approved manifest; never overwrite and never use server autorename. Optional filename-prefix work is a separate FLAT-NAME manifest, not replay of earlier renames.

Use native move with `autorename=false`, ownership transfer disabled, one mutation worker, at most 25 file operations per child and one folder operation per child. Case-only renames require two approved, journaled hops. Do not move a folder with unknown or differently routed descendants as a bulk shortcut.

Before each mutation, verify expected ID, parent/family/root, name, revision, bytes, content hash, permissions, destination availability, approved decisions and verified backup. Commit intent before the call. Capture receipts and per-entry status; poll native async jobs to completion. Afterward, independently reread IDs, exact paths and parents, sizes and hashes. A request accepted is not an outcome verified.

Timeout/connection-loss after submission means OUTCOME_UNKNOWN. Stop dependent work and reconcile by ID/destination before any retry. Disable hidden mutation retries that would bypass reconciliation. A later observation at the target is not proof this run executed the move.

## No deletions or image processing

This migration does not delete duplicates, retire BMPs, convert, resize, compress, recolour, generate, upload replacement images, publish listings or change SKUs/stock. The existing 203 rename exclusions are exclusions from replaying those operations, not an immutable-file ban. Keeper/replacement protection and seven H01 holds remain. Moving a protected file requires an exact new approval and maintained lineage; a local token does not clear an old hold.

The existing Videos Of Sculpture Making folder is already outside this tree in the saved observation; do not replay its relocation. Azure's video folder has one proposed external home, which requires a separate destination allowlist and approval. Other unexpected nonimages require explicit separate routes.

For obsolete source folders, the recommended new safety measure is an explicitly approved external archive of fully empty folders. Retire deepest-first only after zero files AND zero subfolders are freshly confirmed. No recursive deletion function. Check the archived folder after its move to detect concurrent-arrival races; preserve any unexpected content and stop. Never archive canonical leaves or families. The archive is outside Wall Sculptures, not a new workflow subfolder within it.

## Completion and handover

Verify exact root/Family/Leaf/File depth; no root/family loose files; no nested folders, including empty wrappers; no unapproved target names; no unknown files; all external IDs reconciled; no temporary hops; all file IDs, bytes and hashes conserved; all source folder IDs retained/renamed or safely archived; all prior protected IDs preserved. Count 347 leaves only when the whole proposal is adopted without amendment. Do not force a stale file count or confuse mechanical completion with identity/ecommerce completion.

Produce the run summary, final flat tree, current file inventory, source/target folder map, exact file-operation ledger, verification evidence, no-ops, collisions, external and archived-folder records, provisional classifications, unallocated/held exceptions, backups, rollback proposal and package checksums. Preserve immutable historical files.

Implement a dependency-aware rollback that restores archived parents first, then file locations without overwriting later changes. Any binary re-upload recovery must acknowledge that content recovery may not recover the original ID/history.

Start with offline validation, read-only imports, fake-adapter tests and a complete dry plan. After test success and explicit operator approval, pilot Abstract Cave Paintings, then approved Fingerprint and Wall Circle cases. Verify and checkpoint every child before continuing through all 63 family specifications. Rebase old cleanup queues by stable IDs after flat migration; do not run overlapping old executors.
