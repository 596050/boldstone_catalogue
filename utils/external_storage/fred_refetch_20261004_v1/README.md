# FRED observations re-fetch — 4 October 2026

Replaces the one outstanding batch of the Toshiba migration,
`toshiba-fred-7887b862`, by re-fetching the data from the FRED API instead of
copying it off the drive. Uploads to the same encrypted repository,
`sftp://u670499@u670499.your-storagebox.de:23/market-data-v1`
(id `e14c2837a2d7b298aa9d151bfa8c1e4f68bbb74eca622edb2aa0ed5984e327fb`),
under group **`fred-refetch-20261004`**.

## Why re-fetch instead of copy

That batch is 535,143 files in a *single* exFAT directory whose directory table
is **67.6 MB**. exFAT has no directory index, so every open-by-name linearly
scans that table. Measured on an idle, healthy drive (67.7 MB/s on large files,
no I/O errors):

| Operation | Result |
|---|---|
| `listdir` of 534,810 entries | 43-168 s (one sequential pass) |
| open+read 100 files, random order | 4.267 s/file |
| open+read 43 files, on-disk order | 10.069 s/file |

`iostat` showed ~4,600 IOPS x 4 KB = 18 MB/s of metadata churn delivering about
5 KB/s of payload. Projected cost to copy: **62 days**, during which the drive
is unusable for anything else — concurrent access was tested and is impossible,
because a volume-wide exFAT metadata lock starves any second reader (a directory
listing took 33 s with that batch running and 0.25 s with it stopped).

Packing the files first does not help: building the archive needs the same
535,143 lookups. The content is public FRED API data, so re-fetching is the
cheaper path by three orders of magnitude.

## Scope

`SERIES_IDS.json` holds the **534,792** series that have a completed `.json` on
the drive, derived from the directory listing. `SERIES_IDS_EXTRA.json` adds the
**18** series the original collector left as `.tmp` with no completed file, so
this run is slightly more complete than the source. Total **534,810**.

The drive's `catalog/all_series_ids.json` lists 845,503 series; 310,711 of those
were never fetched and are deliberately out of scope. Every on-disk series is in
the catalogue.

## What this is and is not

Re-fetched data is **equivalent, not byte-identical**. FRED series extend over
time and each response carries its own `realtime_start`. Verified on
`00XALCATM086NEST`: identical first observation, same 13 response keys, 368
observations against the original 366, because two more months were published
after the original 11 August fetch. This is a current copy of the same series,
not a bit-for-bit restore of the Toshiba files.

## Output and operation

Consolidated **gzipped JSONL shards** in `shards/` (git-ignored), 128 contiguous
shards of ~4,179 series, one JSON object per line as
`{"series_id", "fetched_at", "response"}`. Measured ~4 KB/series compressed, so
roughly **2.1 GB** total against 18 GB free locally. This is the point of the
format: a handful of large objects, never half a million small files.

```sh
python3 utils/external_storage/fred_refetch_20261004_v1/fetch_fred.py   # resume
cat   utils/external_storage/fred_refetch_20261004_v1/STATE.json        # progress
```

Paced at up to 120 requests/minute, FRED's documented ceiling, backing off on
HTTP 429 and retrying 5xx and network errors with exponential backoff. A series
FRED rejects with 400 is recorded in `errors.jsonl` and skipped. `STATE.json` is
written every 500 series, so the counter lags real progress by a few minutes.

Expected duration **~3.1 days** at 120/min.

`supervise.sh` runs it under `caffeinate` and restarts it on failure until
`STATE.json` reports `COMPLETE`. The 19 September transfer died on a single
transient SSH drop (`ssh command exited: exit status 255`) and then sat idle for
two weeks; this must not repeat on a multi-day run.

Resumption was tested: completed shards are skipped with **zero** network
fetches, and an interrupted shard resumes from the series already in its `.part`
file after that file is rewritten to drop any truncated final line. Uploads run
every 16 completed shards and once at the end, so a crash costs at most the
shards since the last upload.

## Relationship to the Toshiba migration

The other 44 planned batches are already captured; see
[`../hetzner/toshiba_transfer_20260916_v1/README.md`](../hetzner/toshiba_transfer_20260916_v1/README.md)
and [`../hetzner/toshiba_transfer_parallel_20260919_v1/README.md`](../hetzner/toshiba_transfer_parallel_20260919_v1/README.md).
**No Toshiba originals are deleted or modified by this job**; it only reads the
directory listing to determine scope.

The Toshiba `fred` files themselves remain un-copied. If a bit-exact copy of
them is ever required, the only practical route found was a block-level image of
the partition, which bypasses the filesystem entirely.
