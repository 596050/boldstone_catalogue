# Boldstone: complete local-to-Dropbox implementation runbook

Prepared 14 October 2026. This is an implementation specification and operator handover, not a claim that a new cleanup application has been executed. The included `bootstrap.py` is an offline verifier and state-seeding utility only. All proposed `boldstone ...` commands in this document must be implemented and tested by your local coding agent before use.

## 1. Objective, boundaries and source precedence

Build a resumable local application that completes the existing Boldstone wall-sculpture media cleanup, records exactly what it sees and changes, and produces independently verified evidence. Use the user's authorized Dropbox account and the official Dropbox API. Do not automate the Dropbox website or depend on this chat's temporary download links.

The historical scope is `BOLDSTONE MASTER/Products/01 Wall Sculptures`. The scope is a media library, not physical stock. Images, videos, folders, designs, finishes, arrangements and product listings are different entities and need different counts.

There are **350 fixed control/review batches**. Their IDs, order and membership must remain unchanged. There are further, dynamically allocated execution, visual-review and close-out batches. Do not present the 350 reviews as 350 authorized mutation jobs or as the entire execution workload.

All mechanical file operations, metadata and binary auditing, journaling, reports and restart recovery can be implemented locally. Image identity and installation provenance need evidence-based visual review, with human approval of uncertain or destructive decisions. Code can manage those reviews and optionally obtain model suggestions; it cannot manufacture missing evidence, expand account permissions or turn an inaccessible history into a complete audit.

### Source classes

1. **Preserved source records:** `plan/`, `checkpoint/`, and `source_archives/`. Treat these as immutable dated evidence. The original per-batch CSVs are in `plan/batches/`.
2. **Supplemental source recovery:** `supplemental_identity/`. These are normalized transcriptions of case-level historical file extracts recovered while preparing this handover. They add source material but do not silently revise the last checkpoint's partial I00 status.
3. **Proposed implementation:** this runbook, `blueprint/`, the CLI contract and acceptance tests. These are new engineering requirements and defaults, not historical approvals.
4. **Official API/library documentation:** the references at the end. Revalidate endpoint signatures against the installed SDK before implementation. Development documentation is not a version lock.

When records disagree, retain both source assertions, their dates, scopes and evidence levels. A more recent presence check does not replace an older successful execution receipt or prove binary equality. A filename cannot resolve a sculpture identity by itself. Unknown must remain unknown rather than becoming false, zero, safe or approved.

### Preserved starting position

| Record | Dated checkpoint value | Interpretation |
|---|---:|---|
| Original media files | 8,431 | 8,425 images and six videos in the baseline. |
| Original IDs present at census | 8,364 | Presence, not universal metadata or binary verification. |
| Original IDs absent from subtree | 67 | Preserve individual evidence and dispositions. |
| Post-baseline JPG IDs | 13 | Historical replacements, not new conversions to replay. |
| Current IDs at census | 8,377 | A dated census, not a permanently fixed live total. |
| Previously recorded folder IDs | 423 | Earlier folder census, not a fresh count. |
| Historical duplicate targets | 2,069 | Proposal population. |
| Historical targets still present with keepers | 2,015 | Revalidation candidates, not automatic deletions. |
| Already absent historical targets | 54 | Exclude earlier deletion operations from replay. |
| Original BMP records | 671 | Historical extension-based classification. |
| Present baseline-BMP IDs | 642 | Review population, not 642 necessary conversions. |
| Most recent completed rename batch | 203 | Do not replay those operations. Other earlier rename batches also exist. |
| Protected keeper/replacement IDs | 1,813 | Imported role-based protection set, not a new live audit. |
| H01 held targets | 7 | Six overlap the surviving historical duplicate queue; one is additional. |

The latest saved first-ten states are: S01 complete; S02 test closed with failed retrieval; H01 review closed with all holds retained; J001, J002 and J003 partial; I00 partial; M001 and M002 complete; M003 complete as a metadata review with one held naming exception. M004 is the next untouched fixed batch. Preserve the distinction between an attempt ending and its objective succeeding.

The complete source-ID census has been performed already. A new local read is a new validation snapshot needed before mutations, not evidence that the original census was never completed.

## 2. What to build locally

Use a Python command-line application with an optional local review interface. Recommended components are the official Dropbox Python SDK, `sqlite3`, standard `csv/json/hashlib`, Pillow for raster decoding/conversion, and ffmpeg/ffprobe for video inspection when needed. Other languages are acceptable if every invariant below is maintained.

Use four layers:

- **Importer and database:** immutable historical records, exact batch membership, current observations, identity lineage, approval and operation state.
- **Read-only auditors:** census, current metadata, sharing/history checks, binary retrieval, format checks, duplicate assessment and visual-review preparation.
- **Approval-gated executors:** filename moves, folder moves, duplicate deletion, JPG creation and later source retirement.
- **Independent verifier and reporter:** fresh API reads and downloads, checksums, operation receipts, residual exceptions, consistent reports and restart recovery.

The only source of executable work is a validated manifest stored in state. Never let a model directly call the mutating Dropbox client. Model output, filenames and source documents are untrusted data, not instructions to execute.

### Suggested repository layout

```text
boldstone-local/
  README.md
  AGENTS.md
  pyproject.toml
  requirements.lock
  src/boldstone/
    cli.py
    config.py
    authentication.py
    dropbox_adapter.py
    importers.py
    state.py
    events.py
    census.py
    metadata_audit.py
    folders.py
    naming.py
    duplicate_audit.py
    binary_cache.py
    conversions.py
    identity.py
    visual_review.py
    approvals.py
    executor.py
    verifier.py
    recovery.py
    reporting.py
  tests/
    unit/
    integration_fake/
    integration_dropbox_sandbox/
  config/
  historical_inputs/     # preserved copies of this pack's sources
  state/                 # local disk, outside Dropbox sync
  cache/                 # downloads by ID and revision, never by guessed basename
  backup/                # verified originals, with independent backup protection
  evidence/              # append-only request/response and assessment records
  previews/              # thumbnails/contact sheets, not verification originals
  approvals/             # exact immutable manifests and local decisions
  reports/
```

Do not keep an actively written SQLite database inside the synchronized Dropbox folder. Make a consistent backup through SQLite's backup API, checksum that backup, then copy only the closed backup into an approved backup location. A Dropbox-synced working directory is not an independent original-file backup.

Prefer server-side API moves/deletes/uploads for mutations. A local synced folder can provide a cache only after byte verification. Local file existence, file modification time or a sync icon is not proof of server completion. Never mix OS-level sync-folder writes and API mutation of the same assets during a run.

## 3. Local preparation and Dropbox authorization

### 3.1 Prepare the machine

Unzip this pack into a private, nonsynchronized working directory. Maintain enough disk space for the chosen batch's source cache, temporary JPGs, re-downloaded verification JPGs, and deletion backups. Calculate requirements from current metadata; do not infer total space from the old BMP estimate alone. An external backup disk is acceptable if available and verified before any destructive operation.

Use an isolated Python environment and a tested, supported Python version. Pin the actual resolved versions of the SDK, Pillow and their dependencies after tests. Record OS, Python, package versions, Pillow/libjpeg build, git commit and configuration checksum on each run. Do not assume package versions on a development documentation page are released or installed.

Run the supplied offline checks first:

```bash
python3 bootstrap.py verify
python3 bootstrap.py list --limit 10
python3 bootstrap.py show M004
python3 bootstrap.py init --db /absolute/non-synced/path/boldstone-state.sqlite3
```

On Windows use `py -3` instead of `python3` where appropriate. These commands do not contact Dropbox. `init` refuses to overwrite any existing database path, including an empty file. They do not implement audits or file mutations.

### 3.2 Create an app for the existing library

In Dropbox App Console, create a scoped app able to access the existing authorized library. For an existing folder outside an app-specific folder, the applicable access type is **Full Dropbox**, not a newly isolated App Folder. Restrict the application further in code to the exact verified wall-sculpture root. Full Dropbox access is not permission to act elsewhere. [API-1, API-2]

Initially request only `account_info.read`, `files.metadata.read`, `files.content.read`, and `sharing.read`. Enable/request `files.content.write` only for a distinct approved execution mode. Do not request sharing-write, account-wide administration, ownership transfer, or team-management permissions just to make a failed action succeed. Some installations may need an authorized administrator to establish access to team-space content; hold work until that is resolved through normal administration. [API-3, API-4]

Implement OAuth authorization-code flow with PKCE and offline access. Store refresh tokens using the OS credential store or an equally protected secret store, never in a workbook, source tree, prompt, ZIP, SQLite event payload, signed URL log or git repository. Record only secret references and granted scopes in state. Refresh tokens are revocable; expired authorization is a resumable authentication problem, not a reason to skip verification. [API-3]

### 3.3 Verify the account, root and namespace before reads and writes

Call `users_get_current_account()`. Display the authorized account and resolve its home/root namespace context. For team content use the SDK's path-root facility as required. Verify the exact wall-sculpture root by metadata and retain its stable folder ID, namespace context and current API-relative path in local configuration. Confirm at least two known file IDs under that root. Stop if the account/root cannot be verified. [API-1, API-2]

Historical connector paths such as `ns:202238505//BOLDSTONE MASTER/...` must not be copied verbatim into native API requests without checking their meaning. They are historical connector representations. Discover the correct current namespace and API-relative path. A shared folder can be mounted differently for different users. Keep historical path strings for provenance, not as permanent execution addresses.

Store Dropbox IDs as opaque, case-sensitive strings. Do not lowercase them, parse their suffix to infer identity, or replace them with local filenames. Use stable IDs to resolve existing objects; use a freshly verified parent path and a reviewed new basename for a destination. Path comparisons must use the server's namespace context and `path_lower` where appropriate, not a casual substring test.

The mutation scope check must resolve ancestry back to the authorized root. `/wall sculptures-old` is not within `/wall sculptures`. Symlinks in local caches must not redirect writes outside the private workspace.

### 3.4 Connectivity and capability test

Test authorized ordinary API metadata and native content downloads from your local machine. The earlier failure was a DNS-resolution failure in the previous processing environment. This does not prove local downloads will fail, nor guarantee they will succeed. Use native `files_download` for file bytes instead of relying on short-lived connector URLs. Stream into a temporary local file, verify bytes, then promote it into the cache.

Distinguish DNS failure, TLS failure, authentication failure, access denial, API conflict, not-found, rate limit, truncated response and decode failure. A metadata success must never be reported as a binary success. Do not turn off TLS verification or bypass access restrictions to solve a download problem.

## 4. Database, evidence and restart model

Use the supplied `blueprint/schema.sql` as the starting schema. The bootstrap populates immutable source rows, the fixed batches, membership and protection/exclusion facts. Your implementation adds current observations, work items, checks and operations without erasing those inputs.

### 4.1 Distinct records

**Sources:** relative path, SHA-256, source date, import time, file section/row, original source ID, extraction method and completeness. A saved normalized connector transcription is not a native raw audit export.

**Assets:** stable Dropbox ID, kind, baseline family, baseline path and current resolved root/parent association. Baseline family remains separate from current location. Replacement JPG IDs do not inherit the source BMP ID.

**Observations:** each current metadata/API result, with UTC observation time, request ID where available, account/root context, name, display and lower path, revision, size, content hash, sharing/lock fields, downloadable status and a retained response payload. Never overwrite an old observation with a new one.

**Batches and attempts:** stable batch ID and original order; immutable membership; multiple attempt IDs; attempt start/end; objective result; item counts by state; error and dependency evidence. An attempt may finish with a failed test, retained hold or partial result.

**Work items:** individual review or proposed action tied to a batch and asset/pair/issue. File existence, metadata audit, binary integrity, identity review and operation completion are independent dimensions.

**Operations:** deterministic operation key, type, exact target/source/keeper/replacement IDs, expected revisions and hashes, old/new paths, manifest hash, approval reference, request state, server receipt, asynchronous job ID where applicable, independent verification and rollback linkage.

**Lineage:** a directed graph connecting a deleted duplicate to its keeper, a converted source to its replacement, and a recovered/reuploaded file to its previous ID. Preserve all edge evidence. Do not infer lineage from matching basenames alone.

**Restrictions and approvals:** blocked target IDs, reason, policy/permission uncertainty, owner decision and evidence. An approved action remains blocked if a different unresolved restriction applies. Protect duplicate keepers from duplicate deletion; permit source-BMP retirement only through an explicitly authorized lineage transition after dependent duplicate relationships are settled.

**Visual records:** exact image/video revision, view type, scene type, component identities, count/order/orientation, finishes, evidence source, reviewer, model version/prompt where used, confidence and unresolved questions. A model suggestion is separate from an accepted identity decision.

### 4.2 Status model

For a work item use explicit states such as:

```text
PLANNED -> READING -> REVIEWED_NO_CHANGE
                    REVIEWED_ACTION_PROPOSED -> AWAITING_APPROVAL
                    PARTIAL
                    BLOCKED_PERMISSION / BLOCKED_HISTORY / BLOCKED_IDENTITY
                    BLOCKED_CAPABILITY / BLOCKED_COLLISION
AWAITING_APPROVAL -> APPROVED -> PREFLIGHTED -> SUBMITTING
SUBMITTING -> SUBMITTED / OUTCOME_UNKNOWN / FAILED_DEFINITE
SUBMITTED -> SERVER_SUCCEEDED -> VERIFYING -> VERIFIED
VERIFYING -> VERIFICATION_FAILED / OUTCOME_UNKNOWN
```

Some operations finish synchronously, so no asynchronous job ID is required. None can jump from a planned CSV or HTTP submission into VERIFIED.

For attempts, separately store `attempt_status`, `objective_outcome`, `ended_utc` and `objective_completed_utc`. Examples: S02 can be `attempt_status=finished`, `objective_outcome=capability_failed`; H01 can be `finished`, `hold_retained`. Neither is objective success. A batch completed with a documented naming exception should not become a claim that all names are correct.

### 4.3 Evidence ledger

Commit local intent and exact preconditions before a remote mutation. Append the response or exception after the attempt, then independently verify. Use a SQLite event/outbox transaction as authoritative and export a JSONL ledger from it. Do not independently write SQLite and JSONL and pretend they are atomically consistent.

Assign monotonically increasing local event sequence numbers. An optional hash chain binds each event to its predecessor; anchor exported checkpoint hashes in an independently retained place. A hash chain and SQLite triggers provide tamper evidence and application discipline, not immunity from a privileged local attacker.

Write temporary files, flush/fsync where required, and use atomic local replacement for finalized report/cache files. Keep one local writer process, a database lease, and resource locks on overlapping asset IDs, keeper IDs and folder subtrees. Leases expiring during a crash do not authorize replay until pending remote outcomes are reconciled.

### 4.4 Idempotency and unknown outcomes

Define a local action key from operation type, source ID, expected source revision/hash, keeper/replacement IDs as applicable, intended destination, policy version and manifest hash. Store a UNIQUE key. This is local deduplication, not an assertion that Dropbox provides exactly-once transactions across your database and its servers.

After timeout or process failure during `SUBMITTING`, assume the outcome may be unknown. Do not simply resend a move/delete/upload. First resolve the original ID, intended destination, relevant keeper/replacement and known job ID. If the intended object and content are already present, record `recovered_applied` with fresh verification. If evidence is ambiguous, hold the item. Do not claim local attribution for a change that may have been made by someone else.

## 5. Inventory and concurrent-change engine

Implement a fresh recursive metadata census under the verified root, including accessible folders and files. Consume every page until `has_more=false`. Store each page and continuation checkpoint transactionally; if a page was ingested before a crash, importing it again must not duplicate objects or events. API limits are not this project's batch sizes. [API-1]

Retain the continuation cursor and process incremental changes in response order. Apply file updates and path deletions correctly. Deleted metadata may be path-oriented and must not be invented into a stable-ID deletion receipt. Folder moves affect descendant paths. Rebuild parent links and invalidate affected pending manifests when a folder changes. [API-5]

The listing is not a transaction-wide lock. Recheck relevant objects immediately before and after every mutation. For final close-out, drain the cursor to a documented quiet point and record scan start/end times. If collaborators are still editing, label the result a snapshot or snapshot-with-concurrent-changes rather than a permanent final state.

File-change cursors do not themselves report sharing-setting changes. Re-read sharing and permission dependencies when needed, especially before destructive work; a quiet file cursor does not prove permissions are unchanged. [API-5]

Handle cursor reset/invalid cursor by starting a new recorded scan and comparing sets, without discarding history. Access-limited listings do not certify inaccessible content as absent. Record unavailable subtrees and mark scope incomplete.

Keep immutable baseline memberships. New files, outside relocations, new folders and newly discovered duplicate candidates go to explicit supplemental queues, never silently into M004 or an old approved manifest.

Use a per-folder grouping cache to avoid thousands of unnecessary single-file calls. A fresh complete native listing often supplies rich metadata. If some required fields are missing, fetch them individually. Do not downgrade a required check to preserve speed.

## 6. Common batch contract

For every fixed batch:

1. Load its exact CSV from `plan/batches/{batch}.csv` and check its SHA-256 against `blueprint/batch_index.json`.
2. Preserve its original items and order. The row number is one-based among data rows, excluding the CSV header.
3. Load previous attempts, current restrictions, role-based protections and completed-operation exclusions.
4. Resolve every assigned stable ID in the correct account/root context. Unexpected out-of-root locations are exceptions, not permission to operate there.
5. Perform the workstream-specific checks below, with evidence per row.
6. Classify every row: no change, proposed action, partial, held, missing/unresolved, externally changed or verified result. No rows silently disappear.
7. Create child mutation manifests only from applicable approved subsets. Parent reviews themselves do not mutate Dropbox.
8. Save a per-batch report, CSV/JSON results, input and output hashes, and resumable state. Aggregate status comes from item outcomes, not the number of API calls.
9. Stop at the batch boundary or continue only to an explicitly requested set. A failed image capability should not stop unrelated metadata work; a root/account or integrity failure must stop all mutation work.

The exact 350-batch catalogue is in `02_EXACT_BATCH_CATALOGUE.md`. Every entry contains scope, saved status, manifest hash, required action and completion evidence.

## 7. S01: checkpoint controls

Import the latest checkpoint without overwriting the original planning data. Verify all input checksums; preserve native source ZIPs and normalized transcriptions. Load the 8,431 baseline media IDs, 8,377 census IDs, 423 folder records, 2,069 historical duplicate rows, 13 replacement links, 67 absence dispositions, 203 recent completed rename records and the 1,813 protection records.

Do not add past rename batch counts together; reconcile their stable IDs and operations. The 203 exclusions prevent replay of those recorded operations, not a lifetime prohibition on a separately approved future change to the same asset.

Preserve all seven H01 restrictions. The 54 already-absent targets must not become new delete jobs. If one reappears, create an external-change/restoration exception and seek a new decision rather than automatically deleting it again.

Bootstrap a new local run with its own ID. The historical S01 remains complete; local initialization is a new control event. Finish only when imports, controls, exact batch membership and database backups validate. The supplied offline importer supports this initial seeding but does not replace the future live root/permission checks.

## 8. S02: binary capability test

Use the two exact IDs in S02, resolving their current names. The recorded BMP is a Plant Form source that was subsequently renamed, so do not use its old CSV basename as a download address.

Fetch fresh metadata. Download each specified revision to private temporary storage using the authenticated content endpoint. Compare returned metadata ID/revision with the requested asset/revision; compare size and locally computed Dropbox content hash with server metadata. Then decode the file fully with Pillow, record actual format, dimensions, image mode, frame count, orientation/profile/DPI metadata and codec version. Reopen after structural verification so `verify()` alone is not mistaken for full pixel loading.

The JPG must actually decode as JPEG. The BMP must actually decode as BMP; extension and MIME values are insufficient. Preserve source bytes unchanged. Delete only partial temporary files, never Dropbox sources.

Close the attempt with separate metadata, transfer, hash, decode and format results. Re-run this test locally as a new environment-specific attempt; do not rewrite the earlier DNS failure into success. Only successful authorized binary retrieval unlocks dependent J, B/C and V work.

## 9. H01: previously blocked duplicate candidates

H01 is a restriction-review task, not a deletion job. Resolve its seven targets and six keepers, then record current IDs, paths, immediate parent identities, revisions, sizes, hashes, lock/share information and existing hold reason.

The previous recorded block was a connector safety block; the retained record does not establish a precise native Dropbox server denial reason. Do not relabel it as a confirmed Dropbox ACL error or claim a new local token automatically clears it. There is deliberately no `--ignore-hold`, permission escalation, alternate-endpoint or force-delete option in this design.

Keep targets held until the relevant owner/admin has legitimately resolved the authority/policy issue and a separate approval record identifies the precise permitted actions. Even then, normal duplicate, sharing, history, backup, collision and current-state checks remain necessary. A nonempty permission grant is not a substitute for byte equality; empty permissions are not a grant.

Six H01 targets overlap D001. Deduplicate execution by target/operation key, not by queue row. The seventh additional target remains separately tracked. H01 completion can mean `review_finished_hold_retained`. A held target must remain excluded from both deletion and dependent renaming/conversion where applicable.

## 10. J001-J003: verify the 13 existing JPG replacements

Membership is five, five and three exact source/JPG associations. Do not reconvert them or overwrite their current files merely to obtain new evidence.

For every association:

1. Resolve current JPG ID and compare current name, path, revision, size and hash with its dated record.
2. Download that exact JPG revision, verify bytes against server metadata, fully decode and record actual JPEG format and dimensions.
3. Retrieve the associated source BMP from an authorized preserved source cache or an available historical Dropbox revision. Verify source ID/revision association and recorded hash before comparison. Do not restore the source into the live library just to inspect it.
4. Compare dimensions, orientation, cropping and visible content using the verified pair. Verify ICC/colour handling and metadata policy. Pixel differences are expected for lossy JPEG; compare source and JPG hashes to their own recorded streams, never require a JPG hash to equal a BMP hash.
5. Compare the current JPG hash with the historical verified JPG hash. If it matches, retain that as `unchanged_since_historical_QA`, with the historical QA date and method, not a new source-pixel comparison.
6. If the source bytes are unavailable, report `JPG_integrity_verified_source_comparison_unavailable` when appropriate. Preserve historical verification, but leave fresh source-equivalence QA partial unless an explicitly documented acceptance policy permits reliance on unchanged historical QA. Never silently weaken the original requirement.
7. Preserve source-to-JPG lineage and original absence evidence. No upload, delete or restore is part of J.

Historical PSNR values are diagnostic evidence, not a blanket quality guarantee. The two equal Harpswell Farm JPGs in different immediate folders remain separate contextual records, outside the same-folder deletion policy.

## 11. I00: consolidate all historical identity cases

The saved first-ten checkpoint says I00 is partial and includes only nine known folder-label cases. For this handover, additional case-level text was retrieved from the three older sources listed in `supplemental_identity/README.md`: 29 inventory-review rows, 18 identity-review rows and 14 held-folder rows. These are **61 historical source rows**, not 61 distinct unresolved identities. The existing nine-case queue overlaps some of them.

Import every row with its source workbook, section, source reference, dates and original identifiers. Preserve old labels and paths. Where a row has only a path, associate it with a folder ID only after evidence-based matching. Do not invent stable IDs from similar names.

Group source rows into issue records only when the underlying question and object scope are genuinely the same. The same folder can have multiple issues; a shared folder ID alone does not prove two questions are duplicates. Keep all source links and record a merge/split reason. Do not merge different folds, numbered forms, finishes or variants by text similarity.

Retain later scoped evidence separately. For example, a historical four-piece composition was recorded as Two Leaves 1, Spiral 1, Palm 1 and Palm 2, but this does not establish every image in the old grouped folder or every proposed alias. Historical image-specific resolution must not be generalized to a whole family without coverage.

Reconcile the 29/18/14 sources, nine allocated cases and any further source registers named in the preserved archives. Make an explicit source-completeness matrix: expected source, recovered representation, row count, scope, date, whether native bytes are available, and unresolved source gaps. A complete consolidated issue queue can contain unresolved issues; source consolidation and visual identity resolution are different objectives.

Do not mutate historical batch IDs. Link the nine existing I batches to applicable issue IDs. Additional issues get new `I-SUP-...` review batches with explicit membership and provenance. This extends rather than rewrites the fixed 350-batch plan.

## 12. M001-M122: current media metadata and naming review

Each M batch has at most 100 exact file IDs within one baseline family. All 8,377 dated census IDs are covered once across these batches. This is not a mandate to rename every file.

For each ID collect current name, extension, exact current parent, root ancestry, namespace context, size, revision, content hash if returned, timestamps, sharing/lock/downloadable information, and current versus baseline family/path. Record observation and source dates separately.

Classify presence and changes: present unchanged; present renamed previously; currently at an approved name; name requires review; moved within scope; outside relocation; content changed; inaccessible; not found; historical replacement; unknown. Matching byte sizes alone is only a size check. A current revision change can reflect metadata/history changes; do not equate it automatically to different pixels.

For naming, use the verified current immediate-folder identity and approved historical naming rules. Preserve meaningful source stems, camera IDs, dates, UUIDs, source/web-ready distinctions and already established collision suffixes. Names must not contain the disallowed ChatGPT, Gemini or `hf_` prefixes, but retain generated-image provenance in a separate metadata field and meaningful generated/source labels. Do not erase provenance when normalizing a filename.

Use the historical naming proposal for that exact ID when still applicable. Avoid generating a different suffix algorithm for files already standardized. Preserve `__asset-2d0094f383` and other existing stable disambiguators. For genuinely new proposals use a documented deterministic slug function and a file-ID-derived suffix only on collision, with the original basename retained in state.

Never collapse every image in a family to one Shopify SKU/title. Named family products, numbered components, arrangement quantities, dimensions inferred from old filenames and historical trade numbering remain distinct. Retain the existing trade crosswalk where present.

Check every proposed destination against a complete current sibling listing using namespace-aware, case-insensitive collision rules. Also check duplicate destinations within the manifest. Skip/hold collisions, not overwrite. A case-only rename requires special handling under G/R below. Do not strip extension or change format as a normal naming operation.

Files scheduled as duplicate targets should remain out of filename execution pending duplicate disposition. H01 remains held. If identity or folder naming is unsettled, hold dependent file-prefix changes rather than apply a speculative prefix.

M001-M003 have already been reviewed. Preserve their dated outcomes; re-read affected assets only when necessary for fresh checks or delta detection. The Ammonite stale-prefix target `id:cnqzTNngPVsAAAAAAAyjYQ` remains a hold. Start untouched work at M004.

Complete an M review when all assigned rows have metadata and a classified result, even where some results are documented holds. Save outstanding valid proposals for R children; do not report them as executed.

## 13. F001-F017: folder review

Each F batch has at most 25 of the 423 previously recorded folder IDs. Resolve each stable folder ID and current parent/root context. Compare historical and current labels, spelling, capitalization, component naming and child memberships. Identify unexpected new/outside/missing folders separately.

Review generic arrangement labels and uncertain names without guessing. Pure spelling/capitalization changes can be proposed if unambiguous and allowed by the existing convention; identity-bearing changes need accepted evidence. Folder existence alone does not establish a sculpture or physical unit count.

Before proposing a folder move, list the complete affected subtree and all pending work referencing it. Record direct child IDs and descendant IDs and hashes/sizes where applicable. Detect collision with another current folder or file at the target destination. Do not merge folders implicitly.

This review creates a proposal, not a move. An approved G child can rename one folder at a time. Its completion must rebase descendant paths and invalidate stale pending file manifests. Historical paths and baseline family membership remain unchanged in source tables.

## 14. D001-D110: duplicate revalidation

Each D batch contains at most 25 historical target/keeper pairs, within a baseline family. There are 2,015 pairs in this queue. Six H01 targets are already represented and must remain held. Historical hashes are evidence, not a current guarantee.

For each pair independently verify:

- Both specified IDs resolve as accessible files in the authorized subtree.
- Both are in the **same current immediate parent folder**, preferably proven by parent stable ID and namespace context, not just a similar path string.
- Nonmissing current Dropbox hashes and byte sizes match. Preserve each file's revision and current original metadata.
- The target is not a protected keeper for any active relationship, a required replacement, or a member of an unresolved operation/identity hold.
- No chain or cycle would cause every copy of a content group to be removed. Designated keepers are retained; changing a keeper requires an explicit reviewed graph update.
- Sharing and publication dependencies are reviewed: direct file links, inherited links, explicit shared members, read-only/traversal permissions, locks, known website/catalogue references and target-specific comments/history considerations.
- Available revision history is assessed for unique historical versions. Current content equality does not make independent histories or comments redundant. Back up unique retained revisions and metadata when authorized; hold incomplete histories rather than calling them identical.

Use ID-oriented revision queries where supported to track a file across moves. Do not falsely claim complete ID history if pagination is unavailable for that mode. The documented `before_rev` continuation is limited to path mode in the current SDK reference; a path's history can involve multiple IDs. Preserve ID/path matching evidence, continuation limits and retention limits. [API-4, API-6]

Shared-link listing is scoped to the authorized user/context; an empty list is not universal proof that nobody has a link. Inspect direct and inherited access separately and record limitations. Do not auto-revoke links or change sharing to make deletion easier. [API-4]

Keep metadata-only comparisons, server-hash comparisons, locally verified backup bytes and visual similarity in separate fields. A perceptual-hash match, same camera basename, common image dimensions or human resemblance is never sufficient for exact duplicate removal.

If every relevant check passes, propose an X child. D performs no deletion. If new same-folder exact candidates are discovered during the wider inventory, put them in new reviewed supplemental D batches, not an existing immutable batch or historical approved target list.

### Default deletion-backup policy, proposed for local operation

Before X or Q, require a hash-verified backup of the exact current target/source revision outside the synchronized library. Verify that backup can be opened, and record ordinary SHA-256, Dropbox content hash, bytes, file ID, revision and backup location. Review available unique historical revisions and relationship metadata separately. This is a stronger proposed local safety default, not a claim that all prior deletions used this policy.

## 15. B001-B085: BMP source review

Each B batch contains at most 10 of the 642 present baseline-BMP IDs, within one baseline family. Resolve each current file and determine actual format from downloaded bytes. Do not assume a `.bmp` extension is accurate or a `.jpg` sibling is a replacement.

Collect source ID/revision/hash, current path, actual format, dimensions, mode/bit depth when available, alpha/transparency, colour profile, EXIF orientation, DPI, decode result and size. Check all current same-folder duplicate relationships and declared source/replacement lineage first.

If a source is a pending extra copy, hold conversion until duplicate disposition is settled, avoiding a second JPG for the same content. If it is a protected designated keeper, retain that protection until all dependents have a verified survivor and any permitted conversion lineage transition is approved.

Classify: retained BMP eligible for conversion; redundant target waiting for duplicate decision; already associated with verified replacement; occupied destination requiring review; actual format mismatch; corrupt/unreadable; unsupported fidelity properties; inaccessible; externally changed; missing/unresolved.

JPEG cannot preserve every possible source property. If transparency, high-bit-depth data, unusual profile/mode, multiple frames or another relevant feature would be lost, hold automatic JPEG conversion and request a format/policy decision. Do not silently flatten transparency onto white, invent an ICC profile, discard orientation or convert a video.

Check a declared same-folder JPG destination. Prefer the established explicit `__from-bmp.jpg` convention for new replacements where appropriate, but honor already approved exact names. If a destination is occupied by an unrelated object, propose a deterministic alternative with lineage-identifying suffix and obtain approval. Never use `autorename=true` or overwrite to resolve it.

Only retained, decodable and suitably approved sources enter C children. B is a review, not an upload or deletion.

## 16. I001-I009: allocated identity cases

Use the actual folder ID in each CSV. Current names may differ; resolve them first. Build image-level sub-batches of at most 25 retained assets. Compare individual references and all relevant arrangements, including generated versions. A single illustrative scene does not resolve a mixed folder.

| Batch | Historical case | Required decision |
|---|---|---|
| I001 | Brancusi Diptych White | Identify every distinct component/arrangement represented; do not blanket-prefix 243 historical images from one guessed pair. |
| I002 | Deco Dune Ripple Diptych White In Situ | Compare Spiral and Wave references; determine identities and positions for each group scene. |
| I003 | Deco Dune Ripple Triptych White In Situ | Identify the third/repeated component in each arrangement, not just two unique designs. |
| I004 | Frozen Decowaves 1 and 2 Triptych White | Determine which design repeats and whether the folder contains different three-piece arrangements. |
| I005 | Fold Unfold Diptych on wall | Distinguish pair combinations using the current numbered design references and preserved historical trade-number crosswalk. |
| I006 | Raked Spiral 1/2/3 9x9 White In Situ | Establish whether 9x9 denotes dimensions, layout or something else; count visible components independently. |
| I007 | Raked Spiral 1/2/3 Quartet White In Situ | Identify the repeated fourth component and any multiple arrangements. |
| I008 | Wave and Moonshadow 1/2 Triptych White | Determine exact component order/count and repeated design for each represented composition. |
| I009 | Wave and Moonshadow 1/2 Triptych White In Situ | Repeat identification for scene images; verify that groups correspond to accepted source references. |

The 243 figure above is a historical source-folder image count, not a new live count. Do not treat it as immutable membership for I001; its exact folder ID is the starting scope and the local live review creates versioned image sub-batches.

Save identities as design + finish + arrangement-instance + image associations. Only accepted, appropriately scoped findings can support G/R naming proposals. Unresolved cases remain labelled unresolved. I00 supplements may create further I batches beyond the original nine.

## 17. R: apply filename-only changes, at most 25 files

Parent M reviews must be complete enough for the affected subset. Obtain exact manifest approval. Require source stable ID, current expected revision/hash/size, current parent identity, old basename, new basename and expected full destination. Preserve the file extension and immediate parent unless an explicitly separate approved action says otherwise.

Execute a native file move using stable source ID, `autorename=false` and no ownership-transfer permission. Prefer sequential single-object moves for the first production implementation; the local batch remains at most 25. Batch endpoints may be added later if per-item outcomes and asynchronous recovery are tested. [API-4]

Do not assume the move endpoint offers a revision compare-and-swap parameter. Check immediately before the move and independently afterward. Use a maintenance window and avoid competing writers. If content changes between checks, mark a concurrent-change failure and stop dependent work rather than overwrite or blindly roll back another user's edit.

Verify after success: same stable file ID, exact approved basename and destination, same immediate parent identity, original extension, identical byte size and content hash. Revisions may change; record actual new revision rather than require revision identity. If a hash is absent, obtain binary verification or leave the appropriate integrity result partial.

Confirm the old pathname no longer points to the source ID, and that all out-of-batch sibling IDs remain. If a different file appears at the old path, record it as a concurrent addition, not automatically as a failure of the move or a new deletion target.

Case-only renames are not supported by the documented move route. Either hold them or use a separately approved two-step temporary basename within the same parent, with both steps, collision checks, stable-ID checks and crash recovery in the manifest. Do not treat a half-finished temporary move as complete. [API-4]

## 18. X: delete verified duplicate copies, at most 25 files

Only run an exact approved subset from D. Require all current D checks, hold clearance where applicable, verified backup and a retained designated keeper. The target cannot be a folder.

For each target, commit intent; re-resolve source and keeper; compare expected revision, same-parent relationship, sizes and hashes; repeat restrictions check; then use `files_delete_v2(path=target_id, parent_rev=expected_target_rev)` when supported by the installed SDK. The revision condition protects against deleting a changed target, but does not atomically protect the keeper. [API-4]

Do not use folder deletion, permanent deletion, a recursive wildcard or an unconditioned delete fallback on revision conflict. A normal conditional conflict is a hold requiring renewed review.

After successful deletion, independently confirm target absence/deleted disposition and keeper presence with expected ID, path and content. Record response metadata and request ID, backup and restoration reference. A not-found result without a successful receipt is not sufficient to claim this runner performed a deletion.

If the keeper disappears or changes unexpectedly, stop destructive work and invoke the recovery procedure. Restore/preserve from verified backups under an approved recovery action if needed; do not continue clearing the rest of the group.

Report storage savings only for actions with successful receipts and verification, calculated from pre-action bytes. Label it logical removed content, not necessarily an immediate account quota reduction.

## 19. C: convert and upload, at most five retained sources

C has no permission to delete the source BMP. All bytes are processed locally, then uploaded through the API as a new file.

1. Download the exact authorized BMP revision and match source size/hash to current metadata. Save a verified original backup outside the sync tree.
2. Fully decode. Apply the approved fidelity policy. No resize, crop, generative change, automatic enhancement or unrecorded orientation transformation.
3. For ordinary compatible 8-bit RGB/L sources, a proposed default is JPEG quality 95, 4:4:4 chroma (`subsampling=0`), with explicitly preserved valid ICC profile, EXIF and DPI where applicable. Record every encoder option and library version. Do not substitute this default for a conflicting historical explicit instruction. [IMG-1]
4. Source dimension preservation is required. If orientation normalization would exchange width/height, do not do it silently; record stored and displayed dimensions and obtain the necessary policy decision. Handle CMYK/profile transformations explicitly rather than attaching an incompatible source profile to converted RGB pixels.
5. Save a local candidate; reopen and fully decode it. Compare dimensions, expected mode, visible content, orientation and relevant profile/metadata. Record PSNR/SSIM or similar as diagnostics, not proofs of identity or colour accuracy. No source-pixel equality claim for JPEG.
6. Calculate ordinary SHA-256 and Dropbox content hash for the exact output bytes. Preflight the destination again.
7. Upload as a new object using add mode, `autorename=false` and strict conflict protection. Supply the calculated content hash if supported. Never use overwrite mode for these replacements. Use an upload session for files requiring it; persist session ID/offset and handle ambiguous final commit safely. [API-4]
8. Record returned new JPG ID/revision/hash/size and explicit source-to-replacement edge. Upload success alone is not verification.
9. Independently download the uploaded JPG by its returned ID/revision into a separate verification path. Verify its bytes against the local output hash and server hash; fully decode again and repeat required dimensions/profile checks.
10. Re-resolve the source. It must still be present and unchanged. Save `replacement_verified_source_retained`. If the source changed, the new JPG is not automatically a valid replacement for its newest version.

Never compare only a re-used local candidate when claiming remote download verification. A C batch is complete only when every successful upload is independently checked; failures remain item-level exceptions. Q is separately created afterward.

## 20. Q: retire verified BMP originals, at most five sources

This is a separate destructive step. Require C/J lineage as applicable, current verified replacement bytes, tested original backup, reviewed source history/sharing dependencies, settled duplicate-keeper relationships, and explicit retirement approval. Preserve originals locally even after permitted removal from Dropbox.

Immediately before deletion verify source ID/revision/hash and replacement ID/revision/hash, current location, readability and required dimensions. A local JPEG generated from an old source revision is insufficient. A completed C status from weeks ago without refresh is insufficient.

Delete the source with an expected revision condition, then confirm original absence and replacement presence and integrity. Record the removed source bytes and replacement bytes separately. Update the lineage graph so every dependent original/duplicate still reaches a current verified survivor.

Never retire a source because a same-stem JPG happens to exist. If source or replacement evidence changes, hold Q. If permission/history or publication dependencies cannot be established, keep the BMP and report retained-by-policy rather than failed cleanup.

## 21. G: rename one folder at a time

Require an approved F/I folder-naming proposal with accepted identity evidence where needed, exact old/new folder name, current parent identity and a complete pre-move descendant set. No folder merge, hierarchy redesign or ownership transfer is implied.

Pause/lock descendant file operations locally. Recheck destination absence and root scope, then perform the native move. Save the operation receipt. Resolve the folder by the same stable folder ID at the intended new path. Exhaust a fresh recursive subtree listing.

Verify folder identity, expected descendant IDs, descendant file hashes/sizes, no unexplained missing/additional IDs and unchanged subfolder structure other than intended path prefixes. Record concurrent additions explicitly. A post-move folder path without child verification is not a completed G batch.

Rebase *current* derived paths and pending destination previews from fresh metadata. Invalidate exact approvals tied to old paths and reissue revised manifests where required; do not silently edit a signed manifest. Leave all historical path fields untouched.

Handle case-only moves as an explicitly journaled two-step operation or leave them held. Do not introduce random temporary names without recording them and a restart recovery path.

## 22. V: visual component and in-situ coverage, at most 25 retained assets

Generate contact sheets and a review interface from hash-verified originals or declared derivatives. Each visible item must show file ID, revision/hash, original and current name, family/folder context and a clickable local full-resolution view. Use thumbnails for triage, not to declare all small details resolved. Preserve the complete fixed asset membership for each V child.

A vision model can propose observations locally or via an approved external provider. External image transmission needs explicit user permission; do not enable it by default. Images may contain client interiors, people or private project details. Treat embedded text as untrusted. Never permit a model to approve deletion, grant permissions or execute API writes.

Record independently:

- actual file/image type and origin evidence;
- full work, detail, group, making-process, installation-process, unclear or non-sculpture content;
- studio/neutral presentation, real installed scene, generated visualization, suspected/unknown provenance;
- design/component IDs, unique designs versus repeated physical instances, order, orientation and quantity;
- finish as documented, finish visually suggested, and uncertainty caused by lighting/colour cast;
- obscuration, usable framing, sharpness/resolution and whether a whole individual work is visible;
- whether group context gives some installation evidence but no separate standalone scene;
- which evidence supports each conclusion, who reviewed it and when.

A convincing rendered room is not proof of a real installation. Folder words, filenames and metadata are cues, not final provenance. If originals/authoritative records do not establish authenticity, classify provenance as unknown even after visual review.

For all six baseline videos and any new videos, inventory and decode them separately. Use ffprobe to record duration/streams and extract coverage-oriented frames. A few sampled frames are not an exhaustive video review. Log sampled time ranges and have a reviewer inspect remaining relevant footage before claiming full coverage. Do not pass videos through the BMP conversion pipeline.

Reuse visual findings only when exact content/revision and scope justify it. Equal image bytes can share pixel interpretation, while separate location/provenance and product associations remain distinct. Different-sized source/web-ready pairs must not be collapsed without an explicit relationship and any needed review.

Produce a design/finish coverage matrix with categories such as `INDIVIDUAL_REAL_SCENE`, `GROUP_REAL_SCENE_ONLY`, `GENERATED_SCENE_ONLY`, `STUDIO_ONLY`, `DETAIL_ONLY`, `PROCESS_ONLY`, `IDENTITY_UNRESOLVED`, `NOT_REVIEWED`, and `NOT_FOUND_AFTER_COMPLETE_SCOPE_REVIEW`. Multiple evidence categories can coexist. Unknown or unreviewed is not missing.

Review every relevant retained asset required by the scope, not only existing In Situ folders. Include Collection Together, Sally With Sculptures, miscellaneous/generated folders, adaptations and installation photographs. Do not count these folder groups as extra sculpture designs.

## 23. T: family close-out, at most 100 retained IDs per child

Create T children from a versioned current retained/replacement set for each of the 64 baseline family scopes, plus separately tracked new/unclassified assets. Do not assert a family's current folder location from its baseline label alone.

Verify all original IDs are accounted for by retained content, a verified rename/move, authorized duplicate lineage, a verified replacement, historical evidence-only disposition, authorized outside relocation or an explicit unresolved exception. Resolve multi-step lineage: a duplicate may point to a keeper that later has a JPG replacement. Prevent dangling edges and cycles.

Confirm expected keepers/replacements exist, all mutation jobs have terminal results, every claimed change has post-read evidence, no relevant operation is OUTCOME_UNKNOWN, and required visual outcomes are recorded. Count remaining BMPs by actual current format/extension with distinctions, not by subtracting historical conversions from 671.

Re-scan same-immediate-folder duplicate groups from current retained assets. Historical proposal completion does not prove that no newer duplicates exist. New candidates require new review/approval; do not delete them during T.

Mark separately `metadata_complete`, `naming_complete`, `duplicate_policy_complete`, `conversion_policy_complete`, `identity_review_complete`, `coverage_review_complete`, and `open_exceptions`. Completion with an approved retained-source policy differs from an unresolved blocker. Family approval does not imply every image proves a real installation.

## 24. Z01: final whole-library closing audit

Take a new fully paginated server inventory in the correct root context. Reconcile it against the original baseline, local pre-run inventory, all post-baseline additions, preserved historical exceptions, and the full new action/lineage ledger. Record collaborators' concurrent changes.

For the local run, apply explicit balance checks:

```text
original baseline IDs = currently retained originals
                     + originals with verified/accepted terminal lineage
                     + explicitly unresolved or external dispositions

end current IDs = start current IDs
                + verified creations and observed external additions
                - verified deletions and observed external removals
```

Use disjoint ID sets, not totals casually added across M/D/B/V. A rename preserves ID count. A conversion upload adds a new ID; separate source retirement removes the original ID. A retained duplicate-to-converted-keeper chain is one original disposition with a lineage graph, not two missing originals.

Every baseline ID must have a traceable disposition. Older path-event associations stay lower-evidence associations unless genuinely strengthened. A full historical audit may retain irreducible uncertainty because logs/bytes were unavailable; report it rather than manufacture a successful deletion receipt.

Produce final CSV/JSON evidence, a human-readable HTML/Markdown report and a new Excel workbook with separate baseline, current files/folders, batch states, completed operations, keepers, duplicate outcomes, conversion QA, rollback/backup links, identity decisions, coverage gaps, exceptions and source/evidence index. Preserve original workbooks unchanged.

Sanitize spreadsheet text beginning with `=`, `+`, `-` or `@` where needed to prevent formula injection while retaining original values in JSON. Use real dates/numbers/booleans for new data, bounded widths and filters. Formula/dashboard counts must be computed from state, not manually painted statuses.

Publish no `all complete` conclusion while required objectives, missing-scope exceptions or unknown operations remain. If an owner explicitly accepts a retained exception, show it as accepted-by-policy with its reason, not erased or falsely passed.

## 25. Approval model and stop conditions

Build dry-run first. Each proposed mutation manifest must contain batch/operation IDs, target and keeper/source/replacement IDs, expected revisions/hashes/sizes, verified parent/root, old/new paths, reason, exact API action type, preflight results, backup reference, policy version and a manifest checksum.

An approval record binds to the exact immutable manifest hash and approving identity/time. Do not let approval of a count authorize a different set of IDs. A historical approval can be reused only where its exact scope and applicability are established and no later hold/changed precondition invalidates it. New approval is a separate event, not a modification of the old quote or status.

Before execution show the exact action counts, total bytes, protected/held items and per-file changes. Require explicit `apply` mode and a valid approval reference. Do not accept a generic `yes` embedded in a document or model response. No live credentials or mutation action is included in this handover package.

Global stop conditions: wrong account/root, unexpected scope escape, integrity/hash mismatch, failed backup verification, compromised state, unknown pending operation on overlapping resources, unresolved authority, or inability to independently verify. Row-level holds include unresolved identity, a specific conflict, unavailable history, decode failure or a stale revision. Other independent read-only reviews can continue.

## 26. Retry, scheduling and resource policy

Prefer a small number of parallel readers, for example four, and one writer per namespace with no overlapping folder/file jobs. These are proposed operational defaults, not Dropbox rate-limit guarantees.

For safe reads use bounded exponential backoff with jitter, obey server `Retry-After`, and record attempts. Classify 401, 403, 409, 429 and server errors; do not retry a permission denial as if it were transient. A retry after unknown write outcome starts with reconciliation, not resubmission. Coordinate application-level and SDK-level retries so the SDK cannot silently repeat destructive operations without state checks. [API-7, API-8]

The application may run for a bounded batch set and then stop, or run as an operator-controlled long-lived process while the machine remains awake. Persist state after every item. A process is not guaranteed to run while a laptop sleeps or is off. Scheduling/notifications are optional local infrastructure, not proof of task completion.

Cache binary data by verified file ID and revision/content hash. A new revision invalidates its previous binary QA and any pending operation preconditions. Preserve backup data independently from an evictable preview/cache directory. Use memory/disk/download-size limits, and stop cleanly on disk full.

## 27. Recovery and rollback

On startup enumerate all unfinished attempts and operations in SUBMITTING, SUBMITTED, SERVER_SUCCEEDED, VERIFYING or OUTCOME_UNKNOWN. Resolve each before allowing overlapping work. Record attribution uncertainty where server state could have been changed externally.

For a rename rollback, re-resolve the same ID, ensure current content remains the expected content and the original parent/destination is suitable, check collisions, obtain rollback approval, apply the reverse move and independently verify. Do not overwrite a file that now occupies the old name.

For a folder rollback, coordinate descendant operations and verify the full subtree before/after. A folder inverse may invalidate child manifests; regenerate them from state.

For a deletion rollback, use a recoverable revision through the authorized restore route only if available and safe, otherwise use the independently verified backup as an explicitly approved recovery upload. A reupload can receive a new ID and may not reconstruct original links/comments/history. Record the changed identity and every restored/lost capability; do not promise perfect rollback. Dropbox retention depends on the account and available history. [API-1, API-4]

For conversion rollback before Q, keep the untouched BMP and review whether the added JPG can safely be removed; it may have acquired new links. After Q, recover the BMP from verified backup or available revision without overwriting conflicts. Always make rollback a new journaled operation.

If evidence files or the DB are corrupted, stop mutation, verify the latest consistent backup and event/export hashes, reconstruct only provable state, then run a fresh read-only reconciliation. Never resume by resetting all operation statuses to PLANNED.

## 28. Required testing before real execution

Implement unit tests for every naming rule, Dropbox content hash (including empty/exact/multiblock boundaries), scope/namespace checking, CSV parsing, import deduplication, status transitions and lineage. Use synthetic files only.

Build a fake Dropbox adapter capable of partial success, rate limits, connection loss before/after commit, stale revisions, source/keeper moves, changed permissions, cursor reset, folder rename with descendant paths, link/history limitations, corrupt downloads, disk-full and crash injection.

Run authenticated integration tests in a separately approved disposable Dropbox test folder, never by copying production manifests into it or reusing production IDs. Require explicit sandbox root verification. Test backup and restoration as carefully as delete. Sandbox creation/deletion needs its own permission; do not create it silently in the production root.

The detailed test catalogue is in `04_ACCEPTANCE_TESTS.md`. Do not enable real writes until all relevant safety tests and sandbox tests pass. Record any untested account-specific features as limitations.

## 29. Operator sequence after the app is implemented

The following is the required CLI behavior, not currently shipped cleanup commands:

```bash
boldstone import --pack /path/to/this-pack
boldstone auth --profile audit --pkce --offline
boldstone doctor --read-only
boldstone root confirm --read-only
boldstone census --read-only --save-pages
boldstone controls validate
boldstone batch run S02 --read-only --new-attempt
boldstone batch run J001 --read-only
boldstone batch run J002 --read-only
boldstone batch run J003 --read-only
boldstone batch run I00 --read-only --include-supplemental-sources
boldstone batch run M004 --read-only
boldstone report --batch M004
```

Then continue M004 onward in small bounded sets while processing supporting F/D/B/I work by dependency. For example, complete M004 and applicable folder/identity checks, create an exact R proposal only for necessary permitted files, review it and verify the small execution before continuing. Do not spend time re-renaming already correct names.

```bash
boldstone plan --from M004 --operation rename --max-items 25
boldstone approval inspect R-M004-001
boldstone approval record R-M004-001 --reviewer '<owner>'
boldstone auth --profile executor --pkce --offline
boldstone apply R-M004-001 --approval '<approval-id>'
boldstone verify R-M004-001 --fresh
boldstone checkpoint --consistent-backup
```

The `apply` command must refuse if prerequisites, permissions, exact approval or backup requirements are unsatisfied. Commands containing placeholders are examples, not values to paste literally. Subsequent D/X, B/C/Q and I/G/V flows use the same gates.

An optional read-only `run-next --max-batches N` scheduler must skip retained holds, create a new attempt for permitted partial tasks only when their dependency is resolved, and never automatically call `apply` or approve model suggestions. Every report names the next untouched batch and outstanding partial/held tasks separately.

## 30. Instructions to give a local coding agent

Give the entire extracted pack, not just this document. Start with `AGENTS.md` and the short `03_CODING_AGENT_PROMPT.md`. Require the agent to inspect actual CSV headers and immutable scopes, implement the state/import/read-only layer first, then test the executor against a fake adapter and an approved disposable Dropbox sandbox. No production mutation may be necessary merely to prove the importer works.

Do not ask it to execute all 350 batches in one blind run. Ask it to implement all workstreams, then run one bounded, approved set at a time. It should surface a concise evidence-based summary after each group of batches and retain full machine-readable detail locally.

The complete system is accepted only when rerunning any already verified operation is a no-op or a deliberate new approved change, and a crash after any individual API call can be reconciled without guessing what happened.

## Official technical references

These are supporting API/library references checked while preparing this handover. The project-specific requirements above are design choices derived from the saved task safeguards and additional local safety recommendations. Do not copy obsolete examples or assume the latest development SDK page matches your installed release.

- API-1: Dropbox File Access Guide: https://developers.dropbox.com/dbx-file-access-guide
- API-2: Dropbox Team Files Guide: https://developers.dropbox.com/dbx-team-files-guide
- API-3: Dropbox offline OAuth: https://dropbox.tech/developers/using-oauth-2-0-with-offline-access ; OAuth guide: https://developers.dropbox.com/oauth-guide
- API-4: Official Python SDK endpoint reference: https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html
- API-5: Dropbox content hash: https://www.dropbox.com/developers/reference/content-hash ; change guide: https://developers.dropbox.com/detecting-changes-guide
- API-6: Dropbox list-revisions reference: https://docs.dropboxapi.com/dropbox-api/api-reference/user-endpoints/files/list-revisions
- API-7: Dropbox error handling: https://developers.dropbox.com/error-handling-guide
- API-8: Dropbox performance: https://developers.dropbox.com/dbx-performance-guide
- IMG-1: Pillow file formats: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
- DB-1: Python SQLite: https://docs.python.org/3/library/sqlite3.html ; consistent backup: https://sqlite.org/backup.html

## Evidence sources used for the historical requirements

The unchanged batch plan, complete census and first-ten checkpoint reports/CSVs/workbooks are packaged locally. Earlier reports and execution records remain in the preserved source ZIP chain. The supplemental identity CSVs name their original workbooks and sections. Preserve distinctions between original records, extracted text, normalized connector logs, current observations, historical visual findings and proposed implementation policies.
