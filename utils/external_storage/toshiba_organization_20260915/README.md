# Toshiba data organization, 15 September 2026

Scope: the external folders `marketmaker`, `marketmaker_v2` and
`macroeconomics` on volume UUID `087E2AA1-5151-322D-8C09-9852ECD979B5`.
The local repositories under `/Users/tprice/Developer` remain in place.

This record is a work log until `reconciliation/RESULT.json` reports `PASS`
and `DELETION_READINESS.json` confirms the actual cleanup. A plan, proposed
registry, or passing software test is not proof that the drive was reorganized.

## Layout

| Directory below `/Volumes/Toshiba 2TB` | Contents |
| --- | --- |
| `raw_price_data/iqfeed_archive` | Original IQFeed protocol, daily, minute and tick archives, with metadata and receipts |
| `raw_price_data/iqfeed_macro_market` | IQFeed currencies, commodities, rates, Treasuries and market proxies |
| `raw_price_data/ibkr`, `ig`, `yahoo`, `raw` | Existing price and broker dataset layouts |
| `raw_price_data/recovered_project_sources` | Additional acquisition subtrees recovered from old research and runtime folders, retaining their full original relative paths |
| `raw_price_data/embedded_source_archives` | Two intact mixed legacy tar bundles containing price records; member lists retained |
| `raw_price_data/price_views` | Formatted source-update and producer/verifier price views; these are not additional unique vendor observations |
| `other_data/macroeconomics/economic_releases` | Official macroeconomic releases, original responses, calendars and vintages |
| `other_data/non_price_provider_archive` | FRED, EIA, SEC, Treasury, CFTC, FINRA, GDELT and other retained providers |
| `other_data/raw/non_price`, `non_price_legacy` | Other explicit non-price acquisition and exogenous sources |
| `other_data/research`, `derived`, `models`, `datasets`, etc. | Remaining original logical data namespaces |
| `other_data/legacy_ibkr_files` | Loose reports, diagnostics, positioning tables and other retained files |
| `other_data/retained_marketmaker`, `retained_marketmaker_v2` | All other project contents, including hidden files, code, evidence, caches and disk images |

Directory classification does not establish source correctness, usable history,
unique observation counts or point-in-time availability. Mixed bundles stay
intact. No payload deduplication or cache pruning is part of this operation.
Consequently, organization does not materially free drive space.

## Evidence and recovery

- `census_repaired/` contains the complete planning census for the authorized
  trees: **960,175 files / 1,536,393,468,118 logical bytes** across the drive's
  accessible namespaces. This includes a few untouched root/system files and
  is not an atomic snapshot. Five timed-out directories were separately reread;
  original scan results remain unchanged.
- `PLAN.json` and `PLANNED_FILES.jsonl.gz` map original paths to intended paths.
  `execution/moves/*/RECEIPT.json` records actual completed moves. Each receipt
  has immediate `BEFORE.jsonl.gz` and `AFTER.jsonl.gz` inventories.
- `execution/JOURNAL.jsonl` is append-only. `execution/BLOCKED.json` identifies
  busy sources left in place. A move that fails verification retains its data
  at the destination and stops further execution.
- `reconciliation/` independently compares original census, immediate move
  inventories, and final filesystem traversal. It records concurrent additions,
  changes, missing files and namespace differences explicitly.
- `BEFORE_data_paths.json` and the original on-drive identity marker are retained.
  `ACTUAL_data_paths.json` is derived only from verified move receipts.

The mover renames data on the same filesystem; it never copies then deletes a
source. It verifies all file paths, lengths, modification times and non-empty
file IDs, all descendant directory names, and selected SHA256 content samples.
The exFAT driver does not support atomic exclusive rename. Its fallback runs
under the migration lock in the unpublished destination namespace and refuses
observed destination collisions. This is not an atomic no-clobber guarantee
against an unrelated process writing the same new destination concurrently.

This is not a full cryptographic read of every payload byte or a second backup.
Disk images and other archives are preserved intact; their interiors are not
all independently enumerated. OS-managed `.Spotlight-V100` and `.Trashes` are
inaccessible and untouched. Other system folders and Toshiba manuals stay put.

For an original path in a historical receipt, use the final `path_relocations`
map in `data_paths.json`, or:

```python
from utils.data_paths import resolve_relocated_path
current = resolve_relocated_path(
    "/Volumes/Toshiba 2TB/marketmaker/iqfeed_archive/minute/original-file",
    require_exists=True,
)
```

Historical receipts and frozen source bytes are not rewritten. New code should
use `resolve_data_path`, `resolve_data_dir` or `resolve_source_location` for
logical data locations. Concatenating a non-price path onto
`CONFIGURED_DATA_ROOT` bypasses the split layout; legacy callers doing this
need explicit adaptation before use. Frozen price paths under `ibkr/` retain
their original relative dataset layout.

## Resume and cleanup

Only one mover may run. Resume with the same plan and state directory; inspect
any verification failure before continuing. Already verified moves are checked
against their source/destination state and are not repeated.

```sh
python3 -B utils/external_storage/toshiba_organization_20260915/registry.py begin
python3 -B utils/external_storage/toshiba_organization_20260915/organize.py apply \
  --plan utils/external_storage/toshiba_organization_20260915/PLAN.json \
  --state utils/external_storage/toshiba_organization_20260915/execution --skip-active
python3 -B utils/external_storage/toshiba_organization_20260915/reconcile.py audit
python3 -B utils/external_storage/toshiba_organization_20260915/reconcile.py cleanup
python3 -B utils/external_storage/toshiba_organization_20260915/registry.py publish
```

Busy child extractions block their parent move. Observed readers remain fenced
until their process exits, including gaps between file opens. Registry maintenance prevents
new registry-based consumers from accessing a partially relocated layout;
already-running readers are left alone. A partial registry publication records
unmoved sources at their actual old paths. Never infer full completion from it.

Cleanup uses only `rmdir` on the verified-empty external `marketmaker/data` and
`marketmaker` containers. The `marketmaker_v2` root remains present, and its
deletion readiness is recorded outside that directory. No recursive deletion
is used anywhere in the organizer. Reversing a relocation requires a reviewed
reverse mapping with the same identity checks, collision checks and idle-source
checks; do not use an unverified bulk rollback.

The separate [Hetzner helper](../hetzner/README.md) supports upload and recovery
of both organized roots. This reorganization does not provision Hetzner, upload
data, or establish a verified remote backup.
