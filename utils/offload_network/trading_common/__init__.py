"""trading_common — shared mechanics for the multi-strategy IG-demo paper-trading harness.

Strategy code (oil_ig_production, kurt_range_ig_production, tesla_ig_production)
should depend on this package for everything that is NOT strategy-specific:
IG REST client/session, atomic state writes, IQFeed bar pulls, incremental EMD
caches, external-drive storage, recovery helpers, supervisor scaffolding, CLI
helpers.

Layout:
    trading_common.state           — atomic JSON/JSONL writes + process locks
    trading_common.ig.client       — IGRestClient + MockIGClient + make_client
    trading_common.ig.session      — cached IG session (CST + X-SECURITY-TOKEN)
    trading_common.ig.execution    — position reconcile (idempotent)
    trading_common.iqfeed          — bar pull wrappers + freshness checks
    trading_common.emd             — incremental EMD engine
    trading_common.data_storage    — external drive sync helpers
    trading_common.signal_table    — signal-table writer/reader contract
    trading_common.recovery        — stop_supervisor + stale-lock cleanup
    trading_common.cli             — CLI helpers shared by paper_trade entry points
    trading_common.strategy_testing — config-driven causal replay test harness
    trading_common.refresh_lane    — refresh worker PID/state/backoff/lane helpers
    trading_common.process_monitor — OS process summaries for supervisor blockers
    trading_common.cache_generation_status — distributed cache-build state renderer
    trading_common.pending_refresh — preserve-row policy during active refresh
    trading_common.statistical_rigor — reusable candidate audit statistics
    trading_common.ig_production   — shared production-candidate toolkit (atomic io,
                                     executable-signal-table contract, live controls,
                                     splice audit, funding/parity costs, bar time);
                                     new candidate dirs MUST build on this package

See trading_common/README.md for the architecture overview + migration notes.
"""
__version__ = "0.1.0"
