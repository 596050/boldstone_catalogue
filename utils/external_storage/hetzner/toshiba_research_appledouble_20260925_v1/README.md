# Research upload without AppleDouble sidecars — 25 September 2026

`toshiba-research-20260923` (`/Volumes/Toshiba 2TB/other_data/research`, 141,025 files,
130.85 GiB) failed seven attempts on 24 September with **Restic exit 3**, so no snapshot
was marked complete. Every error was on a macOS AppleDouble sidecar (`._docker`,
`._RETURN_MANIFEST.json`, `._*.sparsebundle`, …):

```text
error: incomplete metadata for …/._docker: xattr.list …/._docker: operation not permitted
```

On exFAT, macOS keeps each file's extended attributes in a hidden `._name` companion.
Restic already records those attributes on the real files; listing attributes of the
companion itself is refused by the FSKit exFAT driver. No ordinary data file failed, and
the last attempt added only 163 MiB, so the payload is already in the repository.

## Change

This directory holds a job-local copy of `../storage_box.py`, so the shared utility stays
byte-identical to the `storage_utility_sha256` recorded in
`../toshiba_transfer_20260916_v1/LAUNCH.json`. Differences:

```text
storage_box.py:41   REPO_ROOT = …parents[4]   # was parents[3]; the copy sits one level deeper,
                                              # keeping data_paths.json and the Toshiba identity check
upload --exclude PATTERN                      # repeatable; passed to restic backup --exclude,
                                              # recorded in the receipt ("exclude") and as a
                                              # snapshot tag "exclude:PATTERN"
```

The `._*` pattern was checked against a throwaway local repository: it removes `._name`
entries at any depth and keeps names that only contain `._` (for example `x._y`).

Note: `../toshiba_transfer_parallel_20260919_v1/storage_box.py` also sits one level deeper
but kept `parents[3]`; with no `data_paths.json` at that root, its Toshiba identity/UUID
check was silently skipped.

## Command

```sh
cd /Users/tprice/Developer/marketmaker_v2
caffeinate -i python3 utils/external_storage/hetzner/toshiba_research_appledouble_20260925_v1/storage_box.py \
  upload --group toshiba-research-20260923 --require-mount "/Volumes/Toshiba 2TB" \
  --exclude '._*' -- "/Volumes/Toshiba 2TB/other_data/research"
```

Expected cost: one full re-read (~1 h 10 min at the 24 September rate); new uploaded
bytes should be small because the data is already deduplicated in the repository.
Nothing on the Toshiba is modified.

## Outcome

Checked first on one small folder containing two `._*` files (dry runs): the shared tool
without an exclude reproduced Restic exit 3; this copy with `--exclude '._*'` exited 0.

Full run 2026-09-25 22:59 → 2026-09-26 00:06 UTC: **complete, Restic exit 0**, receipt
`upload-c3c3e2a2b862416abfa57b49d2889993`, snapshot
`b12f333cbad89535ec26380acf7594c0d727148bed9aec751f3c943e40d27715` (tags include
`exclude:._*`). 144,181 files and 136.44 GiB processed; 5.17 GiB new (4.31 GiB stored),
mostly research files written since 24 September. The folder is live, so this is not an
atomic snapshot. Stored-data readback (`verify --read-data`) was not run.
