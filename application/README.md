# Boldstone local auditor

This is the working **read-only milestone**, version 0.1.0, for the preserved handover in `../dropbox resolution/`. It imports historical evidence, checks controls, authenticates an audit profile, confirms the account/root, inventories Dropbox, audits fixed batches and saves reports/checkpoints. It has no Dropbox content-write commands.

The application is installed in `.venv/` using Python 3.13. Dependencies are pinned in `uv.lock` and in the hash-locked `requirements.lock`. macOS Keychain is the only supported credential backend in this release. The original handover remains unchanged.

## Current local setup

Configuration: `/Users/tprice/Library/Application Support/BoldstoneLocal/config.json`.

Historical database: `/Users/tprice/Library/Application Support/BoldstoneLocal/state/boldstone-state.sqlite3`.

Evidence, cache, local checkpoints, previews, approvals and reports have separate directories under that application-data folder. Local checkpoints are on the same computer; they are not independently verified original-image backups.

From this repository:

```sh
./.venv/bin/boldstone doctor --read-only --offline
./.venv/bin/boldstone controls validate
./.venv/bin/boldstone batch list --limit 12
./.venv/bin/boldstone batch show M004
./.venv/bin/boldstone holds show
./.venv/bin/boldstone report --all
./.venv/bin/boldstone checkpoint --consistent-backup
```

The next untouched fixed batch is **M004**, with 100 Ammonite IDs. Historical S02 remains a failed capability test; J001–J003 and I00 remain partial; H01 retains all seven holds. New local attempts never replace those saved results.

## Connect the read-only account

Create or identify a scoped Dropbox API app with **Full Dropbox** content access to the existing library. Enable only `account_info.read`, `files.metadata.read`, `files.content.read` and `sharing.read` for this audit profile. No app secret is needed for this PKCE client.

Run this interactively in your own terminal, replacing `PUBLIC_APP_KEY` with the app's public key:

```sh
./.venv/bin/boldstone auth --profile audit --pkce --offline --app-key PUBLIC_APP_KEY
./.venv/bin/boldstone root discover --read-only
```

Authorization opens Dropbox in a browser. Paste its authorization code into the hidden terminal prompt. Tokens are saved only in macOS Keychain. Do not send authorization codes, refresh tokens or secrets through chat.

Discovery displays the actual account, native home/root namespaces and candidate wall-sculpture folder metadata. It does not confirm a scope automatically. Use those current values to confirm the exact root and two known file IDs:

```sh
./.venv/bin/boldstone root confirm --read-only \
  --account-id ACCOUNT_ID --namespace-id NAMESPACE_ID --root-id ROOT_FOLDER_ID \
  --known-file-id KNOWN_FILE_ID_1 --known-file-id KNOWN_FILE_ID_2
```

The command requires you to type the exact root folder ID shown. The two S02 file IDs in the handover are potential sentinels; both must actually resolve under the chosen root. Historical `ns:...//...` connector paths are rejected as native API references.

```sh
./.venv/bin/boldstone doctor --read-only
./.venv/bin/boldstone census --read-only --save-pages
./.venv/bin/boldstone batch run M004 --read-only
./.venv/bin/boldstone batch run S02 --read-only --new-attempt
```

After S02 succeeds in this confirmed account/root, the J and B binary-dependent reviews are available. These commands perform fresh downloads, size/hash checks, full structural/pixel decoding and independent metadata rereads. A successful JPG check does not certify equivalence to its historical BMP.

```sh
./.venv/bin/boldstone batch run J001 --read-only --new-attempt
./.venv/bin/boldstone changes poll --once
./.venv/bin/boldstone checkpoint --consistent-backup
```

Use `census --resume SCAN_ID` with the other census flags, or `changes poll --once --resume SCAN_ID`, after an incomplete scan. Durable page commits prevent duplicate ingestion. A new scan is refused while an earlier scan needs resuming. A reset cursor can trigger a recorded fresh scan with `changes poll --once --rescan-on-reset`. Cursors cover file changes, not all sharing-setting changes.

Native metadata and content connectivity remain **untested until authorization and live commands succeed**. DNS, TLS, scope, permission and integrity errors stay separate. Development dependency installation does not establish Dropbox connectivity.

## What this version does

| Area | Implemented scope |
|---|---|
| Import/state | Idempotent verified imports, exact batch memberships, separate provenance dates, immutable historical rows, controls and event chain. |
| Account/root | Audit-only PKCE/offline OAuth, Keychain storage, current account and stable-root checks, ancestry and two distinct sentinels. |
| Census/changes | Full pagination, raw page evidence, transactional cursor checkpoints, external-change invalidation, derived parent/path updates and explicit access limits. |
| M batches | Fresh stable-ID metadata, historical-name comparison, holds, size differences and sibling collision checks. Proposals are unapproved and unapplied. |
| S02/J/B | Exact-revision downloads, SHA-256 plus Dropbox hash, actual format, full image decoding, dimensions/mode/profile observations and fresh post-read checks. |
| D/H | Current target/keeper metadata, same-folder/hash comparisons and bounded sharing/history reads. Deletion eligibility stays false pending the later safeguards. |
| F/I | Folder/descendant evidence and candidate visual memberships. Semantic naming and image identity decisions remain pending. |
| I00 | Traceable source assertions and exact dated folder links, with related-scope relationships. Different questions are not merged solely because they share a folder. |
| Reports/checkpoints | JSON, safe CSV, escaped HTML with observed file/folder links, consistent SQLite backup, a ledger derived from that backup, evidence checksums and verified checkpoint ZIPs. |

Batch HTML reports link each observed file to its Dropbox preview and containing folder. Pair reviews keep target and keeper links separate; folder reviews include collapsible descendant links. Links use the recorded native paths and stable-ID associations, without fetching images or creating shared links. Historical paths and proposed names remain in the evidence and are not used as navigation fallbacks.

I00 can progress without Dropbox:

```sh
./.venv/bin/boldstone batch run I00 --read-only --new-attempt
```

Its 29+18+14 supplemental rows overlap the nine checkpoint cases. The report does not claim 61 or 70 distinct unresolved identities. Native workbook completeness, semantic reconciliation and new visual inspection remain separate objectives. This partial attempt deliberately exits with code 4.

J reviews look for hash-verified local source downloads associated with the exact source ID and account/root. When present, they compare dimensions and orientation; they do not automatically accept visual or colour equivalence. Historical revision retrieval and independent backup-source assessment remain to be implemented.

## Remaining implementation and validation

Exact child manifests/approvals, mutation preflight, original-file backups, operation journaling/recovery, independent mutation verification and R/X/C/Q/G execution are **not implemented**. Visual contact sheets/review acceptance, full family T/final Z audits, and XLSX reports are also pending. The CLI exposes none of those unimplemented commands.

Real OAuth, account-specific API behavior and disposable Dropbox sandbox integration have not been certified by the offline tests. Native sandbox mutation tests require a separately approved disposable folder before executor work can be accepted. There is no force option, hold-release option or permanent/folder deletion path.

## Verification and reproduction

```sh
uv sync --locked --extra dev
./.venv/bin/ruff check src tests
./.venv/bin/pytest
python3.13 '../dropbox resolution/bootstrap.py' verify
python3.13 -m unittest discover -s '../dropbox resolution/tests' -v
```

For another local runtime, initialize a fresh configuration and import the preserved package:

```sh
./.venv/bin/boldstone --config /absolute/private/runtime/config.json config init \
  --pack '/absolute/path/dropbox resolution' --runtime /absolute/private/runtime
./.venv/bin/boldstone --config /absolute/private/runtime/config.json import \
  --pack '/absolute/path/dropbox resolution'
```

Exit codes: 0 stated objective succeeded; 2 invalid configuration/local I/O; 3 blocked prerequisite/retained hold; 4 partial/interrupted; 5 remote read failure; 7 integrity failure. A report's successful exit refers to writing that report, not to cleanup completion.

Official references: [Dropbox OAuth](https://docs.dropboxapi.com/dropbox-api/docs/oauth), [namespace guide](https://docs.dropboxapi.com/dropbox-api/docs/team-files), [Python SDK](https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html), [Pillow image decoding](https://pillow.readthedocs.io/en/stable/reference/Image.html).
