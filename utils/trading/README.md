# Broker and market-data utilities

The provider integration code from `marketmaker` is organised here using local
`utils.*` imports. Run Python commands from the `marketmaker_v2` root.

Automatic marketmaker launch jobs and old startup scripts have been removed at
the user's request. Providers are stopped. The entrypoints below are for manual
use; no replacement LaunchAgent, cron job or restart supervisor is installed.
The machine cleanup record is [MACHINE_STARTUP_CLEANUP.json](MACHINE_STARTUP_CLEANUP.json).

| Directory | Contents |
| --- | --- |
| [`../iqfeed`](../iqfeed) | IQConnect startup and keepalive, Level 1 quotes, generic tick and interval downloads, daily refresh, minute-cache refresh |
| [`../ibkr`](../ibkr) | Gateway startup and singleton management, connection and installation checks, historical bars and ticks |
| [`../ig_index`](../ig_index) | REST/OAuth clients, quotes and dealing rules, positions, order submission/confirmation, dry-run-first strategy bot |
| `utils/trading` | Shared order management, broker state, market-data store, calendar, generic IBKR runtime libraries and read-only broker reconciliation |

The [migration inventory](MIGRATION.json) maps original files to their new paths,
with hashes of both versions. Imports, repository-root calculations, helper
locations and IQFeed output defaults were adjusted for this layout. Protocol,
strategy and order-handling logic is retained. No service starts on package import.
`migrate_v1.py` records the initial copy operation; the manifest additionally
records subsequent relocation edits and validation of the delivered files.

Install the dependencies into your chosen Python environment:

```sh
python3 -m pip install -r utils/trading/requirements.txt
```

Credentials are supplied through environment variables; the
[blank template](.env.example) lists the names. Startup scripts additionally
accept `MARKETMAKER_ENV_FILE` and default to the v2 root `.env`. Keep private
credentials outside the repository, or use the ignored `utils/trading/.env`.
Broker credentials were transferred to the ignored v2 root `.env`, readable
only by its owner. Startup scripts source that file; other clients can use the
same values through their process environment. Price archives remain external.

## IQFeed

```sh
python3 -m utils.iqfeed.downloader --help
python3 -m utils.iqfeed.downloader test-connection
python3 -m utils.iqfeed.downloader download-intervals --help
python3 -m utils.iqfeed.downloader download-ticks --help
python3 -m utils.iqfeed.daily_refresh --help
```

`download-intervals` defaults to genuine 60-second bars. The generic downloader
retains the tick/interval request and parsing code. Provide an existing entitled
universe CSV with `--universe-file`; default universe files are not created by
this migration. Its new default outputs are below the external data root at
`iqfeed_downloads_v2/`. `daily_refresh` retains the original shared external
daily datasets and their validation. These are data tools, not performance proof.

`utils.iqfeed.live_data.IQFeedLevel1MarketData` is the copied quote adapter.
The downloader normally connects to the existing IQConnect service. When a
startup is needed, `bash utils/iqfeed/start.sh` uses Wine/IQConnect installed
separately. Export `IQFEED_WINEPREFIX` or `WINEPREFIX` for the existing installation;
the local default is `.runtime/iqfeed/wineprefix`. The existing Wine prefix was
moved to that v2 location. Wine itself remains installed as a macOS application.
Runtime logs and the keepalive PID
live under v2 `.runtime/iqfeed`, outside source directories.

## IBKR

```sh
python3 -m utils.ibkr.preflight --help
python3 -m utils.ibkr.download_historical --help
python3 -m utils.ibkr.download_historical_ticks --help
python3 -m utils.ibkr.connection_readiness --help
```

`utils.trading.main.connect_to_ib` and
`utils.trading.order_management.OrderManagementSystem` provide the existing
connection/execution APIs. Generic order-library calls remain order-capable.
`utils/ibkr/start.sh` retains the paper gateway, IBC opt-in and duplicate-process
checks. IBC and its configuration now live in `.runtime/ibkr/ibc`; the disclaimer
helper is in `.runtime/ibkr/IBGatewayPaperDisclaimerHandler.app`. The installed
IB Gateway remains in the macOS Applications directory. Automatic recovery via
the removed LaunchAgent is disabled.

`run_ibkr.py` remains non-routing. Provider startup does not start model trading.

## IG Index

```sh
python3 -m utils.ig_index.bot --help
python3 -m utils.ig_index.bot --epic IX.D.FTSE.CFD.IP --once
```

The second command authenticates and reads IG data; order placement stays
disabled by default. The original `--live-orders` switch is retained.
`utils.ig_index.client.IGRestClient` exposes the standalone client, and
`utils.ig_index.session.IGSession` exposes the rate-limited spread-bet session.
`instruments.py` retains instrument metadata parsing and validation. Supply
account/instrument YAML paths explicitly, or configure the private files under
`utils/ig_index/config/`; previously verified dealing metadata is not assumed.
The library's mutable defaults are outside the protected model tree. These
clients provide quotes/account data; no new IG historical-price downloader
was invented as part of the copy.

## Frozen IG S&P 500 backtest

```sh
bash utils/trading/backtest_ig_sp500.sh
```

This runs the v2 testing entrypoint for Carry96 and Crash90 with the retained
static S&P 500 roster and 2007-01-01 through 2026-09-04 minute source. It selects
all 31 implemented metric rows, package/preflight checks and independent replay.
Each invocation creates fresh output and ledger paths. Its configuration is in
v2 at `research/all_research_candidates_not_harness_frameworks/frozen_ig_sp500_toshiba_20260907_v1/`.
Raw minute prices, corporate-action evidence, prepared caches, independent
verification caches and model ledgers use `/Volumes/Toshiba 2TB` exclusively.
Stock preparation uses four concurrent workers by default; the two models run
in separate workers after preparation. Override preparation concurrency with
`bash utils/trading/backtest_ig_sp500.sh --source-workers 6`.
The wrapper checks the Toshiba mount before creating output. Source/roster
metadata and small reports remain in the repository; the testing package keeps
its documented retained-code and policy dependencies in the sibling repository.
Historical index membership is not reconstructed, frozen eligibility is unchanged,
and missing prices can stop replay or leave metrics unavailable.

## Scope and checks

The copied utility packages import their shared code locally, without adding
the sibling repository to `sys.path`. Existing frozen model packages and the
separate research resolver were not edited or rerouted. Frozen model targets,
instrument configurations, runtime books and research-specific source files
retain their existing dependencies; their old installed schedules are removed.
This is the reusable integration layer, not a copy of every research experiment.

`utils.data_paths` remains v2's authority for external storage. Real data-command
imports validate that configured volume; there is no disconnected-volume fallback.

The tests use temporary data fixtures, fake brokers, and disabled network access:

```sh
python3 -B -m pytest -p no:cacheprovider utils/trading/tests
```

They check local import resolution, relocated CLI entrypoints, protocol parsing,
quote validation, order identity and existing dry-run controls. The retained
validation record does not certify live connectivity, account access, fills,
credentials, entitlement or broker performance.
