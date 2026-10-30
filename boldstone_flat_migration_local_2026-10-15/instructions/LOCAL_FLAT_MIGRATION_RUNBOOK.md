# Boldstone: local flat-folder migration instructions

Prepared 15 October 2026. Specification FMIG-20261015-v1.

## 1. Exact outcome and scope

Implement the user's requested structure, not the earlier catalogue-first physical hierarchy:

```text
BOLDSTONE MASTER/
  Products/
    01 Wall Sculptures/
      Family/
        Member or Combination [Texture] [Colours or Surface Effects] [In Situ]/
          actual-image-file.ext
```

There must be exactly one leaf-folder level after Family. Do not introduce Images, Originals, Working, Approved, Process, Generated, Web Ready, SKU or numbered workflow folders beneath those leaves. A registry may exist outside this image tree. The active migration database, credentials, working logs and backups must be outside Dropbox synchronization.

Keep the existing root name `01 Wall Sculptures`. The earlier tree's `Wall Sculptures` heading was a presentation label, not an approved root rename. Preserve all 63 observed family/group names, including ampersands. Do not merge similarly named families or replace internal family names with retail titles.

This is a narrowly scoped, reversible organization migration. It does not authorize duplicate deletion, BMP retirement, conversion, resizing, recompression, colour correction, image generation, catalog publication, SKU changes, stock decisions or changes to sharing/ownership. Preserve every file's content and stable Dropbox ID. Move existing files natively; do not download/re-upload them as a substitute for a move. Downloads are for backup and verification.

This package supplies exact directory inputs, family specifications, decision templates, an offline inspection helper and the implementation requirements. It does not supply a production Dropbox mutation executor. The local coding agent must implement and test that executor before running it. Proposed `boldstone-flat` commands in the CLI contract are not supplied commands. `tools/check_flat_plan.py` commands are supplied and run offline.

## 2. Source precedence and what the plan actually proves

Use the included `inputs/flat_plan/` CSVs as the fixed directory proposal. Do not recreate destinations by parsing a chat diagram or by asking a model to rewrite the names again.

1. The current user requirement defines the physical depth and naming fields.
2. `Boldstone_347_Proposed_Subdirectories.csv` defines exact proposed family/leaf pairs.
3. `Boldstone_Source_to_Flat_Target.csv` defines the observed source-folder dispositions.
4. `Boldstone_Review_Required.csv` preserves provisional naming/identity/provenance issues.
5. Fresh authorized Dropbox reads determine current objects, contents and availability. They do not automatically authorize a semantic change to the proposal.
6. Immutable historical controls protect prior operations and lineage. Preserve their dates; do not describe imported data as freshly verified.
7. This runbook supplies NEW implementation safeguards, clearly separate from the source proposal.

The saved directory scan has 422 unique folder IDs: 63 top-level groups and 359 subdirectories. Fourteen folders are deeper than the allowed leaf level. The proposal contains 347 unique target leaves, of which 74 are flagged for review. These are dated directory-level counts, not current image counts, completed moves or visually verified product counts.

### The 425-row mapping is intentional

| Source action | Rows | Meaning |
|---|---:|---|
| RETAIN FAMILY | 63 | Keep the family container; this is not a recursive file-routing rule. |
| FLAT GROUP PROPOSAL | 356 | Route files immediately inside this source folder to its proposed leaf. |
| ROOT-FILE HOLDING PROPOSAL | 3 | Route files immediately inside a specified family folder to its provisional leaf. |
| COLLAPSE EMPTY WRAPPER | 2 | Retire only after separately routing children and proving complete emptiness. |
| VIDEO EXCEPTION | 1 | Separate, approval-gated external route; not an image leaf. |
| Total | 425 | Represents 422 unique source folder IDs. |

Three family IDs appear twice: once as RETAIN FAMILY and once as ROOT-FILE HOLDING PROPOSAL. Never build `dict[id] = row` across the whole mapping. Partition folder-control and direct-file rules, or use `(source_folder_id, source_action)` as a key. A last-row-wins importer would either lose the family or incorrectly treat every descendant as a root-level file.

The 347 leaves reconcile as 356 source leaf rows minus 12 duplicate target-group contributions, plus three family-root-file proposals. The two wrappers and video exception are separate dispositions. This arithmetic does not count file moves.

The previous local package remains included as an unchanged historical archive. Keep its state/recovery safeguards and original 350 batch memberships. This flat layout overrides any conflicting proposed deeper physical hierarchy. Do not execute older folder proposals alongside this migration.

## 3. Initialize the local workspace

Extract this package outside any synced directory, for example `C:\BoldstoneMigration\flat-20261015` or `~/BoldstoneMigration/flat-20261015`. These are examples, not inferred local paths. Check the actual machine's Dropbox location and filesystem before configuring paths.

Use a development environment separate from production data. A suitable implementation uses Python 3.11+ (a project minimum), the official Dropbox SDK, standard `sqlite3`, `csv`, `json` and `hashlib`, and Pillow only when binary type/preview checks are needed. Select and lock dependency versions after testing; no dependency lock in this package is represented as production-tested.

Run the supplied offline checks from the extracted package directory:

```bash
python3 tools/check_flat_plan.py validate
python3 tools/check_flat_plan.py family "Fingerprint"
python3 tools/check_flat_plan.py family "Wall Circle"
python3 -m unittest discover -s tests -v
```

On Windows, use `py -3` in place of `python3` where that is the configured Python launcher. The offline helper does not authenticate, download or change anything in Dropbox.

Suggested runtime locations, all outside sync:

```text
runtime/
  state.sqlite3
  snapshots/
  approved-manifests/
  evidence/
  backups/
  reports/
  locks/
```

Preserve `inputs/` byte-for-byte. Put edits in overlays with author/date/reason and the source checksum. Do not edit the original source CSV to turn a proposal into an approval. Preserve old reports and generate new report versions.

## 4. Authorization, root binding and writer coordination

### 4.1 Dropbox application

Use an appropriately authorized scoped Dropbox app that can access the existing library. A Full Dropbox app is appropriate for existing account content; an isolated App Folder would not expose arbitrary existing library content. Full Dropbox access does not override the user's actual shared-folder permissions. Implement OAuth authorization-code flow with PKCE and offline access when continued access is needed. Store tokens in an operating-system credential store, not source files, CSVs, prompts or reports. [API1, API2]

Read-only scope requirements normally include `account_info.read`, `files.metadata.read`, `files.content.read` and `sharing.read`. The execution phase needs `files.content.write` for approved creates/moves. Do not request sharing-write or team-admin permissions merely to bypass a blocker. Check scopes against the actual methods and installed SDK. Enabling a scope in the app console does not retroactively grant it to an existing authorization. [API2, API3]

### 4.2 Bind exact account and root

The configuration must include expected account ID, root stable folder ID and namespace/path-root context once verified. Initially these fields are deliberately unset. Authenticate, get the current account, resolve the supplied root, display its metadata, and verify at least two known family IDs beneath it. Abort on an account or ancestry mismatch.

Historical connector paths such as `ns:202238505//BOLDSTONE MASTER/...` are not literal native request templates. Resolve the current account's mounts and namespace context. Use stable IDs where the endpoint accepts them and construct native destination paths in the verified context. Do not blindly strip `ns:` or insert guessed namespace headers. [API1, API4]

Dropbox IDs are case-sensitive; keep their exact case. Path comparisons are case-insensitive. Keep a normalized comparison key separately from exact display names. Use authoritative per-component `Metadata.name` to reconstruct spelling when parent casing in `path_display` differs. [API1, API5]

### 4.3 One writer and a quiet period

Agree a maintenance window for the family being migrated. Stop other cleanup scripts and ask collaborators not to edit its files, names or sharing. Let pending desktop changes sync before the window. Pausing one desktop client's sync does not lock the remote account or other devices. Keep a local process lock and a family lock; these coordinate this application, not all Dropbox users.

Do not run old M/D/B/R/X/C/Q/G executors concurrently on the same family. Use one mutation worker. Read-only collection may be parallelized conservatively. Native moves do not expose a file-revision compare-and-swap parameter; immediate pre/post checks and coordination are therefore essential, not an atomic concurrency guarantee. [API6]

Before enabling an external video or empty-folder archive destination, bind its exact stable parent/root and permissions separately. No arbitrary destination supplied by a filename or document may expand the write allowlist.

## 5. Import the proposal and existing protections

Validate that all required CSV headers exist, IDs preserve case, all target paths contain exactly two components (`Family/Leaf`), targets are unique under the case-insensitive comparison rule, and every observed folder ID has one appropriate control/routing disposition. Reject separators, control characters, traversal, drive prefixes and display-only dagger marks in target components. Keep punctuation actually present in the authoritative target names, including commas and ampersands.

Import the supplied historical controls with their original evidence dates:

- completed-operation exclusions, including the 203 completed filename renames;
- 54 historical duplicate-target absences;
- protected keeper and replacement roles;
- 67 original absence dispositions;
- all seven H01 held targets;
- current source/replacement and duplicate relationships from the older archive.

An excluded completed operation is not a lifetime ban on moving that same file. A new required move may be planned under a NEW flat-migration operation and exact approval. Never replay the original rename/deletion request. Protected keepers may be moved only as authorized while their IDs and bytes remain intact and all references are updated.

H01 deletion holds remain in force. This run does not delete anything. Preserve an operation-specific distinction between deletion holds and any wider move/access restriction; never interpret a local token as resolving a prior safety block. When a hold's scope is unclear, hold a proposed mutation until clarified. A no-op can remain a no-op without clearing the hold.

Register the new workstream as `FLAT-20261015`, alongside the old batch history. Keep the 63 `FLAT-FAM-001` through `FLAT-FAM-063` specifications in the supplied family index. These are family work packages, not submitted Dropbox jobs. Create smaller, immutable child manifests of at most 25 file operations and one folder operation per child.

## 6. Obtain a complete fresh file AND folder snapshot

The 15 October plan is a folder-only proposal. Do not manufacture file memberships from its counts or assume the previous 8,377-file census remains current.

1. Resolve the bound root by stable ID.
2. List recursively without filtering out files, folders, hidden names or unexpected types. Exhaust all pages using the returned cursor until `has_more=false`. Save each page, its request, observation time and safe response metadata. A short or empty intermediate page is not proof of completion. [API1]
3. Build an ID map and a parent graph. If no parent ID is returned, resolve the immediate parent through normalized current paths and the folder inventory. Treat a missing/ambiguous parent as an exception.
4. Capture file ID, current name, actual current path, immediate parent ID, parent family ID, revision, size, content hash, client/server timestamps and supported type/downloadability fields. Get additional metadata for fields missing from a list result.
5. Resolve all known source folder IDs again. Report absent, externally moved, new, renamed, reparented or type-changed objects. Never substitute a different object occupying an old path.
6. Examine direct files in EVERY family, not just Barbados Wave, Collection Together and Sally With Sculptures. Identify unallocated files under wrappers and files directly in the wall root.
7. Record non-image files, sidecars, shortcuts, unsupported documents, corrupt/unreadable files and videos separately. An extension is only an initial hint. Use authorized binary inspection where needed. Do not discard an unrecognized file.
8. Capture access/sharing context for sources and proposed destinations. Read inherited access where relevant. Lists of the current user's links are not proof that no other user's links or access grants exist. [API7]
9. Retain the folder cursor for drift checks; sharing needs separate rereads because file-change cursors do not report sharing changes. [API8]
10. Save a finalized snapshot ID and checksum. Preflight each operation against fresh state again immediately before execution.

A stable listing does not make the account immutable. Any drift affecting an approved record invalidates that record's preflight until reconciled. New families or destinations require an explicit versioned amendment. Do not cram newly discovered images into the nearest existing leaf just to retain the 347 count.

## 7. Decide provisional storage names without inventing identities

The 74 flags refer to provisional target groups, not 74 definitely distinct unknown designs. An unflagged source label is not a completed image-content audit either.

Use `decisions/Folder_Decisions_TEMPLATE.csv` as a copy-on-write template. Record one of:

- `APPROVE_SOURCE_LABEL_ROUTING`: accept the exact unflagged target for organization, without asserting universal visual verification.
- `APPROVE_PROVISIONAL_STORAGE`: accept the exact flagged target as a temporary storage label, retaining its unresolved status.
- `RESOLVED_APPROVED`: evidence establishes the assignment; attach the evidence and any versioned target amendment.
- `HOLD`: do not perform changes dependent on this decision.
- `PENDING`: no decision yet.

Keep two independent fields: `storage_route_approved` and `identity_verified`. A provisional storage approval must not set the second to true. No dagger is written into a folder name. Do not auto-approve the whole template.

This provides two legitimate completion outcomes:

- Flat storage migration completed with provisional classifications still open, when the user explicitly accepts those storage labels and all file routes pass.
- Partial structural migration with held families/leaves left unchanged, when decisions remain pending.

Never label the second outcome fully flat. Conversely, do not block an otherwise approved mechanical move solely because the artist has not resolved a sale/catalogue question unrelated to its provisional storage route.

When a source contains several actual members or finishes that require splitting, create a per-file override referencing exact IDs and evidence. Keep the original directory proposal and link the amendment. No model may invent member numbers, quantities, texture, colours, physical availability or installation provenance.

## 8. Exact routing algorithm

### 8.1 Route immediate files, not arbitrary descendants

Partition the 425 mapping rows by action. Build a direct-file route for `FLAT GROUP PROPOSAL` and `ROOT-FILE HOLDING PROPOSAL`. Match each file's CURRENT immediate parent folder ID against that table. Do not apply a parent's label to all nested descendants.

Examples:

- Files directly in `Fingerprint Verdigris` stay in its unnumbered target unless individually reassigned by evidence.
- Files directly in its nested `Fingerprint Verdigris 1` use that folder ID's separate flagged target.
- A family-root rule for Collection Together handles its immediate files only, not new nested folders.
- A wrapper with a newly discovered immediate file is held; it has no subject route just because the wrapper's children do.

Every file receives exactly one disposition: already in target, planned in-tree move, separately approved external route, unsupported/non-image hold, identity hold, source-drift hold or unallocated hold. A file must never receive two moves from parent and child scopes.

Source folders relocated outside the bound family/root are not pulled back automatically. Preserve the discrepancy and request an explicit plan amendment. If an unrecognized folder now occupies the desired target, do not silently adopt it.

### 8.2 Select a canonical destination folder

For each exact target:

1. Prefer an existing folder already at that exact target path when its ID is a known contributing source or a previously recorded destination created by this run.
2. Otherwise propose reuse/rename of one contributing source folder only after confirming its entire descendant behavior. A whole-folder move affects every descendant, so all contents must be in scope and destined compatibly; no conflicting nested route or unknown file may be carried along. [API6]
3. If no source can safely be reused, propose creating the exact target folder. Record why a new folder is needed and preserve the disposition of all old folder IDs.
4. If a noncontributing folder or a file occupies the desired target, hold. Explicitly review its contents and adopt it in an amended manifest or choose an approved alternative. Do not infer a merge from matching names.
5. Record canonical destination ID after creation/rename. Subsequent file moves use that bound destination and verify it remains in the expected family.

New empty target folders may be created after approval when the exact complete target tree is required, including currently empty member folders. Do not move unknown material into them to make them look populated.

### 8.3 Merge sources at file level

Where several source folders share a target, move their individual files into the canonical destination. Do not submit a folder-to-existing-folder move expecting a safe file-by-file merge. Preserve all files even when contents match. Keep the source-folder ancestry in the asset register before any move.

Nested folders must be handled in dependency order. Drain deeper source routes before retiring an ancestor. Renaming a canonical container with children is permitted only under a fully approved descendant manifest; otherwise use direct-file moves and leave children for their own routes.

## 9. The plan's specific consolidations and exceptions

The following 12 target groups each consolidate two source groups. Their exact source IDs are already present in the supplied manifests; do not rematch by approximate wording.

| Family / target | Required treatment |
|---|---|
| Abstract Cave Paintings / Abstract Cave Paintings 1 White | Pool its process and ordinary images; retain making-process provenance. |
| Fingerprint / Fingerprint 2 Verdigris In Situ | Pool the two explicitly numbered source groups; preserve the separate unnumbered nested group. |
| Knightsbridge Fountain / Knightsbridge Fountain White In Situ | Pool scene and behind-the-scenes assets; retain image-role distinctions. |
| Leaf Growth / Leaf Growth Finish Unclassified | Pool sand-mould/workshop material only as explicitly approved provisional storage. |
| Moonphases / Moonphases 3 and 4 White In Situ | Pool ordinary and Additional Images sources; retain all distinct files. |
| Rust and Verdigris Panel / Panel Rust and Verdigris In Situ | Pool two sources; keep ArtRoom/source provenance, without asserting real installation. |
| Wall Circle / Wall Circle Members Unclassified | Pool Misc Images and Web Misc only after provisional approval. |
| Wall Circle / Wall Circle Series 001 Blue | Pool source and web-ready series 001; retain both versions. |
| Wall Circle / Wall Circle Series 002 Green | Same rule for series 002. |
| Wall Circle / Wall Circle Series 003 Red | Same rule for series 003. |
| Wall Circle / Wall Circle Series 004 Yellow | Same rule for series 004. |
| Wall Circle / Wall Circle Series 005 White and Black | Same rule for series 005. |

The generated-series colour words are inherited from the historical filename evidence. They are not freshly verified physical variants. Do not simplify away existing `generated-variant-images` or `web-ready-variants` filename context merely because the folder disappears.

### 9.1 Family-root files

The three explicit provisional routes are:

```text
Barbados Wave [direct files]
  -> Barbados Wave/Barbados Moons and Waves Unclassified
Collection Together [direct files]
  -> Collection Together/Mixed Sculptures Unclassified
Sally With Sculptures [direct files]
  -> Sally With Sculptures/Sculptures With Sally Unclassified
```

The saved Barbados listing had 19 files and Sally had one; Collection Together was sampled, not completely file-enumerated for that proposal. Recount and classify current files. The snapshot includes pre-existing JPG additions in Barbados; do not re-convert or delete associated BMPs in this migration.

Collection Together and Sally With Sculptures remain as the user's proposed supporting groupings. Do not remove them merely because they are not conventional product families.

### 9.2 Wall Circle wrappers

`id:cnqzTNngPVsAAAAAAAs74Q` is the Generated Variant Images wrapper.
`id:cnqzTNngPVsAAAAAAAs87g` is its Web Ready Variants wrapper.

Their earlier direct-file lists were empty, but they contained descendants. Move/reconcile those descendants first. Recheck for new direct files. Only then propose retirement of the fully empty wrappers. A directory with zero direct files is not necessarily empty.

### 9.3 Videos

The source folder `id:cnqzTNngPVsAAAAAAAyjbQ` (Videos Of Sculpture Making) was observed outside the wall tree at `/BOLDSTONE MASTER/Products/Videos/Videos Of Sculpture Making`. This is an observed previous change; do not replay it or pull it back in.

The Azure video source `id:cnqzTNngPVsAAAAAAA5RBg` has the proposed external destination `/BOLDSTONE MASTER/Products/Videos/Wall Panel Azure Blue Marble`. That external write must be separately approved and allowlisted. Resolve the current source and destination first. Inspect the complete source for image/nonvideo files and nesting. Move the whole folder only if its full contents and destination semantics are approved; otherwise use explicit per-file external routes. Preserve both copies on collisions. An image-only final audit cannot pass with unresolved videos left in the tree.

No general rule authorizes moving every unexpected non-image to this Azure destination. New video families, documents and sidecars need their own routes outside the image tree or remain reported holds.

## 10. Filenames and collisions

### 10.1 Default: preserve the basename

The requested change is the folder organization. Keep existing filenames and actual extensions by default. Native moves preserve bytes, including embedded metadata. Do not re-encode images to move them.

The long verified filenames from the earlier 203-file batch are not a reason to replay that batch. If a moved image's prefix becomes misleading, record it in a separate `FLAT-NAME` queue. Approval of a folder path is not blanket approval to rewrite all basenames.

An optional naming pass may use:

```text
<approved-leaf-slug>__<preserved-source-stem>[__role-or-rendition][__asset-<id-token>].<actual-extension>
```

Do not duplicate an existing approved prefix or `__asset` suffix. Preserve camera numbers, meaningful details, source UUIDs and provenance. Do not make an unknown image look documented by inserting an unverified role such as `installation`. Generated context can be recorded as an inherited source-folder assertion until independently established.

### 10.2 Same basename does not authorize deletion

Before executing, reserve all intended destinations against the full current destination contents and all other proposals, using case-insensitive path keys. Preserve exact display spelling separately.

- Same file ID already at the correct destination: verified no-op, not a second move.
- Different IDs, different bytes: preserve both.
- Different IDs, equal bytes: preserve both in this migration; record a new duplicate candidate for a later separately authorized review.
- Original and web derivative: preserve both and their relationship.
- Existing unapproved object at destination: hold or amend the exact manifest; never overwrite.

For collisions between known in-scope sources, the proposed deterministic rule is to preserve the already-at-target file's name. For other competing files, sort by case-sensitive full Dropbox ID and allocate collision names with `__asset-` plus the first 12 hex characters of SHA-256 of the FULL ID. Extend the token if needed until unique. Hash the ID, not the content, so byte-identical copies still get different names. Treat this as a proposed filename change that must be present in the approved manifest.

Do not let Dropbox choose a surprise suffix: use `autorename=false`. Do not trim a meaningful long basename automatically; propose an explicit shortened name while preserving the full original in the register. Validate Windows/macOS-friendly component restrictions without claiming your local portability policy is a Dropbox maximum.

### 10.3 Case-only changes

For a change such as `in Situ` to `In Situ`, the documented move API does not directly support a case-only rename. Use two individually journaled moves through a preapproved unique temporary sibling name, then the exact final name. Verify each step, and on restart inspect which of the three states currently exists. No final temporary directory is allowed. Do not mix a case-only folder hop with unrelated child operations. [API6]

## 11. Backups, approvals and manifests

Before the first mutation, save a consistent database backup and immutable starting manifests. Preserve verified local copies of all files this run will move, or a verified independently recoverable backup that covers their exact revisions. Compute required capacity from the actual snapshot. An online-only placeholder is not a verified backup. A full-library backup is preferable where practical; the changed-file backup is the minimum proposed execution gate here.

Download the intended revision, compare Dropbox content hash and size, and compute ordinary SHA-256 as well. Dropbox's content hash is a different algorithm from the ordinary file SHA-256; use each in its own field. A local backup is usable only when the saved bytes match their intended source revision. [API9]

A file-operation manifest must include at least:

```text
run_id, operation_id, family_batch_id, child_batch_id
source_file_id, source_parent_folder_id, source_family_folder_id
observed_source_path, observed_name, expected_rev, expected_size
expected_dropbox_hash, backup_path, backup_sha256
route_rule_id, exact_target_relative, destination_folder_id_or_creation_dependency
proposed_destination_name, collision_reason, provenance_record_id
storage_decision_id, identity_status, hold_status
approved_manifest_sha256, approval_by, approval_utc
```

Folder manifests also list the expected descendant ID set, source/destination parent IDs, access context, whether the folder is canonical or retiring, and every affected child operation dependency.

Approve the exact manifest checksum, not just the family name. Changing its destinations, collision policy, membership, relevant revisions or dependencies invalidates the approval. Directory-plan approval and file-operation approval remain separate. Your coding agent must not grant itself user approval.

## 12. Execution procedure and verification

### 12.1 Preflight immediately before each child

Resolve sources and destination parents by ID. Confirm account/root/family ancestry, expected names, current revision, size/hash, unchanged access context, no unresolved hold, available verified backup and collision-free destination. Check the proposed target is an approved leaf in the same family unless explicitly external.

If the source is already at its approved destination, reconcile its state and provenance rather than repeat a mutation. If another actor moved it, record observed convergence separately from an operation demonstrably executed by this run.

### 12.2 Durable state first

Write the complete intended request and expected before-state transactionally before submitting. Set `SUBMITTING` and commit before the network call. Preserve a request digest and safe request ID; never log OAuth credentials or signed download URLs.

Prefer individually attributable file moves, capped at 25 per checkpoint child. A folder operation is a separate one-folder child. Native batch moves are permitted only when per-entry outcomes are recorded and the asynchronous job is polled to terminal status. A batch can have mixed success and failure. [API6]

Set `autorename=false`, `allow_ownership_transfer=false`. Do not enable ownership transfer to make a failing move work. Follow actual permission errors; do not fall back to copy/upload/delete or browser automation.

### 12.3 Independent post-read

After a successful response, make a NEW metadata request and a relevant fresh listing. For each file verify:

```text
same stable file ID
exact approved filename
expected canonical parent ID and family ID
expected final path within the bound root/context
same byte size and Dropbox content hash as preflight
actual extension unchanged except a separately approved format-label correction
no unapproved sharing or ownership change
```

Record the post revision and modification times without assuming metadata timestamps cannot change during a move. Verify all source files are accounted for; sum-of-bytes equality alone is insufficient.

For a moved folder, verify its own ID and final name plus the complete approved descendant ID set and each affected file's resulting location and content metadata. Do not count implicitly moved child files as separate new API file-move operations, although each needs an outcome record.

A source path is expected to be vacant after a rename/move only when it is not reused by another approved operation. Stable-ID checks, not path absence alone, determine what happened.

### 12.4 Throttling and uncertain outcomes

Use bounded retries with backoff for safe read failures. Honor rate-limit retry information. Configure the SDK/transport so it cannot silently replay a mutation after an uncertain 5xx/timeout before the application has reconciled its outcome. Dropbox has namespace contention and rate limits; more concurrent writes are not necessarily faster. [API10]

A timeout or interrupted response after submission becomes `OUTCOME_UNKNOWN`, not failed-with-no-effect. Pause dependent operations. On resume, resolve the source ID and approved destination, compare hashes and examine any saved job ID before deciding whether to continue or retry. Preserve “success observed; receipt unavailable” as a distinct evidence level when attribution cannot be established.

## 13. Retire obsolete folders without risking recursive deletion

Flattening is not complete if redundant empty nested wrappers remain. But the normal Dropbox folder-delete operation deletes descendants, and its revision condition is for files, not a delete-only-if-empty folder guarantee. Do not call it merely because an earlier listing said no direct files. [API11]

NEW recommended safeguard: after all mapped descendants are verified, relocate obsolete, fully empty, noncanonical folders to a separately approved archive OUTSIDE the wall-sculpture root, rather than deleting them. Example proposed home:

```text
/BOLDSTONE MASTER/Migration Archives/Wall Sculptures/<run-id>/empty-<folder-id-token>
```

This archive is an implementation proposal, not an existing folder or an automatically authorized external destination. Bind and approve its parent first. Do not create the archive as a fourth level under a family. Preserve original source paths in the register instead of recreating the whole source tree under each archived folder.

Retire deepest-first, one folder at a time. Immediately before each retirement, require complete fresh enumeration with zero files AND zero subfolders. Preserve the folder ID and its historical name. Stop when a shared-folder boundary, access change, active link dependency or unknown restriction is encountered.

The empty-check and move are not atomic. With concurrent uploads, an item might appear between them. Immediately list the archived folder too. Any unexpected archived descendant triggers `RACE_DETECTED`: stop, preserve the content, reconcile or return it safely, and do not count it as successful empty-folder retirement. The maintenance window is required to reduce this risk. No data is deleted by this preferred route.

Canonical destination folders and family folders must never be retired. Do not retire a source while a pending operation still depends on its parent ID or while rollback requirements are unresolved. When external archival is not approved or cannot preserve access, leave the source and report that structural completion remains partial.

Permanent removal of archived empty folders can be a later, separately approved task; it is not part of this migration.

## 14. State, restart recovery and rollback

Keep the active SQLite database local, not in a synced folder. Use transactions, foreign keys and consistent backups. An append-only event table is authoritative; exported JSONL/CSV is derived through a transaction/outbox pattern. Do not treat two independently written logs as mutually consistent without a reconciliation mechanism.

The supplied `spec/STATE_SCHEMA.sql` is a standalone logical schema for this new workstream, not an in-place migration of the old application. Integrate it through a versioned database migration or use a separate database linked to immutable historical source references. Never overwrite an existing checkpoint database with a new empty schema.

Recommended operation states:

```text
PLANNED -> REVIEWED -> APPROVED -> PREFLIGHTED -> SUBMITTING
        -> SERVER_SUCCEEDED -> VERIFYING -> VERIFIED
```

Separate states include `NOOP_VERIFIED`, `HELD`, `FAILED_DEFINITE`, `OUTCOME_UNKNOWN`, `OBSERVED_AT_TARGET`, `RACE_DETECTED`, `ROLLBACK_PLANNED` and `ROLLED_BACK_VERIFIED`. Ending an attempt does not imply its objective succeeded. A checksum is tamper-evidence for accidental change, not cryptographic proof of who approved it; keep actual approver identity/evidence separately.

Recover first, then schedule new work. Check exact source ID, content state and destination after any interruption. Avoid duplicate operations through a deterministic operation key derived from run, action, source ID, expected source state, destination and manifest version. No “exactly once” guarantee is claimed across the database and a remote API; reconciliation handles uncertain outcomes.

Rollback is a NEW approved inverse plan from recorded before/after states. Do not run a blanket reverse-CSV loop.

1. Stop new work and capture current state.
2. Restore retired source folders from the external archive to their recorded parent IDs/paths, parents before children, checking collisions.
3. Restore any case-hop or folder-move dependency in an order that makes original file destinations available. Derive the dependency graph; reverse chronology alone is not always sufficient.
4. Move each affected file ID back to its recorded original parent/name only if current content and state match the expected migration outcome. Do not revert a collaborator's later edits by overwriting them.
5. Verify every inverse operation independently.
6. Newly created destination folders may be archived only when fully empty; existing folders must not be removed just because this migration reused them.

A binary backup can recover content if needed, but re-uploading it may not restore the original ID, history, comments or links. Record that limitation and never call such a recovery a perfect rollback.

## 15. Completion tests and deliverables

Evaluate against the fresh starting snapshot plus explicit amendments, not a stale historical image count.

### Structural tests

- Bound root and all retained family IDs remain correct.
- Every image's path relative to the wall root is exactly `Family/ApprovedLeaf/Filename`.
- No files remain directly in the root or a family.
- No folders remain below an approved leaf, including empty nested folders.
- Every leaf belongs to the exact approved target set and has the exact approved spelling.
- Every unexpected file, folder or non-image has an explicit disposition; none is silently dropped.
- External video destinations contain the expected IDs; already-external material was not replayed.
- There are no temporary case-hop names or unintentionally created conflict folders.

347 leaves and 63 family folders imply 410 descendant folders only if the entire original proposal is adopted, all empty targets are retained and no amendment is required. Treat that as a conditional plan expectation, not a forced live count. A new complete visual review may justify more leaves through an approved amendment.

### Conservation and integrity tests

Track the same IDs, not just counts. With no newly added files and no outside changes:

```text
starting_in_scope_file_IDs
  = final_wall_tree_file_IDs UNION explicitly_moved_external_file_IDs
```

The sets must be disjoint for current location and every file retains its expected size and content hash. If another actor adds/removes/edits content during the run, report it separately and reconcile it before closing. Unexpected content captured during an archive race is not a legitimate planned external export.

Every starting folder ID is retained, renamed/reparented with identity preserved, or externally archived as an empty source. Newly created folder IDs are recorded separately. No accidental missing folder IDs can be hidden by an equal total count.

All protected keeper/replacement IDs remain accounted for. Prior absent files are not attributed as new deletions. No image upload, file-content write, duplicate deletion or BMP conversion occurred in this organization run.

### Evidence and coverage tests

Preserve exact original filename, original parent/source hierarchy, inherited roles, source/derivative relationships, generated context, backups, approval and operation receipts. Flagged provisional classifications remain flagged until actual evidence resolves them. Folder depth completion does not establish ecommerce readiness or a completed in-situ audit.

Generate these outputs:

```text
Run_Summary.md
Current_Flat_Tree.txt
Current_File_Inventory.csv
Source_Folder_to_Destination.csv
File_Operation_Ledger.csv
Verified_Moves.csv
Noops.csv
Filename_Collisions_and_Resolutions.csv
Retired_Folders.csv
External_Moves.csv
Unallocated_and_Held_Items.csv
Provisional_Identity_Register.csv
Asset_Provenance.csv
Rollback_Proposal.csv
Before_After_Integrity.json
Package_Checksums.json
```

A readable workbook may mirror those tables, but must not be the only authoritative execution state. Keep registries and reports outside the image-only tree. A report may state “flat organization complete; 74 provisional label issues retained” only when the mechanical criteria truly pass and the final unresolved count is freshly calculated. Otherwise use a partial status with exact blockers.

## 16. Practical rollout order

| Stage | Task | Stop/checkpoint |
|---|---|---|
| FLAT-00 | Validate original inputs and import historical protections. | Original files preserved and schema/route checks pass. |
| FLAT-01 | Authenticate, bind root and external allowlists, arrange quiet period. | Correct account/ancestry and authorization recorded. |
| FLAT-02 | Complete fresh file/folder snapshot, backup changed files, build drift report. | Every known and new object is accounted for. |
| FLAT-03 | Record target/storage decisions and approved amendments. | No implicit approvals; held items stay held. |
| FLAT-04 | Build exact per-file/folder manifests and run collision simulation. | Preview says precisely what will change. |
| FLAT-05 | Test on disposable fixtures, then pilot one simple production family. | No unexplained ID, hash, path or access changes. |
| FLAT-FAM-* | Run each approved family in small dependency-ordered children. | Verify each child, save state, then continue. |
| FLAT-EXT | Handle explicitly authorized Azure/non-image exceptions. | Correct external IDs and no unallocated non-images. |
| FLAT-RETIRE | Archive fully empty obsolete source folders. | Zero nested folders left, with race checks. |
| FLAT-NAME | Optional, separately approved file-prefix cleanup. | No unwanted loss of identifiers or provenance. |
| FLAT-FINAL | Fresh whole-tree census, conservation, depth and exception audit. | Date-stamped complete or accurately partial report. |

Suggested production pilots are Abstract Cave Paintings (small process/ordinary consolidation), then Fingerprint (nested routing), then Wall Circle (multi-source/generated derivatives). A pilot with pending provisional approvals remains held. The family index provides all 63 packages, so the pilot order does not remove any family from the exhaustive scope.

The existing 350 review batches remain separate. Structural changes invalidate their current-path assumptions and may change same-folder duplicate eligibility. Rebase those queues by stable IDs after this run; do not rewrite their old membership or preserve stale deletion readiness. Run later conversion/deduplication work only under its own current approvals.

## 17. Maintenance after migration

Adopt new images into one exact family/leaf directly. New leaf proposals use the same field order and require actual evidence for texture/finish/context. Store processing stage, camera name, source lineage, role and publication approval in a register and, where useful, the basename, not a new directory tier.

Run the depth/name/orphan lint after each intake or family change. Detect file-content changes separately from name/path changes. Recompute derivative/duplicate relationships after changes. Do not let a scheduler execute structural changes without a reviewed manifest. Keep a reproducible release of the approved mapping and an append-only change history.

## 18. Official implementation references

These support API behavior only. The source CSVs, not public documentation, define Boldstone's proposed folders. Recheck installed SDK signatures before implementation.

- [API1] Dropbox File Access: https://docs.dropboxapi.com/riviera/docs/guides/file-access
- [API2] OAuth with offline access and PKCE: https://dropbox.tech/developers/using-oauth-2-0-with-offline-access
- [API3] Scope authorization behavior: https://dropbox.tech/developers/customizing-scopes-in-oauth-flow
- [API4] Team files, namespace and root contexts: https://developers.dropbox.com/dbx-team-files-guide
- [API5] Dropbox HTTP API paths and case behavior: https://www.dropbox.com/developers/documentation/http/documentation
- [API6] Official SDK move, batch/check and create methods: https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html
- [API7] Official SDK sharing-list methods, scope and visibility limits: https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html
- [API8] File cursor and sharing-change distinctions: https://developers.dropbox.com/detecting-changes-guide
- [API9] Dropbox content-hash algorithm: https://www.dropbox.com/developers/reference/content-hash
- [API10] API rate limits and namespace contention: https://developers.dropbox.com/dbx-performance-guide
- [API11] SDK `files_delete_v2`: recursive folder deletion; `parent_rev` does not support folders: https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html
