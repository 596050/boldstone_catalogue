# Live research queue and coordinator

The coordinator continually discovers newly scheduled plans and existing source
queue entries. It runs bounded source admission/collection processes while the
original worker owns execution, dependency ordering and resource reservations.
The read-only dashboard refreshes every three seconds and labels unavailable or
old observations. A successful execution is separate from research acceptance.

## Run and schedule

Configure the existing [source project](PROJECT_RECOVERY.md), authorized workers
and their resource/runtime profiles first. From an installed offload package:

```sh
research-offload orchestrate --config PROJECT.json --port 8766
research-offload schedule --config PROJECT.json --plan COMPILED_PLAN \
  --worker machine-a --origins ORIGINS.json
```

Open `http://127.0.0.1:8766/`. The JSON observation is `/api/queue`. Both are
loopback only, read only and require a matching local Host/Origin. Worker access
continues to require the configured bearer token; the dashboard never contains
that token. Use an authenticated private forward for access from another machine.
The coordinator does not provision a public service.

`ORIGINS.json` uses the existing mapping from each job ID to its originating
research directories. Planning and scheduling do not import or execute candidate
code. `schedule` requires a compiled `full_results` plan including every native
research evidence port. It copies and verifies the exact plan and bundled objects
into the bounded local queue before acknowledging it. The original plan can then
be unavailable. Registered immutable dataset references avoid copying large input
archives into the local scheduling allowance.

The coordinator attempts normal `enqueue` when storage permits; it never lowers
the project's free-space or size limits. Once admitted, ready jobs execute when
the worker has slots, CPU, RAM, process, scratch and execution-storage capacity.
Waiting reasons and byte shortfalls appear when the worker can be observed.
Completed results pass the existing immutable collection, origin publication and
ACK process. Existing `enqueue` entries are discovered too. Work must be supplied
as explicit plans; the coordinator does not infer experiments from folders.

## Recovery and ownership

- Source intents and queued submissions persist across coordinator restarts.
  Original source bindings, payload hashes and worker assignment cannot change
  under an existing workflow ID.
- A coordinator restart stops only its own source-service children. Worker jobs
  continue, and source reconciliation recovers lost admission/collection/ACK
  responses using the existing durable queue.
- One kernel lock permits one coordinator per source queue. Per-workflow source
  locks also fence existing independent synchronizers. Up to two source processes
  run by default; `--transfers` sets a bound of 1 to 16. Shared publication/storage
  operations retain their existing locks.
- Network/storage observations run separately from source transfers. A blocked
  observer retains its concurrency slot; it is not repeatedly duplicated. The
  UI remains responsive with stale observations. Kernel-level filesystem stalls
  still require the underlying storage to recover and can delay process shutdown.
- Transport retries use the existing configured backoff. Scientific failures are
  retained. Interrupted execution follows the project's existing bounded retry
  policy; the coordinator does not silently move jobs to another machine.

For a pre-admission intent needing operator attention:

```sh
research-offload retry-scheduled --config PROJECT.json --workflow WORKFLOW_ID
research-offload cancel-scheduled --config PROJECT.json --workflow WORKFLOW_ID
```

These commands preserve the sealed plan. After ordinary enqueue, use the existing
worker cancellation or source `retry-transfer` operations instead. Cancelled and
admitted scheduled plans currently retain their local archive copies. They count
against `max_local_state_mb`; this version does not automatically discard that
retained staging evidence. The schedule limit includes existing pending requests.

`--poll-seconds`, `--observers` and `--request-timeout` bound coordinator polling.
The source project's separate transfer timeout/backoff settings remain in force.
Worker configuration changes require a coordinator restart; new queue entries do
not. Portable CLI operation supports the existing Python platforms; install it
under an OS-appropriate supervisor for restart after login/reboot.

For a source project whose result verification delays unrelated enqueue calls,
`recovery.collection_lock_scope="separate"` uses a dedicated `collection.lock`
for shared-object collection, origin publication and acknowledgement. These
operations remain serialized; metadata enqueue retains `queue.lock`, and the
per-workflow ownership lock still prevents duplicate reconciliation. Partial
returns use the same collection lock. Outbox deletion retains its existing
object locks, enqueue references and final metadata checks.

The default remains `"queue"` for compatibility with existing source processes.
Enable `"separate"` only after upgrading every synchronizer for that project and
letting existing collection/publication work finish. Mixed lock protocols must
not service the same shared store. This option changes source coordination only;
workflow identities, inputs, execution limits, publication and ACK requirements
remain unchanged.

## Existing worker compatibility

New workers expose authenticated `GET /v2/queue` with node states, attempts,
resource use and execution-storage wait reasons. An older worker provides health
only unless an explicit local compatibility mapping is supplied:

```sh
research-offload orchestrate --config PROJECT.json \
  --local-worker machine-a=/absolute/local/worker-home/worker.json
```

This adapter accepts only a matching loopback port and matching configured token,
then opens that worker's SQLite database read only. It does not assert the
worker's startup controller code hash. An unreachable worker or blocked database
is reported as unavailable/stale; cached running states are not current progress
proof. Source and worker processes remain independently owned.

## Validation and this deployment

The focused suite covers durable scheduling, storage recovery, changed identities,
local limits, cancellation, live queue reasons, responsive UI, ownership fencing
and discovery/return of jobs scheduled after coordinator startup. The local
Docker probe also restarted the coordinator during execution: four distinct jobs
completed on attempt one, respected the comparison dependency and published four
origin records. This is actual local Docker validation, not a configured remote
host or native Windows/Linux validation.

Retained evidence and the macOS user-service deployment helper are under
`research/utility/offload_orchestrator_20260912_v1`. Its `DEPLOYMENT.json` identifies
the frozen controller, LaunchAgent and configuration. The service starts after
login and is kept alive by launchd. Updating working-tree code does not replace
its frozen runtime. Existing scientific workers and image identities are retained.
