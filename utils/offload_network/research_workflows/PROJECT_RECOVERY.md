# Research remains local; workers outsource processing

Use the project queue for unattended research batches. The older `submit --out`
and `local --dir` commands remain explicit low-level collection tools: they do not
infer a candidate's origin or turn themselves into a background return service.

The source-owned [project.json](project.json) is the central requester policy.
It uses the existing `data_paths.json` `testing_ledgers` registry and its actual
volume/UUID/marker checks. No data path registry, candidate, framework, lessons
catalog or historical receipt is rewritten. Existing research remains usable.

## Location and identity

Each testing job has one or more explicitly declared origin directories. A
multi-model comparison can be filed under every participating candidate, without
copying its full evidence for each model. The mapping is frozen with the workflow
hash and worker identity before sending anything. Remote code cannot supply local
write destinations. Only existing canonical candidate directories (or explicitly
selected retained legacy candidates) are accepted; traversal and symlinks fail.

```text
research/candidates/<family>/<candidate>/
  model.py, DESIGN.json, README.md, existing runs ...    unchanged
  offload_runs/<workflow>/<node>/<delivery-sha256>/
    RESULT.md                 short explanation and evidence-access command
    RUN_RESULT.json           roles, outcomes, inputs, dependencies, attempt history
    PUBLICATION.json          local record hashes and immutable delivery identity

testing_ledgers/offload/       resolved through the existing central data registry
  REPOSITORY.json
  outbox/<object-sha256>.tar.gz
  objects/<object-sha256>/     shared verified archive, manifest, retention receipt
  collections/<workflow>/<delivery-sha256>/
    DELIVERY.json, INDEX.json, RUNS.json, COLLECTION_RECEIPT.json, OBJECT_STORE.json

utils/offload_network/.source-state/     small ignored source-local SQLite queue
  queue.sqlite3, submissions/<workflow>/ENQUEUED.json
  read-cache/<object-sha256>/  bounded, verified on-demand file views
```

`RUN_RESULT.json` preserves failed, interrupted, inconclusive and blocked outcomes,
not just completed successful executions. It includes exact native gate summaries;
full metrics, ledgers, code, input manifests and original path-bearing receipts are
readable through the verified central collection. No automatic model promotion,
performance reinterpretation, or rewriting of accumulated lessons is performed.

## Return finished nodes while siblings run

Worker 0.6.10 sizes result-publication reservations from the archive's bounded
expanded contents instead of the runtime's maximum output allowance. Member
validation and extraction share the same limits; every object ingest still checks
storage use and the free-space reserve. A real capacity failure keeps the completed
execution available for publication retry without rerunning its model.

Worker 0.6.8 also keeps live storage scans and job sealing outside the shared
workflow control lock. Cancellation and dependency identities are checked in the
same database transactions that reserve a job and make it runnable. Cancellation
during preparation cannot launch the job later, including when preparation itself
fails. These changes do not weaken content hashes or capacity checks. They require
a worker upgrade; a source-only upgrade cannot alter an already running worker.
Filesystem calls may still be slow, and a pending request is not proof of failure.

Source 0.6.9 also keeps observational preflight/capacity scans outside the global
storage lock. Each workflow retains its own synchronization lock; unrelated
admission and status polling can proceed while another source process scans or
collects evidence. Result collection, publication and cleanup remain serialized,
with unchanged capacity and content verification. Outbox staging now uses the
separate publication boundary described below.
This change requires restarting/upgrading the source watcher, not a busy worker.

Set `recovery.collect_completed_nodes` to `true` on the source to enable early
publication; omission or `false` preserves final-only collection. A node and all
its dependencies must be terminal before its local record is published. This
includes failed, blocked and exhausted-interrupted outcomes, not just successes.
Running siblings remain queued/running and the source workflow remains pending.

Each partial delivery is pinned by manifest hash in the durable source queue
before downloading. A connection or source-process interruption resumes that
exact snapshot, even if the worker has since completed more jobs. The normal
archive/file verification and storage limits apply. Identical archives occupy
one shared central object store; only small immutable snapshot indexes and
origin records are added. No partial ACK or outbox release is sent.

The final delivery is still verified, published to every declared origin and
acknowledged through the normal recovery path. A completed job can therefore
have both an early and final snapshot directory: the same workflow/node/attempt
identifies one research trial, not two. Older records and native receipts are
never rewritten. This is a source-side feature and works with workers already
supporting `/snapshot`; it does not require restarting a busy worker.
An execution success does not imply predictive improvement.

## Configure and use

The checked-in project config deliberately has **no active worker endpoints or
credentials**. Add an authorized worker to its `workers` object, for example:

```json
{"external-one": {"url": "https://YOUR-WORKER-HOST",
                  "token_file": "/PRIVATE/PATH/access-token"}}
```

Token contents are never put into the plan, capsules or candidate result records.
Keep token files out of version control. HTTPS is mandatory except for loopback
HTTP. Each request retains the original worker endpoint; editing the config does
not silently reassign already-admitted work. A replacement deployment must retain
its durable worker state and immutable identities.

Each batch request uses `return_policy: {"profile":"full_results"}`. Add
`"include_inputs":true` when a complete return of code and input data is wanted.
Leave it false to avoid downloading large registered datasets already retained
elsewhere; their exact object/version references remain in the workflow. This does
not claim that all replay inputs are locally available. Source-bundled archives
remain pinned in the shared outbox unless an identical verified object is retained
in the shared returned store. Return-designated outputs and declared dependency closure
are collected. Ports explicitly marked `delivery: remote` remain remote-only unless
selected through that closure; this is recorded, never described as local evidence.
For complete reproducibility, mark every required producer output for return too.
The input copies that actually exist are retained; a failed producer cannot supply
an input that was never created.

Create an origins JSON file. These are **compiled testing job IDs**, not worker
attempt IDs or absolute worker paths:

```json
{
  "group": ["research/candidates/directional_forecasting/YOUR_CANDIDATE"],
  "head-to-head": ["research/candidates/directional_forecasting/YOUR_CANDIDATE",
                   "research/candidates/directional_forecasting/YOUR_OTHER_CANDIDATE"]
}
```

Map every testing node, including failure controls. Shared producers can also be
mapped explicitly; each testing record already references its dependency ancestry.

```sh
research-offload plan-batch --request REQUEST.json --out PLANNED \
  --project-config utils/offload_network/research_workflows/project.json
research-offload enqueue --config utils/offload_network/research_workflows/project.json \
  --plan PLANNED --worker external-one --origins ORIGINS.json
research-offload sync --config utils/offload_network/research_workflows/project.json --watch
research-offload queue --config utils/offload_network/research_workflows/project.json
```

`enqueue` is local and can succeed while the worker is offline. It copies and
verifies required bundle/capsule archives into the shared durable outbox, then
commits source identities and the queue row. After that, the original plan/source
directories are not needed to finish submission. Explicit `dataset_ref` versions
still require the exact registered remote dataset; there is no substitute fetch.

Archive copying and hashing run outside the source queue lock. Concurrent copies
of one object own separate, exclusively created temporary files. A short lock for
that object publishes the first verified copy; later copies verify and reuse it
without replacing its inode. Copying, hashing and fsync do not hold that lock.
Failed or interrupted copies remain inspectable as uniquely named `.copying`
files; only a successful attempt's redundant copy is removed. This prevents
competing enqueues from renaming each other's temporary file.

Before staging, each enqueue registers its required archive identities under the
source queue lock and keeps a unique OS ownership lock until commit or failure.
Cleanup preserves references whose ownership lock is held and never waits for
that lock. After a source process exits, cleanup can acquire its released lock
and reclaim the stale reference without a PID guess or time expiry. The normal
verified-retention rules still govern archive deletion. Malformed or linked
reference records stop cleanup; small ownership lock files alone do not pin data.
This protects the interval between staging and source queue commit while allowing
unrelated work to proceed. A staging or fingerprint error never acknowledges an
enqueue.

All source processes sharing cleanup must use this lifetime-reference protocol.
An older source watcher does not read these references; complete a verified
normal source shutdown or idle handoff before mixing versions. This does not
require a Docker Desktop restart or an interruption of a worker's model job.

The planner's `--project-config` freezes the central default of **two attempts**
(initial execution plus one interruption retry). An explicit per-job `max_attempts`
wins. Old plans are not mutated: a sealed `max_attempts: 1` remains one attempt.
The workflow format's absolute maximum is three attempts. Semantic model failures,
failed gates, ordinary exceptions and timeouts are not automatic retry targets.

`sync` without `--watch` performs one pass. `--now` skips the persisted reconnect
delay once, but not integrity errors. After repairing an integrity/configuration
problem, `retry-transfer --config PROJECT.json --workflow ID` clears its hold;
it never changes the worker, workflow identity, sealed attempt limit or model code.

Source synchronization uses an OS-released **per-workflow ownership lock** during
network admission, polling and interruption reconciliation. Slow remote checks
do not hold the global local-storage lock, so another source process can enqueue
new work or resolve an already-returned research record. Multiple supervised
`sync --watch` processes may service different workflows; they skip a workflow
already owned by another synchronizer. Each process makes one network operation
at a time; the number of supervised processes bounds source transfer concurrency.
Result collection, materialization, shared-object updates and publication remain
globally serialized to preserve their space budgets and retention invariants.

From 0.6.5, `sync --workflow ID --watch` services only an explicit existing
workflow; repeat `--workflow` to select several. The Python API is
`queue.sync(workflows=[ID, ...])`. This lets a bounded watcher serve a small job
on another worker without first entering an unrelated long admission. The entire
selector is validated before any work, duplicates/unknown IDs fail, and an empty
API list is a no-op. Backoff, per-workflow ownership, origin binding and global
storage fencing are unchanged. This is explicit routing, not automatic worker
failover, priority scheduling or an unbounded background thread pool.

A successfully observed remote admission is committed locally before subsequent
network requests, including delivery retrieval. A later timeout must not erase
that fence and permit a silently recreated job. Stop all older source synchronizers
before upgrading from 0.6.2 or earlier; do not mix source-locking versions against
one queue. Worker protocol identities and frozen workflow manifests are unchanged.

## Interruption and recovery behavior

The owned `research_workflows local` launcher retries transient **GET status
observations** within its existing monotonic polling budget. Each socket timeout
is capped by the remaining budget; this is not a hard wall-time guarantee for a
streaming HTTP body. Authentication, malformed-response and workflow-identity
errors remain explicit. Submission and cancellation are never retried by this
status loop. Recent observation errors and their count are retained.

After submission may have begun, a lost acknowledgement, status error or observer
deadline does not authorize terminating the worker. A still-live owned worker is
recorded as `OBSERVATION_INCOMPLETE_WORKER_PRESERVED`, with its PID, URL, exact
workflow identity, config and token-file path in `LOCAL_RUN.json`. Reconnect to
that worker and poll/collect the same workflow. A missing worker process requires
inspection of its retained state and native attempt; it does not authorize a
blind replay. Normal worker cleanup still occurs before submission or after the
matching terminal workflow has been confirmed, including a later collection
failure. These changes apply to newly started controllers; existing controllers
are not upgraded or restarted in place.

| Event | Behavior |
| --- | --- |
| Connection fails before admission | Source request stays queued; uploads resume by immutable object digest and retained offset. |
| Worker admits a batch but the reply is lost | Source queries the same ID first; matching submission is reused, not duplicated. |
| Source shuts down after enqueue | Local SQLite and shared outbox survive. Restart `sync`; no memory-only queue is required. |
| Source disappears after remote admission | Worker continues the complete admitted dependency graph and retains results. |
| Worker shuts down | Its SQLite queue and immutable objects remain. On service restart, abandoned containers are stopped/fenced; queued work continues. |
| A running attempt was interrupted | Source reconciliation asks the worker to retry only after confirmed termination and only within the sealed attempt limit. This requires source reconnection. |
| Cancellation was requested before worker restart | From 0.6.4, the cancellation remains terminal after the old container is fenced; source collection proceeds without attempting to resume the cancelled workflow. |
| Result transfer stops | Verified objects are reused and a retained partial archive resumes using HTTP byte ranges and immutable hash checks. |
| Crash during upload initialization/commit | Empty unbound starts are reconciled; verified commits finish removal of their exact redundant staging copies. Ambiguous/corrupt bytes are retained for inspection. |
| Crash after a complete result download | The hash-bound prefix or deterministic `.receiving` stage remains reusable without transferring the payload again. Finalization does not duplicate the archive. |
| Source dies while filing candidate records | Already committed records are verified; incomplete publications resume. Existing records are never overwritten. |
| ACK reply is lost | Verified local collection and every origin record remain; ACK is retried without recomputing. |
| Toshiba/origin directory is unavailable, or storage is full | Queue waits with a recorded storage reason. No shadow directory, substituted data, truncation or silent result deletion. |
| Worker reports a different identity, loses an admitted workflow, or local evidence is corrupt | `needs_attention`; restore the exact state or investigate. It is not blindly rerun on another worker. |
| Machine/disk is permanently lost | This is not replicated high availability. Restore queue/object backups or explicitly authorize a new submission; unreplicated data may be unrecoverable. |

The software does **not** install a login/startup task. To resume unattended after
an OS reboot, run `sync --watch` under a source supervisor and `offload-worker serve`
under a worker supervisor, with the same persistent paths, user and image store.
Use a user LaunchAgent on macOS, systemd on Linux, or Task Scheduler/service on
Windows. Docker must be available before the worker starts; Docker Desktop
commonly needs an interactive user session. An ephemeral Quick Tunnel hostname is
not a stable recovery address: use a stable authenticated endpoint/private forward.

There is no heartbeat-based automatic reassignment to another worker. Loss of
contact cannot distinguish a dead worker from a still-running partitioned worker.
Moving work without confirmed termination could duplicate scientific attempts.
For portable stage jobs, only a **committed** stage checkpoint can be resumed; an
arbitrary half-executed model fit is not automatically checkpointable.

Version 0.6.4 also checks cancellation and shutdown between preparation, mount
verification, container creation and process launch. If both are requested, a
durable cancellation takes precedence over retryable interruption. A filesystem
read already in progress can still delay reaching a check; cancellation is not a
claim of instantaneous I/O interruption. Results already verified as completed
are not rewritten by a later cancellation request.

Version 0.6.6 separates serialized DAG preparation from the HTTP control lock.
Slow input preparation and output packing no longer hold cancellation, new
admission or delivery requests behind the whole scheduler tick. Before queueing,
the coordinator rechecks durable cancellation, attempt and dependency identities;
cancellation also covers an intended job ID not yet present in the job queue.
Input-size accounting uses the bounded declared manifest only for its capacity
estimate. This is **not content verification**: full tree/archive checks remain
at admission, before execution, after execution, and on downloads. No persistent
hash cache or stat-only execution authorization is introduced. Cancellation can
be acknowledged during a slow read, but completion still waits for the worker's
existing safe boundary and confirmed process/container termination.

## Central defaults and space efficiency

Current source defaults in `project.json`:

| Setting | Value |
| --- | --- |
| Pending workflows | 128 |
| Poll interval / request timeout | 10 s / 30 s |
| Reconnect delay | Exponential, 5–300 s, bounded jitter; transient outages are never discarded by retry count |
| Default execution attempt budget at planning | 2, only confirmed interruptions eligible |
| Bulk repository limit / free-space floor | 100 GiB / 4 GiB |
| Per-collection archive + extracted-data limit | 8 GiB |
| Source queue metadata limit / local free-space floor | 256 MiB / 1 GiB |
| Automatic cleanup | Redundant outbox archives after verified publication and ACK; expanded shared copies only when exact compressed archives are verified; evidence stays |

Identical objects are shared across batches, candidates, retries and imports.
Shared collections contain small indices pointing to one verified object store;
they use neither symlinks nor hardlinks. Every reuse rechecks hashes. Different
overlapping trees are still different objects: this is object-level deduplication,
not block-level deduplication. Source shared collections retain compressed archives
and verify every archived file without permanently expanding them. This avoids
exFAT's large allocation overhead for thousands of tiny source/receipt files.
Native result verification uses temporary views that are cleaned automatically.
`origin --relative ...` materializes just the requested file/subtree into the bounded
source-local read cache; it does not need to expand an entire code/data capsule.
Returned bytes and hashes are unchanged. The read cache counts toward the 256 MiB
local-state budget and is not silently evicted while readers may be using it.
Standalone low-level collections and worker runtime objects remain expanded.
In a compressed shared collection, retained `INDEX.json`/`local_directory` entries
describe the original expanded layout, not permanently present directories. Use
the `origin` resolver for a real readable path; it verifies the compressed object
and creates the requested bounded view without rewriting those retained indices.

Budget checks count logical stored bytes and pending transfer estimates; active
work is additionally bounded by each worker's `worker.json` queue, concurrency,
resource and storage limits. These are admission/free-space guards, **not filesystem
quotas** or guarantees against unrelated writers filling a disk. Worker resource
approval remains local to each machine; the source cannot override it.
New `init-worker` configurations admit up to 512 pending nodes so a complete
128-node graph fits. Existing workers keep their configured limits unchanged.

Worker ACKs still never delete data. Completed remote evidence and nonredundant
source evidence are not automatically aged out. Capacity pressure pauses work
until the operator expands storage or deliberately archives verified, no-longer-
needed evidence. Back up source queue metadata and the central object repository;
copying only a shared collection's tiny index is not a backup of its artifacts.

## Read or adopt already returned evidence

```sh
research-offload origin --config PROJECT.json --record CANDIDATE/offload_runs/WORKFLOW/NODE/HASH \
  --port NODE.research_evidence --relative RESULT.json

research-offload publish --config PROJECT.json --result EXISTING_VERIFIED_COLLECTION \
  --origins ORIGINS.json
```

`origin` verifies and resolves without executing returned code. `publish` explicitly
adopts an older collection into the shared repository and appends origin records;
it neither submits nor re-runs jobs. It leaves the original collection/receipts
unchanged and sends no remote ACK. This is useful for existing offload results,
including the retained genuine Treasury model-development test.
