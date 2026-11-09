# Economic releases and historical vintages

Stored only at `/Volumes/Toshiba 2TB/macroeconomics/economic_releases` using the
central `source_locations.macroeconomic_releases` registry and verified Toshiba
identity. This is a separate HTTP collector: it does not stop, edit or duplicate
the existing IQFeed worker, its queue or its source files. A 20 GiB reserve applies.

## Contents

- `current_vintage/inflation/{cpi,ppi,pce}/`: headline and core series. CPI/PPI
  include separate seasonally adjusted and unadjusted variants.
- `current_vintage/labour/{payrolls,jobless_claims}/`,
  `current_vintage/inflation_expectations/`, and
  `current_vintage/financial_conditions/`: PAYEMS, ICSA, T10YIE and NFCI.
- `vintages/`: every advertised ALFRED vintage through the snapshot cutoff,
  requested in bounded batches. Each ZIP's original CSV and historical metadata
  README are retained alongside the exact downloaded ZIP body in `.raw.gz`.
- `calendars/`: official BLS, BEA and FOMC source documents. Successful
  iCalendar downloads additionally produce structured events with explicit zones.
- `release_documents/bls/`: CPI, PPI and payroll archive indexes and all dated
  release documents discovered on successfully fetched indexes.
- `consensus/`: documentation and explicit access status; no fabricated forecast
  values. No paid service, registration or subscription is purchased.
- `policy_expectations/`: methodology and links to the separate dated IQFeed
  futures catalogue. No claim to have downloaded or calculated FedWatch odds.
- `metadata/`: archive scope, durable queue, status, per-run collector hashes,
  `SERIES_INDEX.csv`, `MANIFEST.json` and independent verification reports.
- `reference/probes/`: retained live transport tests, including initial Python
  URL-opener timeouts. The native curl transport succeeded on the same public
  sources. Failed probes are evidence, not datasets or successful acquisitions.

## Interpretation and safety

These are published statistics, not minute-by-minute traded prices. Original
FRED/ALFRED responses are labelled with their distributor and underlying source;
they are not mislabelled as direct BLS/BEA API responses. Index levels, original
numeric strings and missing-value markers are preserved. No filling, splicing,
rescaling, seasonal adjustment, return calculation or consensus inference occurs.

Current-vintage history is **not** what a trader knew at each historical date.
ALFRED validity intervals are date-level evidence, not exact intraday release or
local receipt timestamps. Read each ZIP's README: historical definitions, index
bases and titles can change, and early vintages may contain incomplete history.
The first archived vintage is not necessarily an observation's original release.
Never expose a monthly statistic at the beginning of its reference month.

All ALFRED form-advertised vintage dates are enumerated. Each response must echo
the exact requested dates in its README; a truncated selection fails validation.
Validity intervals may repeat unchanged across download chunks. Keep the raw
chunks; consumers may deduplicate only exact identical interval/value records,
must reject conflicts, and must retain the metadata valid for the chosen vintage.
Reported chunk row totals therefore are not unique observation counts.

Calendars are snapshots as observed now. Past events on today's calendar are not
proof that a historical forecast knew that schedule. Source filename dates on
BLS documents are retained as such; an 08:30 publication time is not silently
assumed. Consensus, release values and revised prior values need independently
verified units, adjustment, reference periods and availability times before use.

Each HTTP receipt preserves the URL, POST fields, response status, selected HTTP
headers, local capture start/end times and body/compressed SHA256 hashes. Original
error responses remain distinct. Source denials do not cause authentication
bypasses or replacement with a different provider. Temporary responses are on
Toshiba; interrupted temporary files and failed attempts are retained.

## Run and verify

From `/Users/tprice/Developer/marketmaker_v2`:

```sh
python3 -B -m utils.macroeconomics.archive init
python3 -B -m utils.macroeconomics.archive start
python3 -B -m utils.macroeconomics.archive status
python3 -B -m utils.macroeconomics.archive verify
```

`init` creates one new snapshot and must not be rerun on an existing queue.
`run --max-jobs N` performs a bounded foreground batch; `start` launches one
detached worker. Resumption skips completed queue entries; previous responses
are rechecked when reused, never overwritten. A transport failure gets at most
one separately retained retry; access denials are not automatically retried.
Errors and blocked requests remain visible in `STATUS.json` and `MANIFEST.json`.
Collector versions are hash-recorded separately for every worker execution.

For a vintage batch that failed with HTTP 500/502/503/504, the explicit command
`python3 -B -m utils.macroeconomics.archive split-failed-vintages` queues two
disjoint subsets of the same dates. The original error and response remain in
the manifest as `SPLIT_HTTP_FAILURE`, linked to their child requests. Then use
`run` to process the smaller requests. This does not retry authentication,
permission or rate-limit denials, or alter any successful payload.

Create `metadata/STOP` or send the worker SIGTERM for a graceful stop. Remove the
STOP file deliberately before resuming. Never remove a live lock. Keep the Mac,
drive and internet connected; after a host reboot run `start` to resume pending
work. `verify` checks source/derived hashes, gzip/ZIP integrity, schemas, row
counts, exact source-to-derived bytes and vintage acknowledgements. It reports
any missing advertised vintage dates by series; it is not an economic completeness,
forecast-consensus or intraday point-in-time audit.
