# Boldstone local implementation handover

**Purpose:** build and operate a resumable local application against the user's authorized Dropbox library, with audits, exact small-batch actions, independent verification, state tracking and recovery.

**This package contains instructions and historical inputs, not a finished live Dropbox cleanup application.** The shipped `bootstrap.py` is a working offline package verifier and historical-state importer. It never contacts Dropbox. The native Dropbox runner and all its mutation commands must be implemented and tested by your local coding agent.

## Start here

Read `instructions/01_LOCAL_IMPLEMENTATION_RUNBOOK.md` for the complete specification. Give your coding agent the entire folder and `AGENTS.md`; the copy-ready prompt is `instructions/03_CODING_AGENT_PROMPT.md`.

Run these safe local commands after unpacking outside your Dropbox synchronized folder:

```bash
python3 bootstrap.py verify
python3 bootstrap.py list --limit 10
python3 bootstrap.py show M004
python3 -m unittest discover -s tests -v
python3 bootstrap.py init --db /absolute/non-synced/path/boldstone-state.sqlite3
```

Use `py -3` on Windows if needed. Python 3.11 or newer is the intended baseline for these supplied standard-library utilities. `init` creates a new DB only and refuses to replace an existing one. If an import fails, inspect the retained failed database before selecting a new destination. The resulting state is historical, not a new live audit.

## Contents

| Path | Use |
|---|---|
| `instructions/01_LOCAL_IMPLEMENTATION_RUNBOOK.md` | Complete procedures, architecture, all workstreams, API/verification requirements, approvals, rollback and operator sequence. |
| `instructions/02_EXACT_BATCH_CATALOGUE.md` | Every one of the 350 fixed batches, in original order, with exact scope hash, saved status, gates and completion evidence. |
| `instructions/03_CODING_AGENT_PROMPT.md` | Copy-ready local implementation brief. |
| `instructions/04_ACCEPTANCE_TESTS.md` | Required tests for the future full application, clearly separate from executed bootstrap tests. |
| `blueprint/schema.sql` | SQLite schema for source evidence, batches, observations, approvals, operations, lineage, visual decisions, backups and events. |
| `blueprint/config.example.json` | Proposed fail-closed configuration with no credentials and no enabled writes. |
| `blueprint/CLI_CONTRACT.md` | Commands the local agent must implement; not shipped live commands. |
| `blueprint/batch_index.json` | Machine-readable index of all exact fixed scopes. |
| `blueprint/dropbox_hash.py` | Working standard-library Dropbox content-hash helper. |
| `plan/batches/` | All 350 original scope CSVs, unchanged. |
| `plan/source_registers/` | Baseline/census/duplicate/folder/JPG-association source registers. |
| `checkpoint/` | Latest first-ten results, controls and historical evidence, unchanged. |
| `source_archives/` | Byte-identical original first-ten checkpoint ZIP and complete census ZIP; the latter retains the nested prior execution history. |
| `supplemental_identity/` | Recovered normalized historical case rows: 29 + 18 + 14, not a distinct unresolved-case count. |
| `tests/` and `OFFLINE_TEST_RESULTS.txt` | Executable offline tests and their observed results; no live Dropbox tests. |
| `PACKAGE_SHA256.json` | Integrity manifest for this handover, not a digital signature or proof of current server content. |

## Where work resumes

The next untouched fixed batch is **M004**. Keep S02's previous failed attempt; create a new local capability attempt. J001-J003 and I00 are partial in the saved checkpoint. H01 remains held. Do not replay the 203 recorded completed renames or 54 historical duplicate deletions already absent. Preserve the 1,813 role-based keeper/replacement protections and all 67 original absence dispositions.

The historical I00 checkpoint reported incomplete source recovery. This handover additionally supplies normalized extracts from 29 inventory-review rows, 18 identity-review rows and 14 held-folder rows. They overlap the nine known label cases and sometimes each other. They add source material for the local consolidation; they do not revise that saved status, establish current unresolved counts or represent new visual findings.

## Automation boundary

Code can do the file operations, integrity checks, comparisons, journaling, reports and review orchestration. Ambiguous design identity, source provenance, publication dependency and owner/administrator authority still need real evidence and accepted decisions. No program can truthfully certify unavailable history or missing source bytes. Keep unresolved questions as explicit exceptions.

No Dropbox files were changed in preparing this handover. Source ZIPs and CSV scopes were preserved rather than rewritten.
