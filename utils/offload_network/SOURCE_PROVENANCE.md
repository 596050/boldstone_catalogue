# Source provenance

This utility was transferred from the private repository
`596050/famous-model`, directory `scripts/offload_orchestration`, at commit:

`4598664e203588e78f7cf28151f6696fb407a7f6`

Source commit date: 2026-06-17T00:21:44+01:00.

The complete orchestration directory was retained because its generic v2
sealed-job layer imports the fleet state/path and transport helpers. Generic
shared-state packages from `trading_common/cluster_state`,
`trading_common/orchestrator`, and the SQLite external queue plus its layout
and mount-health dependencies were also retained under `trading_common/`.
The live
source `hosts.json` was replaced with a disabled example inventory so copying
the code cannot accidentally target the original machines. No `.env`, SSH
keys, runtime state, logs, source data, or result data were transferred.

Destination additions are `simulator.py`, `run_simulation.py`,
`tests/test_simulated_network.py`, and generated receipts under
`simulated_network/`. Documentation and golden-test paths were mechanically
updated from `scripts/offload_orchestration` to `utils/offload_network`.

The destination subsequently added explicit Linux and macOS live-worker
support. Those additions are local adaptations, not claims about the source
commit: platform-tagged manifests, an executable POSIX bootstrap, quoted
`sh -s` SSH operations, POSIX extraction/detached launch/status/file probes,
rsync paths, atomic promotion, and guarded cleanup.

The 2026-09-09 readiness implementation added `offload_service/`, portable archive
and locking/process helpers, a packaged worker/client CLI, and regression tests.
It repaired the destination's admission snapshots, result retention/terminal
records, artifact reuse verification, extraction boundary, dependency import
paths and installed resources. These are local changes, not properties of the
upstream commit. The original validation evidence remains under `validation/`.
