# Toshiba data manifest — 14 September 2026

The latest verified census is **run_06**: **949,203 files**, **21,921 directories** below the volume root, and **1,514,854,899,421 logical bytes** (1.515 TB decimal).
It read `/Volumes/Toshiba 2TB` from **2026-09-14T04:37:03.728291+00:00** to **2026-09-14T04:48:53.368014+00:00**. Every reachable directory was attempted. This is a live, non-atomic census; it cannot include subsequent filesystem changes.

The registered volume UUID `087E2AA1-5151-322D-8C09-9852ECD979B5` and storage identity (USB serial `20251128012837F`) matched before and after the scan. The manifest process only read the Toshiba; its outputs are in this repository. Other jobs could write during the scan.

## Files to use

- [Full file manifest](run_06/FILES.jsonl.gz): one JSON record per file, including hidden, empty and partial files. Paths are relative to the mount. Records retain logical size, modification/change times in epoch nanoseconds, observation time, device and inode.
- [Directory summary](run_06/DIRECTORY_SUMMARY.jsonl.gz) and [directory index](run_06/DIRECTORY_INDEX.json): counts, logical sizes and read errors.
- [IQFeed datasets and filename symbol lists](run_06/IQFEED_DATASETS.json).
- [Macroeconomic datasets](run_06/MACRO_DATASETS.json) and [individual acquisition records](run_06/MACRO_ACQUISITIONS.jsonl.gz).
- [Exclusions](run_06/EXCLUSIONS.json), [scan summary and hashes](run_06/SUMMARY.json), and [independent verification](run_06/VERIFICATION.json).

The following filename-based categories partition the observed files. They include associated metadata and research artifacts; they are not counts of unique source observations.

| Category | Files | Logical GB |
| --- | ---: | ---: |
| `iqfeed_related` | 133,037 | 731.497 |
| `macroeconomics` | 551,815 | 54.858 |
| `other` | 264,351 | 728.500 |

## IQFeed coverage

The main `marketmaker/iqfeed_archive` tree contains **68,745 files** and **725.613 logical GB**. Its family counts include metadata where present. Plain CSV filename stems do not certify ticker identity, valid rows or continuous date coverage.

| Archive family | Files | Logical GB | Plain CSV filename stems |
| --- | ---: | ---: | ---: |
| `.locks` | 1 | 0.000 | 0 |
| `daily` | 549 | 0.183 | 549 |
| `daily_sp_historical` | 50 | 0.009 | 50 |
| `future_proxy_tick_data_20260905_v1` | 156 | 0.882 | 0 |
| `future_proxy_tick_data_20260905_v2` | 504 | 3.970 | 0 |
| `future_proxy_tick_data_20260905_v3` | 296 | 2.319 | 0 |
| `future_proxy_tick_data_20260905_v4` | 336 | 3.114 | 0 |
| `iqfeed_lifetime_tick_availability_20260905_v1` | 6 | 0.001 | 0 |
| `minute` | 741 | 62.699 | 549 |
| `sp500_lifetime_minute_book_20260905_v1` | 397 | 0.094 | 305 |
| `tick` | 46,024 | 294.171 | 135 |
| `tick_futures` | 10,031 | 104.855 | 145 |
| `tick_teacher_breadth_405_20260905_v1` | 44 | 0.366 | 0 |
| `tick_teacher_breadth_405_20260905_v2` | 409 | 5.698 | 0 |
| `us_primary_listed_minute_book_20260906_v1` | 9,008 | 247.245 | 8,816 |
| `us_primary_listed_minute_book_frozen96_tail_20260911T174415601489Z` | 96 | 0.003 | 96 |
| `us_primary_listed_minute_book_frozen96_tail_20260911T201442724800Z` | 96 | 0.003 | 96 |
| Files directly in the archive root | 1 | 0.000004 | — |

The separate frozen daily source `marketmaker/data/ibkr/iqfeed_192_daily` contains **578 files**, totalling **71,098,217 bytes**. Other IQFeed-named source, replay and research directories are listed in the IQFeed index. Different paths do not establish independent canonical datasets.

## Macroeconomic coverage

| Root | Files | Logical GB |
| --- | ---: | ---: |
| `macroeconomics` | 11,265 | 13.031 |
| `marketmaker/macro_archive` | 540,550 | 41.828 |

The IQFeed macro source catalogue includes commodities, Treasury futures, Fed Funds/SOFR futures, published rates, currencies, volatility and market breadth. Configured instruments are not necessarily acquired instruments. Retained acquisition outcomes are:

| Acquisition status | Jobs |
| --- | ---: |
| `COMPLETE` | 5,210 |
| `COMPLETE_WITH_ANOMALIES` | 83 |
| `NOT_AUTHORIZED` | 99 |
| `NO_DATA` | 22,267 |
| `SPLIT` | 90 |

**10,766 payload references were present** and **0 were missing** in the census. All **11 source catalogues** were freshly copied, SHA-256 hashed, checked for stability while copied and reconciled to the census size and modification time. Their compressed copies are in [source_catalogs/](run_06/source_catalogs/). Acquisition payload checksums remain historical declarations; large payloads were not rehashed.

The original economic-release catalogue declares the following series and observation endpoints. These are source dates, not file timestamps or a new certification of historical release availability.

| Series | Description | Frequency | Adjustment | First observation | Last observation |
| --- | --- | --- | --- | --- | --- |
| `CPIAUCSL` | Consumer prices, all items | monthly | SA | 1947-01-01 | 2026-07-01 |
| `CPIAUCNS` | Consumer prices, all items | monthly | NSA | 1913-01-01 | 2026-07-01 |
| `CPILFESL` | Consumer prices excluding food and energy | monthly | SA | 1957-01-01 | 2026-07-01 |
| `CPILFENS` | Consumer prices excluding food and energy | monthly | NSA | 1957-01-01 | 2026-07-01 |
| `PPIFIS` | Producer prices, final demand | monthly | SA | 2009-11-01 | 2026-07-01 |
| `PPIFID` | Producer prices, final demand | monthly | NSA | 2009-11-01 | 2026-07-01 |
| `PPIFES` | Producer prices, final demand excluding food and energy | monthly | SA | 2010-04-01 | 2026-07-01 |
| `PPICOR` | Producer prices, final demand excluding food and energy | monthly | NSA | 2010-04-01 | 2026-07-01 |
| `PCEPI` | PCE price index | monthly | SA | 1959-01-01 | 2026-07-01 |
| `PCEPILFE` | PCE price index excluding food and energy | monthly | SA | 1959-01-01 | 2026-07-01 |
| `PAYEMS` | Total nonfarm employees, level in thousands | monthly | SA | 1939-01-01 | 2026-08-01 |
| `ICSA` | Initial unemployment insurance claims | weekly | SA | 1967-01-07 | 2026-08-29 |
| `T10YIE` | 10-year Treasury/TIPS breakeven inflation | daily | NSA | 2003-01-02 | 2026-09-09 |
| `NFCI` | Chicago Fed National Financial Conditions Index | weekly | NSA | 1971-01-08 | 2026-08-28 |

Employment and yield extensions also present:

| Series directory | Files | Logical bytes |
| --- | ---: | ---: |
| `DGS10` | 58 | 2,006,612 |
| `DGS2` | 58 | 1,613,997 |
| `DGS30` | 58 | 1,573,663 |
| `UNRATE` | 14 | 114,365 |

The archive retains ALFRED vintage evidence and separate source/local clocks. Vintage-interval rows are not unique observations. Consensus expectations and certified intraday release/calendar completeness remain unavailable as described in the preserved source status.

The older macro archive is included at file level:

| Provider directory | Files | Logical GB |
| --- | ---: | ---: |
| `cftc` | 119 | 0.118 |
| `ecb` | 4 | 0.007 |
| `eia` | 32 | 1.791 |
| `eia_api` | 260 | 0.038 |
| `finra` | 1,934 | 0.639 |
| `fred` | 535,143 | 11.690 |
| `gdelt` | 2,917 | 0.306 |
| `ofr` | 1 | 0.001 |
| `sec` | 121 | 8.534 |
| `treasury` | 3 | 0.008 |
| `usaspending` | 16 | 18.696 |

## Other areas included

All reachable file trees are included: IBKR/IG/Yahoo data, ADR/home-market/FX quotes, research inputs and results, retained models and execution evidence, runtime files, downloads, caches and sparsebundle bands. The following selected trees do not overlap with one another; the detailed directory index also contains parents and their children.

| Other directory | Files | Logical GB |
| --- | ---: | ---: |
| `marketmaker/data` | 157,722 | 221.939 |
| `marketmaker/research` | 240 | 38.339 |
| `marketmaker/research_runtime_offload` | 69,976 | 6.381 |
| `marketmaker/recoverable_build_caches` | 0 | 0.000 |
| `marketmaker_v2` | 100,691 | 467.715 |

## What is left out or not verified

- Contents below `.Spotlight-V100`: `PermissionError` during `directory_read`. The entry is recorded, but its interior files and size are unknown.
- Contents below `.Trashes`: `PermissionError` during `directory_read`. The entry is recorded, but its interior files and size are unknown.
- Members inside ZIP/TAR/other containers and filesystems inside disk images or sparsebundles. The containers and accessible band files themselves are included.
- Internal tables, workbook sheets and array variables inside databases, workbooks and binary datasets.
- Extended attributes, ACLs, resource forks, deleted/unallocated data, other devices and link targets.
- Full payload checksums, row-level validity, interior date/bar completeness and independent economic interpretation outside the retained catalogues. This is not a complete backup or trading-input certification.
- Physical allocation is generally unmeasured. `allocated_bytes: null` means unknown. Logical sizes are not occupied filesystem space or potential cleanup savings.

The census retains **8,847 zero-byte files** and **245 files with incomplete/temporary names**. These classifications do not establish that files are disposable. **0 directories** were observed changing during their own listing. The entire volume was not frozen.

## Changes from the previous census

Compared with `run_05`, the file metadata comparison found:

| Observation | Files |
| --- | ---: |
| `METADATA_UNCHANGED` | 931,286 |
| `METADATA_CHANGED` | 377 |
| `APPEARED_IN_CENSUS` | 17,540 |
| `NOT_SEEN_IN_CURRENT_CENSUS` | 291 |

Non-atomic file metadata censuses. Equal metadata does not prove equal contents. Appearance or absence does not prove creation or deletion.

[Comparison and bound manifest hashes](run_06/CHANGES_SUMMARY.json).

## Search without Toshiba connected

Run from the repository root:

```bash
python3 research/utility/toshiba_data_manifest_20260913_v1/query.py --prefix marketmaker/iqfeed_archive/minute/ --summary
python3 research/utility/toshiba_data_manifest_20260913_v1/query.py --contains /DGS10/ --limit 5
python3 research/utility/toshiba_data_manifest_20260913_v1/query.py --directories --prefix marketmaker/macro_archive/
```

`LATEST.json` selects `run_06`. Use `--run-id run_04` or `--run-id run_03` for retained earlier censuses.

Independent verification re-read all manifest streams, checked their hashes and all **971,124 unique entry paths**, reconciled every directory's child counts and logical byte totals, checked the directory/IQFeed indexes, and compared macro acquisition records with the preserved source catalogue. It passed with the recorded filesystem exclusions.
