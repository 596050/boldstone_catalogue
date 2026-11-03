# Boldstone flat migration: local instruction package

Prepared 15 October 2026. Implements the requested **Family -> member/combination leaf -> images** organization, not the earlier deeper layout.

## Start here

1. Read `instructions/LOCAL_FLAT_MIGRATION_RUNBOOK.md` for the complete procedure.
2. Give the whole extracted package to your local coding agent with `AGENTS.md` (also supplied as `instructions/COPY_TO_LOCAL_CODING_AGENT.md`).
3. Use exact names/mappings from `inputs/flat_plan/`; do not regenerate them from the diagram.
4. Validate and test offline, then have the agent implement the live read-only adapter, controlled executor and verifier.
5. Generate a complete fresh snapshot and an exact dry-run file manifest. Review provisional labels, backups, external destinations and collisions before any authorized mutation.

The package is an instruction and source handover. The live Dropbox executor is NOT included or production-tested. No Dropbox read or mutation was performed in this preparation. The offline helper does not have a Dropbox connection and never sets a route executable.

## Included

- The original flat plan ZIP, unchanged, and its machine-readable files extracted under `inputs/flat_plan/`.
- 347 exact proposed leaves, 74 original review flags, 425 source mapping rows representing 422 unique source folder IDs.
- 63 individual family specifications and `rules/Family_Migration_Index.csv`.
- A 347-row `decisions/Folder_Decisions_TEMPLATE.csv`, all PENDING. Approval is separate from identity verification.
- Historical protection/exclusion controls, with their dates preserved.
- The previous local implementation ZIP unchanged, for the old 350 batches, original evidence and source/replacement history.
- New move-only runbook, schema/configuration, normalized snapshot format, CLI requirements and live test matrix.
- Offline validator/route-preview helper and 28 passing offline tests.

## Commands supplied and tested

From the extracted package directory:

```bash
python3 tools/check_flat_plan.py validate
python3 tools/check_flat_plan.py family "Fingerprint"
python3 -m unittest discover -s tests -v
```

Windows can use `py -3`. The helper uses only the Python standard library. No tokens or pip packages are needed for these commands.

After your live read-only adapter exists and produces a full normalized snapshot:

```bash
python3 tools/check_flat_plan.py route-preview /local/path/live-snapshot.json --out /local/path/new-route-preview.json
```

This preview is still offline and NOT an executable mutation manifest. It cannot prove source authenticity, live freshness, permissions, backups or operator approval. See `spec/SNAPSHOT_FORMAT.md`.

`spec/LIVE_CLI_CONTRACT.md` lists FUTURE commands for the application to implement. Do not assume those commands already work. The historical package's bootstrap utilities are also offline; they are not a production flattening executor.

## Important boundaries

Keep `01 Wall Sculptures` as the actual root name. Keep family names. Keep basenames/extensions and file bytes by default. Do not delete duplicates, convert BMPs, upload replacement images, change sharing or publish products in the same run. Old completed-operation exclusions are not permission to skip newly required verification.

Handle file membership through CURRENT immediate parent IDs. Three family IDs deliberately occur twice in the mapping: RETAIN FAMILY and ROOT-FILE HOLDING PROPOSAL. Do not collapse these rows by ID alone.

The 347-leaf tree is a dated directory proposal, not a file census or completed visual classification. Provisional labels may be explicitly approved as temporary storage while remaining unresolved. New files or deeper subject distinctions need amendments, not guesses.

The recommended empty-source-folder safeguard is an explicitly approved archive outside the image tree after complete emptiness checks, rather than recursive deletion. The archive and the Azure video destination require separate destination approval. No archive or video relocation was executed here.

## Evidence

`evidence/Preparation_Scope.json` describes exactly what was prepared.
`evidence/OFFLINE_TEST_RESULTS.txt` contains the actual 28-test output.
`evidence/Offline_Input_Validation.json` records source checksum and mapping checks.
`PACKAGE_SHA256.json` records this package's file checksums, excluding itself and temporary interpreter caches. Checksums detect changed bytes; they are not digital signatures or user approvals.
