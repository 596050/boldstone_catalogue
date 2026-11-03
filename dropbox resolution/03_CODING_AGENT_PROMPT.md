# Copy this prompt into your local coding agent

Implement a production-safe local Python application for the Boldstone Dropbox wall-sculpture cleanup using this extracted handover pack as the authoritative historical input and implementation specification.

Read `AGENTS.md`, `instructions/01_LOCAL_IMPLEMENTATION_RUNBOOK.md`, `instructions/02_EXACT_BATCH_CATALOGUE.md`, `blueprint/schema.sql`, `blueprint/config.example.json` and `blueprint/CLI_CONTRACT.md`. Inspect actual CSV headers and exact memberships in `plan/batches/`. Preserve all historical checkpoint records in `checkpoint/` and `source_archives/` without modifying them.

Implement the complete workflow: authorized Dropbox OAuth and correct namespace/root discovery; fully paginated current inventory and incremental change tracking; immutable source imports; SQLite state and append-only evidence; every S/H/J/I/M/F/D/B review; exact immutable manifests and approvals; bounded R/X/C/Q/G actions; independent fresh verification; original-file backups; restart reconciliation for unknown outcomes; conflict-safe rollback; image/video identity and in-situ review; family T checks and final Z01 audit; machine-readable and human-readable reports.

Do not execute production writes while building. Default to a read-only profile. Use a fake API adapter and then an explicitly approved disposable Dropbox sandbox for integration tests. No elevated permissions, ownership transfer, unlocking, sharing changes or alternate routes to bypass a hold. The seven H01 targets remain blocked until normal owner/admin authority is explicitly resolved. No `force`, `ignore-hold`, recursive folder delete, or permanent-delete option.

Preserve the 350 fixed batch scopes and their historical statuses. Do not replay the 203 recorded completed renames or 54 historical already-absent duplicate deletions. Preserve the 1,813 keeper/replacement protections and 67 original absence dispositions. The next untouched fixed metadata batch is M004. S02 needs a new local capability attempt; J001-J003 require actual JPEG retrieval and QA; I00 needs source consolidation. Supplemental identity files now contain 29 inventory-review rows, 18 identity-review rows and 14 historical held-folder rows. Import all as overlapping historical source evidence, not 61 distinct unresolved identities or new visual decisions.

Use stable Dropbox IDs, revision-aware delete preconditions, current same-immediate-parent checks, exact content hashes and verified backups. Do not count an API submission as completion. Every mutation must have independent post-read verification, and uploaded JPGs must be independently re-downloaded and decoded. Never remove source BMPs inside a conversion/upload batch; Q retirement is separately approved and verified.

Treat semantic identity and installation provenance as evidence-based review. Model suggestions must be separate from human/authoritative acceptance. Do not transmit private images externally without permission. Do not infer extra designs from camera names, generated variants, detail images, group quantities or similar family names.

Build and demonstrate the read-only importer/auditor first. Add the executor only after the transaction/recovery and acceptance tests pass. Return a working repository, pinned tested dependencies, documented setup, fake/sandbox test results, and exact commands for bounded operation. Report limitations and missing evidence precisely, without silently weakening completion requirements.

Start by running `python3 bootstrap.py verify`, `python3 bootstrap.py list --limit 10`, and the supplied offline tests. These supplied utilities are not the live cleanup application; implement the live application described above.
