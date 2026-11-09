# Boldstone catalogue tools

Source code for the local Boldstone sculpture catalogue, image review room,
Dropbox organisation tools and supporting catalogue workflows.

Loose spreadsheets and CSVs are organized by purpose in [data/](data/README.md).
Their original root paths remain as relative compatibility links. Run
`python3 scripts/check_data_layout.py` to verify the files and links against
their original SHA-256 checksums. Runtime databases and credentials stay in the
applications' private state folders outside this checkout.

Run every active application's offline checks with
`python3 scripts/check_workspace.py` (use `--python` / `--node` to select runtimes).
The Python environment needs the application dev extras and the Squarespace
script requirements. Each check has a separate log and failures return a nonzero exit.
Add `--browser` to exercise the review app and layout lab in Chrome against an
isolated fake server. This requires Playwright (set `PLAYWRIGHT_MODULE` to its
`index.mjs` when installed separately) and Chrome or Playwright Chromium.
Browser screenshots and a workflow receipt are saved alongside the check logs.
It also verifies 20 fresh page loads, two at a time, checking every startup
script's response, content type and bytes without retries.

The [9 November bug audit](docs/bug-audit-2026-11-09.md) records the fixes,
verification and missing private inputs. The earlier channel publication
handover is retained in [docs/archive/](docs/archive/catalogue-channel-status-2026-10-31.md).

## Projects

- `catalogue-review/` - local review application, galleries, component and
  specification editing, image roles, pricing, exports and background jobs.
- `application/` - read-only Dropbox inventory/audit application and the shared
  Python environment used by the review app's authenticated workers.
- `image-processing/` - Dropbox authorisation and image conversion tools.
- `sculpture-catalogue/` - catalogue reconciliation, publication, review and
  verification scripts, including retained historical source versions.
- `search-analytics-toolkit/` - search/analytics utilities, with its own setup.
- `SquareSpace product upload/`, `dropbox resolution/` and
  `boldstone_flat_migration_local_2026-10-15/` - platform and migration tools.
- `reports/` and `outputs/` - source scripts from earlier reviews and audits;
  the generated records, photographs and results are deliberately excluded.

This repository includes retained source workbooks, but is not a copy of the
private published catalogue or Dropbox.
Historical scripts may reference local datasets and absolute paths. They are
retained for traceability and are not automatic startup or migration commands.
Read each project's instructions before running it.

## Review application

Use Python 3.11-3.14 for the shared environment (verified here with 3.12).
Install the Dropbox SDK, Pillow and Keyring in the
existing `application/.venv` environment (the dependency ranges are in
`application/pyproject.toml`). On a new checkout, create that environment and
install the application package:

```sh
python3.12 -m venv application/.venv
application/.venv/bin/python -m pip install -e './application[dev]'
python3 catalogue-review/launch.py
```

The app opens at `http://127.0.0.1:8767`. It requires the separately retained
private catalogue publication, including `sculpture-catalogue/current-master.json`
and the register/database named by that pointer. Review decisions and runtime
state are stored outside this repository under
`~/Library/Application Support/BoldstoneReview/`. Existing Dropbox credentials
remain in macOS Keychain; they are not distributed by this repository.

Gallery thumbnails are cached with a 256 MiB limit. Full Dropbox originals are
read on demand through the local server. Background inventory checks do not
download galleries. See `catalogue-review/README.md` for the workflows and
data-preservation rules.

## Tests

The review application's fake-adapter tests do not need Dropbox credentials:

```sh
application/.venv/bin/python -m unittest discover -s catalogue-review/tests -p 'test_*.py'
node --test catalogue-review/tests/*.cjs
```

Some browser and historical verification scripts explicitly require the local
catalogue, browser tooling or a live read connection. They are separate from
the fake-adapter suite. Never use test execution to authorise Dropbox changes.

## Local files excluded from Git

The allowlist in `.gitignore` includes code and retained CSV/XLSX inputs while excluding
photographs, downloaded originals, generated binary exports, private catalogue JSON, SQLite
databases, JSON snapshots, logs, archives, installed dependencies and secrets.
Those files continue to exist locally or in their verified archives/Dropbox.
Source scripts and required static application HTML are included. A generated
JavaScript inventory containing private image records is explicitly excluded.
