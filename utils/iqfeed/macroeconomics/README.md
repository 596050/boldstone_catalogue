# Macroeconomics: IQFeed source archive

The user-requested physical location is `/Volumes/Toshiba 2TB/macroeconomics`.
It is registered as `source_locations.iqfeed_macroeconomics` in the repository's
`data_paths.json`. All market payloads, the durable queue, receipts and logs are
external-only. The collector uses the already-running IQFeed service on port
9100. It never starts another service, purchases subscriptions, changes source
archives or falls back to another provider.

## Layout

```text
macroeconomics/
  iqfeed/
    commodities/
      gold/{contracts,continuous_front_month,continuous_back_adjusted,spot/}
      oil/{wti,brent}/{contracts,continuous_front_month,continuous_back_adjusted}/
    treasuries/{2_year,5_year,10_year,bond,ultra_10_year,ultra_bond}/
    volatility/{vix,move,vvix,skew,vix_9_day,vix_3_month,oil_etf,gold_etf,vix_futures}/
    currencies/us_dollar_index/
    rates/{treasury_yields,effective_fed_funds,sofr,prime,mortgage_30_year,fed_funds_futures,sofr_futures}/
    market_breadth/{put_call_ratio,nyse_only_tick,nyse_tick,nyse_trin,nyse_advances,nyse_declines}/
  metadata/{ARCHIVE.json,STATUS.json,MANIFEST.csv,queue.sqlite3,WORKER.lock}
  reference/                 # Raw IQFeed listed-futures symbol searches
  incomplete/                # Retained interrupted/split response attempts
  logs/download.log
```

Each source has `daily/` and `minute/` subdirectories. Completed data responses
produce `.raw.gz` (exact received protocol bytes) and `.csv.gz` (readable bars,
original price strings, and quality flags). File names include symbol, requested
date range, immutable job ID and attempt number. Request commands, capture times,
compressed/uncompressed hashes, counts, errors and verification results are in
SQLite and the exported manifest. Tiny empty/denied responses are retained as
gzip BLOBs in SQLite `responses.small_raw_gzip` to avoid thousands of wasteful
exFAT allocations. There is no silent deletion of failed acquisition evidence.

## Scope and interpretation

- Daily and one-minute history, through the cutoff sealed in `ARCHIVE.json`.
  The current partial day, ticks, order book, options and other providers are not
  included. This is historical source collection, not a live trading service.
- Gold and WTI roots are `QGC` and `QCL`, not `@GC` or `@CL`.
- Dated futures, vendor front-month `#`, and vendor back-adjusted `#C` are
  distinct datasets. Treasury futures are not cash-bond transactions or yields.
  OVX/GVZ are ETF option-implied volatility indices, not gold/oil spot prices.
- The 13 declared futures roots are searched across all 12 month codes, expiry
  years 1959 through 20 years after the cutoff year. This deliberately includes
  unlisted candidates; their no-data results are evidence, not missing trades.
  The current IQFeed futures directory supplements the candidate search.
  The selected root family does not cover micros, options, spreads, predecessor
  pit symbols or every exchange variant. No such coverage is claimed.
- Both cadences are requested independently, even when the daily or continuous
  request is denied. Some expired contracts are available when current contracts
  are not. No-data, denied, malformed, interrupted and complete responses remain
  distinct. No credentials or account information are stored in the archive.
- No maximum-datapoint limit is sent for bar downloads. Bounded failed requests
  can split into adjacent non-overlapping date windows and resume independently.
- Negative futures prices and negative breadth are permitted. Nothing is filled,
  shifted, adjusted or replaced. Malformed rows remain in the raw response;
  successfully parsed suspect bars retain quality flags in CSV.
- IQFeed's supplied timestamps are retained verbatim. The minute request
  explicitly uses end-of-bar labels. Vendor daily close/settlement, session
  boundaries, exchange time zones and publication/availability clocks must be
  interpreted before joining sources for research. Zero-volume index bars and
  sparsely published interest rates are not traded prices.
- Completion means the declared requests were processed, not that every market
  minute exists or that every instrument's inception history is recoverable.
  Stale series such as PCRATIO.Z and MTG30YR.X retain their actual final dates.
  Calendar completeness, historical revisions and point-in-time availability are
  not independently established. Read `ARCHIVE.json` for official source links.

## Run, monitor, resume

From `/Users/tprice/Developer/marketmaker_v2`:

```sh
python3 -B -m utils.iqfeed.macroeconomics.archive init
python3 -B -m utils.iqfeed.macroeconomics.archive start
python3 -B -m utils.iqfeed.macroeconomics.archive status
python3 -B -m utils.iqfeed.macroeconomics.archive verify
```

`init` is for a new archive only; it seals the date cutoff, instrument catalogue,
and collector code hashes. `start` launches one detached worker and records its
PID. `run` does the same work in the foreground; `--max-jobs N` permits a bounded
batch. Re-running resumes only unfinished jobs and keeps all prior attempts.
Completed data are not overwritten. For a fresh vintage or changed scope, use
an explicitly reviewed new archive/queue; do not silently change the cutoff.

The worker waits for the existing shared archive-download lock. It releases that
lock between requests and checks a 20 GiB free-space reserve and verified drive
identity before acquisition. It stops if the drive disappears or capacity falls
below the reserve. There is no automatic removal of existing data to make space.
`SIGTERM` requests a graceful stop with partial evidence retained. A file named
`metadata/STOP` also stops the worker at a request boundary; it must be deliberately
removed before resuming. Never remove or override a live lock.

The worker survives a terminal closing, but not a host reboot or a permanently
unavailable drive/feed. After restoring those prerequisites, run `start` again.
Inspect `STATUS.json` and the process/log to distinguish active work from a
stale status after an abrupt machine failure. `verify` rechecks every recorded
response's hashes, gzip integrity and CSV row count; it is not an exchange-
calendar coverage audit. `MANIFEST.csv` is refreshed periodically and at exit.

Monitor using `status`, `STATUS.json`, `MANIFEST.csv` and the log, not a long
transaction on the live SQLite queue: even read-only SQL can block commits on
the external drive. The collector retries only SQLite BUSY/LOCKED conditions for
up to five minutes after the underlying busy timeout, without repeating a
download or previously executed INSERTs. `WAITING_FOR_SQLITE` is logged. A stop
request, exhausted retry window, corruption or other storage errors still pause
the worker; uncommitted changes are rolled back before exporting error status.

Collector maintenance is explicit: after reviewing and testing a code change,
`rebind --reason 'description of reviewed change'` verifies all existing response
hashes and creates an immutable `metadata/COLLECTOR_REVIEW_*.json` containing the
previous archive binding and new code hashes before allowing resumption. It also
corrects legacy failed queue entries whose complete raw response was solely an
IQFeed no-data error with optional trailing empty columns. Original attempt
receipts and raw responses are never rewritten, and changed entitlements are not
automatically retried.
