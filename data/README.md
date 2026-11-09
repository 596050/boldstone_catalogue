# Workspace data

The 26 spreadsheets and CSVs formerly stored directly in the repository root
and the Squarespace content folder now live under `inputs/` and `exports/`,
grouped by purpose:

```
inputs/
  catalogue/                Masterplans and matched sculpture workbooks
    pricing/                Source price list and reconciliation workbook
  marketplaces/
    chairish/
    ebay/
    saatchi/
    squarespace/
    tiktok/
  migration/                Folder proposals, source routes and family index
exports/
  squarespace/              Prepared import and commerce-catalogue CSVs
file-manifest.csv           Original names, new paths, sizes and SHA-256 hashes
```

Original filenames, duplicate downloads, workbook contents and CSV bytes are
preserved. Relative symbolic links at their original root paths keep scripts,
saved references and external workflows working. Use the organized paths for
new work; retain those links for older tools. Git preserves the links on macOS
and Linux. A checkout that cannot create symbolic links needs symlink support
enabled before running tools that use the old paths.

Run `python3 scripts/check_data_layout.py` from the repository root to verify
every moved input and compatibility link. The manifest records the organization
baseline; intentional later edits will require a reviewed manifest update.

Other data already has dedicated locations:

| Location | Purpose |
|---|---|
| `sculpture-catalogue/` | Published catalogue and retained reconciliation history. The private `current-master.json`, register and gallery database must be restored separately. |
| `channel-update-playbook/` | Channel-specific publishing records and preparation tools. |
| `SquareSpace product upload/` | Blog/social content and per-post image preparation. |
| `reports/`, `outputs/` | Dated audit and export workflows, including historical scripts with retained paths. |
| `dropbox resolution/`, `boldstone_flat_migration_local_2026-10-15/` | Immutable handover packs and migration evidence. |

The original paths in both the root and Squarespace folder remain usable. The
dated history and handover packs remain at their original paths to preserve
checksums and dependencies. This organization does not move anything in Dropbox.
Active review decisions, caches, credentials and databases remain outside this
checkout, under the applications' configured private runtime directories.

The source workbooks are not a substitute for the private published catalogue,
shipping tariff or migration evidence omitted from this source checkout.
