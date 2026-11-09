# Original hybrid source refresh and Hetzner copy

The 96-stock source copy and parallel IQFeed refresh are verified. **Neither original hybrid achieved adjusted statistical confirmation.**

The pinned cutoff is 21 September 2026, the latest completed session when acquisition started. All 96 daily histories were refreshed in full and all 96 minute tails were downloaded concurrently with four workers. The six new sessions are September 14, 15, 16, 17, 18 and 21. The source update contains 679,293 daily rows and 326,564 minute-tail rows; raw inconsistent observations remain retained.

## Storage

Existing encrypted Restic repository: `sftp://u670499@u670499.your-storagebox.de:23/market-data-v1`.
Repository ID: `e14c2837a2d7b298aa9d151bfa8c1e4f68bbb74eca622edb2aa0ed5984e327fb`.

- Original sources: **526 files / 26,451,956,602 bytes**: 96 daily files and 430 overlapping raw-minute components. Snapshot `f0ca9f2225f088002e2eee645fba278272bd0343622479e8775ed06cd260453a`; group `frozen96-original-hybrid-sources-20260922`.
- Refresh: **96 daily files, 96 minute tails, one historical SLB probe**, plus receipts and VIX context. Snapshot `02286b85b0d054badcb54966658d79457240e46cb8ddade7bdf72a3a19668381`; group `frozen96-iqfeed-update-20260922`.
- Full remote content readback passed for all 531 historical/provenance files and 388 refresh/receipt files. Every file was decrypted and SHA256-compared with its bound source hash.
- No Toshiba source was deleted or overwritten. Updates are separate, immutable source versions in Hetzner, with a bounded local staging copy used for this replay. Existing source directories remain bound to their original vintage.
- [Source binding](SOURCE_BINDING.json), [historical readback](REMOTE_READBACK.json), [refresh readback](UPDATED_REMOTE_READBACK.json), [acquisition receipt](REFRESH.json).

The snapshots retain the original absolute source paths. Use the existing storage utility to list or restore a group; restore to a separate destination with sufficient free space:

```sh
python3 utils/external_storage/hetzner/storage_box.py --profile market-data snapshots --group frozen96-original-hybrid-sources-20260922
python3 utils/external_storage/hetzner/storage_box.py --profile market-data snapshots --group frozen96-iqfeed-update-20260922
```

## Refreshed original comparison

The daily study now covers **2011-01-03–2026-09-21, 3,952 sessions**. Original algorithms, expert policies, matched controls, GBP capital and 0/20/40 bp costs are unchanged. All 14 model books and all 31 common metric rows, annual and stock-level breakdowns are retained. These remain hypothetical daily GBP rule-transport results; native broker execution and point-in-time evidence are not established.

| Hybrid versus its own parent, 20 bp per leg | Additional net profit | Fewer losing sessions | Adjusted profit p |
| --- | ---: | ---: | ---: |
| Carry96 HGC_POOL | £2,948.66 | 22 | 1.00 |
| Crash90 HGC_POOL | £7,394.68 | -2 | 1.00 |

A negative fewer-losses count means more losing sessions. Carry96 hybrid requires £21,707.92 under the 40 bp capital proxy, exceeding the retained £21,195.51 limit. Crash90 hybrid remains within that proxy limit. Neither passes the original joint improvement criterion or the full 50% objective.

| Model | Long direction accuracy | Short direction accuracy |
| --- | ---: | ---: |
| Carry96 parent | 52.8414% (20838/39435) | 49.0772% (3457/7044) |
| Carry96 hybrid | 52.8439% (20839/39435) | 48.8217% (3439/7044) |
| Crash90 parent | 52.8414% (20838/39435) | 55.3191% (52/94) |
| Crash90 hybrid | 52.9225% (20870/39435) | 61.7021% (58/94) |

Direction accuracy uses the original next-close direction contract, with zero moves counted as non-wins; it is distinct from costed profitability. The short Crash90 denominator is only 94. These accuracy differences are point estimates, not adjusted statistical confirmations.

The 84 original profit/loss comparisons were retained. The known family was extended from 42,180 to 42,264 slots before fitting; the wider research family remains unclosed. Both year-bootstrap and exact year-sign-flip adjusted p-values for the primary comparisons are 1.00. Under the retained 16-year/100,000-draw design, the minimum achievable adjusted sign-flip p is 1.00 and the bootstrap minimum is 0.4226. Six sessions inside 2026 do not add independent year clusters. This is a limit of this declared confirmation procedure, not a claim that improved trading is impossible. [Resolution audit](INFERENCE_RESOLUTION.json).

## Verification and remaining minute gap

The first 3,946 daily input sessions and the earlier VIX bytes match the original source. Action and holding prefixes match all 14 original books across 3,945 pre-terminal sessions; the old final liquidation session is horizon-dependent. All six causal checks pass. Separate result readback checked scalar long/short direction counts, 42 costed cash totals, 42 paired contrasts and all 84 exact tests using all 65,536 sign assignments.

The direct IQFeed SLB request for 2008-11-28–2008-12-10 returned 230 rows, all on November 28 and December 10: **zero on December 1**. Thus the original required event-day minute price is still unavailable. Native funding/account/corporate-action inputs also remain unresolved. No completed 2007-onward native minute cash comparison or statistical confirmation is claimed. [Minute refresh coverage](MINUTE_REFRESH_COVERAGE.json).

[Updated 31-metric table](/Users/tprice/Developer/marketmaker_v2/research/candidates/directional_forecasting/full_history_shadow_vote_hybrid_20260922_v2/refresh_20260922_v1/ALL31_METRICS.csv) · [Statistical tests](/Users/tprice/Developer/marketmaker_v2/research/candidates/directional_forecasting/full_history_shadow_vote_hybrid_20260922_v2/refresh_20260922_v1/STATISTICS.json) · [Full-scope comparison summary](/Users/tprice/Developer/marketmaker_v2/research/candidates/directional_forecasting/full_history_shadow_vote_hybrid_20260922_v2/refresh_20260922_v1/COMPARISON_SUMMARY.json) · [Independent result readback](RESULT_READBACK.json)
