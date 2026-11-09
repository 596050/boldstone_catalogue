# Research offload workflows

Opt-in uploaded-code workflows on the existing authenticated worker. One submission
contains the complete dependency graph. The worker runs ready nodes without a
connected requester, preserves their immutable outputs, and mounts verified producer
outputs read-only for dependent jobs. All production jobs run in **Linux Docker
containers**; the worker/requester Python package supports Linux, macOS and Windows.
Docker Desktop must use Linux containers on Windows/macOS.

For durable source-side queuing, restart/reconnect recovery, space-bounded shared
storage and automatic return into each originating research candidate, use the
[project queue and recovery configuration](PROJECT_RECOVERY.md). The research
tree remains authoritative; external workers outsource processing only.
See [parallel execution](PARALLEL_EXECUTION.md) for per-worker limits and assigning
independent workflows to multiple machines.
For reusable runtime preparation, verified input relocation, automatic input
budget preflight, enqueue receipts and recoverable completed-local-job retention,
use the [generic job lifecycle](GENERIC_JOBS.md), not a dated study launcher.
For continuous admission, execution monitoring and automatic result return, use
the [live queue orchestrator](ORCHESTRATOR.md). It discovers new plans without a
restart and exposes a read-only dashboard at `http://127.0.0.1:8766/`.
For bounded byte-identical JSON write measurements in an existing job runtime,
use the [generic I/O probe](IO_PROBE.md). It distinguishes raw-write overhead
from complete workflow time and never changes a running worker.

Large shared inputs are verified once per distinct object in each admission,
not once per occurrence in its dependency graph. Every dataset ID/version binding
is still checked, and there is no persistent stat-only verification cache. Each
execution verifies mounted contents before Docker creation and again after exit.
The extracted manifest is checked against the hash-bound archive header too, so
editing extracted data plus its local manifest/commit record cannot detach it
from the sealed archive identity. Per-submission admission locks let unrelated
control-plane operations proceed during long preflight reads; scheduler dispatch
and publication still have their own serialized work and are not latency-free.

## Quick start

From the repository root, install into a virtual environment:

```sh
python -m pip install "./utils/offload_network[test,cloudflare]"
research-offload simulate
research-offload simulate --docker
```

The first command uses trusted local subprocesses: **no OS sandbox**. The Docker
simulation requires an already available `python:3.12-slim` image. Both simulations
use synthetic inputs, run a four-node dependency graph, disconnect the requester,
verify returned JSON/CSV/Markdown/binary files and clean their temporary stores and
threads. `--report summary.json` retains only a small validation receipt.

On the external machine:

```sh
docker pull python:3.12-slim
research-offload init-worker --dir worker-home --image python:3.12-slim
offload-worker serve --config worker-home/worker.json
```

`init-worker` explicitly enables uploaded code in `worker.json`. Existing worker
configurations remain template-only unless a `workflows` configuration is added.
The bearer token grants operator-level workflow/code submission and object access;
this is not a multi-tenant service. Keep that token out of capsules and manifests.
The service listens on loopback. For remote access use the existing
[authenticated tunnel setup](../offload_service/README.md), adding `--tunnel` to
`serve`, or an authorized private SSH forward. Public HTTPS requires that separate
configured tunnel/service; this workflow layer does not provision a public address.
Jobs themselves have no network, Docker socket, host home, worker store or tokens.

From the source machine, using the packaged synthetic [example](examples/request.json):

```sh
research-offload plan --request utils/offload_network/research_workflows/examples/request.json --out planned-example
research-offload validate --plan planned-example --url http://127.0.0.1:8765 --token-file worker-home/access-token
research-offload submit --plan planned-example --url http://127.0.0.1:8765 --token-file worker-home/access-token --out returned-example
research-offload verify --result returned-example
research-offload resolve --result returned-example --port report.reports --relative metrics.csv
```

Replace the URL and token-file path for a remote worker. `--plan` names a compiled
directory, not its JSON file. `submit` without `--out` returns after admission;
`submit --out` waits and automatically collects final results. A disconnected or
timed-out client does not cancel computation. Resume collection later:

```sh
research-offload status --workflow example-producer-chain --url https://YOUR-WORKER --token-file access-token
research-offload collect --workflow example-producer-chain --url https://YOUR-WORKER --token-file access-token --out returned-example
```

Never reuse a submission ID for changed work. Identical resubmissions are idempotent;
changed bytes under an existing ID are rejected. Use fresh output directories.

## Inputs and capsules

`plan` snapshots only explicitly selected files, without importing candidate code
or fetching data. It writes `WORKFLOW.json`, `OUTPUT_PLAN.json`, sealed
`objects/<sha256>.tar.gz`, and local planning receipts. All remote manifests refer
to immutable object hashes, never arbitrary worker filesystem paths.

New worker output objects use `marketmaker.offload_object.v2`: each distinct
payload is stored once, with the complete original path/size/hash map retained.
Archives contain regular payload files, not extraction-time links. Restoring
creates independent regular files; logical expansion limits still count every
path. V1 objects remain readable. Upgrade source clients before workers that
produce V2; `/v2/capabilities` advertises supported object schemas. Packaging a
verified returned V2 object preserves its archive identity, including across a
checkpoint continuation on a new worker. Nested legacy report archives remain
opaque objects; their producer must select a deduplicating envelope format.

| Input mode | Request before compilation | Resolution |
| --- | --- | --- |
| Bundle | `{"mode":"bundle","source":"data","include":["cases.jsonl"]}` | Selected bytes uploaded once; hash-verified read-only mount |
| Remote reference | `{"mode":"dataset_ref","dataset_id":"prices","version":"v1","object_sha256":"<64 hex>"}` | Existing registered immutable snapshot; no data re-upload |
| Generated input | `{"mode":"artifact_ref","job":"prepare","output":"features"}` | Committed required output of an explicit `depends_on` job |
| Referenced source | `{"mode":"data_ref","source":"prices","key":"v1/prices.tar.gz","object_sha256":"<64 hex>","archive_bytes":123456}` | Worker fetches a pinned sealed object from approved filesystem, HTTPS or S3 storage before admission |

The planner's `--max-object-mb` allowance applies to source snapshots as well as
sealed object packing. Selected byte and file counts are checked before copying;
an over-budget selection is rejected before bulk I/O. Successful capture still
verifies source and copied-file hashes and retains an immutable file manifest.

Inspect sealed Python inputs as text or with an AST parser. If an inspection
must execute Python, use a separate `python -I -B` process and set
`PYTHONDONTWRITEBYTECODE=1` for any children it starts. A read-only Docker mount
does not make the origin's object directory read-only: importing there from the
host can add `__pycache__` files and invalidate the input tree after an otherwise
unchanged computation. Tree verification rejects added, missing and changed
files, reporting their counts and bounded path samples. Preserve that rejection;
inspect a separate copy when an operation needs to write files.

When an immutable file manifest already exists, `research_workflows.bound_objects.pack`
accepts its explicit `{relative_path: {bytes, sha256}}` map. It hashes the bytes
as they enter the ordinary V1 archive, without creating an expanded snapshot or
discovering unlisted files. Declared size limits are checked before bulk reads;
a hash mismatch never substitutes the current file identity. The archive remains
compatible with normal extraction, admission and collection verification. Use
`compressed.verify_archive` for an independent archive readback, then reference
the sealed object through the existing bundle `object_sha256` input. This is an
explicit option for previously declared identities; ordinary source selections
still use snapshot discovery. Failed partial archives are retained for inspection
and must not be published as sealed objects.

See [referenced data for testing stages](DATA_REFERENCES.md) for worker source
configuration, raw-file snapshot preparation, remote authentication and examples.

Register a dataset locally on the stopped worker:

```sh
research-offload register-dataset --config worker-home/worker.json --id prices --version v1 --source /operator/approved/data
```

Registration takes a one-time worker-owned snapshot and returns its digest. Later
jobs reuse it through read-only mounts; changing the operator's original directory
does not change that version. Registration is not an HTTP host-path operation.
It needs temporary/archive space in addition to the original dataset. Dataset
version remapping is rejected. Licensing and authority to export data remain the
operator's responsibility; `delivery: remote` is a transfer preference, not an ACL.

Object commits reserve the compressed copy plus the expansion declared in the
bounded, first-member `OBJECT.json`, not `max_object_mb` again for every small
result. Extraction is capped at that byte count and exact member-count bound;
the complete file manifest and archive hashes are still verified. A false small
declaration cannot bypass the storage limit. Upload staging, workspaces and
retained results also consume space, so dataset size alone is not a sufficient
store budget.

On supported macOS filesystems, the retained archive copy uses `clonefile`:
separate file identities share data blocks until either file is modified.
Other platforms and unsupported/cross-filesystem cases keep the ordinary copy
path. This does not replace archive hashing, expanded-file verification or sync,
and logical storage reservations still count the complete archive. Clone I/O
errors are retained as errors; a hard link or unexpected destination is rejected.

Capsules use `{"source":"code","include":["main.py","helpers"]}` or an already
uploaded digest. They execute a relative Python `entrypoint`, with arguments passed
as an argv array, never a shell command. `{input.port}` expands to an input directory;
`{output.port}` expands to the declared output path. File ports arrive in an input
directory under their original basename. Output parents may already exist. A job
can also read `WORKFLOW_INPUTS_JSON` and `WORKFLOW_OUTPUTS_JSON`.
`WORKFLOW_REQUEST_FILE` names the sealed request, including each dependency's
terminal state, attempt and available ports, so finalizers can report failures.

No dependencies are installed inside jobs. Select an operator-approved prebuilt
runtime image with required native libraries. Python packages can be supplied by
that image or a declared, offline-prepared `python_environment` input that is
verified before the workload starts. The image ID, input hashes and runner code
are bound at admission. Newly queued descendants retain those identities
across worker restart or a later change to an image tag. Code/data/input limits,
CPU, RAM, PID, wall-time, scratch/output size and aggregate capacity are explicit.
The scheduler admits only jobs fitting the worker-wide capacity reservation.
Worker job receipts and workflow node status expose `worker_phase` transitions:
input preparation, input verification, container creation, execution supervision,
post-execution input verification, result verification, and terminal completion.
`running` retains its capacity reservation throughout these phases. A process
exit alone does not establish verified completion. The recorded transition time
is not a heartbeat; status polling does not freshen it. Elapsed intervals use a
monotonic clock, and a restarted worker retains the previous observation without
combining clock intervals from separate worker lifetimes. Already running worker
processes acquire this reporting when they next start with the updated code.
The queue API preserves the recorded phase timestamp, and updated monitor
processes display the last worker phase separately from lifecycle state. The
legacy local compatibility observer closes its read-only SQLite connection after
every poll, including failed reads, instead of waiting for garbage collection.

When several ports name the same object, each verification boundary checks that
object once and preserves all mount paths. Admission, pre-execution, and
post-execution checks remain separate full byte verifications; a check is never
reused across those boundaries.

## Native testing candidates and batches

For **one or more models per job with arbitrary comparison groups**, use the v2
`runs` schema: [RUN_BATCHES.md](RUN_BATCHES.md). `research-offload local` exercises
the normal queued Docker service on this machine with verified result return.
For research workloads beyond the small default limits, pass
`--runtime-resources limits.json` and `--min-free-mb 4096`. For example, a limits
file can contain `{"timeout_s":7200,"memory_mb":2048,"max_input_mb":512,
"max_work_mb":1024,"max_output_mb":256}`. These limits apply to each job;
aggregate CPU, memory, PID and scratch reservations scale with `--concurrency`.
The Python `local.run` API accepts the same dictionary as `runtime_resources`.
Unspecified limits keep their existing defaults. The overall `--deadline` also
needs to cover queueing, execution and result collection.
`local` forwards an HTTP `--request-timeout` derived from the deadline and
`--max-object-mb` into `submit`; the 30-second client default cannot commit a
multi-gigabyte market object.
For an individual source or result object exceeding 256 MiB, also pass an
explicit `--max-object-mb` (Python: `max_object_mb`). This bounds both compressed
and expanded object size; job input/output limits and the storage reserve still
apply separately. The workflow object-store budget is at least 4096 MiB and
twice the declared object limit, to accommodate an archive and its extracted
tree. Collection defaults to 1024 MiB total. Set `--max-return-mb` (Python:
`max_return_mb`) for a larger explicitly budgeted return; the same bound applies
to final collection, partial collection and verification. All retained copies
still need to fit the actual filesystem.

`plan` and `plan-batch` accept `--capsule-staging-directory` (Python:
`capsule_staging_directory`) for an existing, separately budgeted directory on
a faster filesystem. Only temporary software snapshots use it. Large data
snapshots and compressed objects stay in the plan directory, and all byte/hash
checks remain enabled. The staging directory must be outside every packaged
source. Budget its space in addition to the plan directory and runtime reserve;
the option does not change those limits. Without it, staging stays under `--out`.

`--input-transport docker-volume` (Python: `input_transport="docker-volume"`)
can avoid slow host-mounted reads in Docker Desktop. The default remains `bind`.
The worker verifies each retained object, copies it into a private volume, and
hashes every copied file before mounting the volume read-only at the same job
path. Staging uses the admitted image and bounded resources. The extra copies
are normalized by a fixed helper with only the `CHOWN` capability, because Docker
can preserve private host file ownership. Uploaded code runs afterward with all
capabilities dropped and read-only input volumes. The extra copies
count against the worker store budget, with host and Docker free-space checks;
they require additional disk space. They are removed after the job or during
restart recovery, using only that worker's persisted attempt and ownership labels.
Authenticated inputs and results stay retained. The receipt records copy and
verification time separately. This is Docker-only; simulator results do not
validate it. Worker configuration uses `workflows.input_transport` for the same
option, which is fixed in each admitted job's payload.
Repeated references to the same object share one verified volume at their
separate read-only paths. The receipt lists every target and counts the physical
copy once; each declared mount still counts against the logical job input limit.

When reusing a completed worker store, a committed object with a valid
`ARCHIVE_ONLY.json` receipt can be restored from its retained archive. Admission
checks the runtime helper as well as the declared data and capsule inputs.
Restoration verifies the archive identity, manifest and extracted files, respects
the store budget and free-space reserve, and preserves the archive and original
receipt alongside `RESTORED.json`. Missing data without a valid retention receipt,
interrupted compaction, or damaged existing data fails verification. Compaction
must still happen only while that worker and its consumers are stopped.

After controller loss, `workflows.recover_completed` can explicitly list worker
job IDs whose original Docker containers have already exited. Startup holds the
worker lock, checks the original attempt, image, command, read-only inputs,
resource limits and elapsed runtime, then verifies and collects the original
result. A running container is rejected and left intact. Cancelled, unprepared,
unselected unresolved or identity-mismatched jobs cannot use this recovery path.
The original failure receipt is retained in `recoveries/<attempt>/INTENT.json`;
completion is published only after the original container and owned volumes
are removed. It creates no new submission or model execution. Omitting this
option keeps the normal interrupted-attempt recovery behavior. Actual Docker
tests in `test_finished_recovery.py` cover bind and volume result recovery after
an injected controller cleanup failure.

The opt-in native checkpoint parity tests cover both transports and the three
input modes with invented classification data. Set `OFFLOAD_RESEARCH_TEST_IMAGE`
to a prebuilt research image and select
`test_native_whole_capsule_and_portable_stage_checkpoint_parity`; adding
`-k docker-volume` selects the volume cases. Its temporary snapshot must be
outside the source repository. `test_input_volumes.py` includes separate real
Docker corruption, cancellation, shutdown and recovery cases under the same
image opt-in. These tests do not measure market performance.

For **one isolated testing job per candidate**, use the independent batch schema
and `plan-batch`: see [BATCHES.md](BATCHES.md). Each candidate can have different
data/code/configuration and a private chain of dynamic preparation producers.
All branches are admitted together; failures remain independent and collection
adds a verified `CANDIDATES.json` roster. The example below is the older alternative:
multiple models deliberately executing inside one shared native testing job.

`kind: testing` runs the capsule's existing `testing.py escalate`. It accepts the
normal model/benchmark/seed/purpose/intensity/check/statistical arguments, including
multiple `--model` entries. The adapter owns output location, final `through`,
research scope, pinned freshness and cache-off mode. It caps native processing
resources to the container allocation. There is no broker access or model promotion.

Prepare code separately, selecting candidate-specific dependencies explicitly:

```sh
research-offload pack-research --repo . --include path/to/candidate_package --out research-capsule
```

This includes testing framework code/config and materializes in-repository Python
compatibility links, recording their original targets. Other links, directory
links and out-of-tree links are rejected. It does not automatically discover all
plugin dependencies or copy real research datasets. Add required code with repeatable
`--include`; use the input ports for explicit data/configuration selections.

A node in a request can then be:

```json
{
  "id": "test-batch", "kind": "testing", "runtime": "research-python",
  "capsule": {"source": "research-capsule"},
  "testing": {"through": "statistics"},
  "inputs": {"data": {"mode": "bundle", "source": "prepared-inputs"}},
  "args": ["--model", "{input.data}/candidate_a.py",
           "--model", "{input.data}/candidate_b.py",
           "--benchmark", "{input.data}/benchmark.py",
           "--data", "{input.data}/cases.jsonl",
           "--criteria", "{input.data}/criteria.json",
           "--statistics-config", "{input.data}/statistics.json",
           "--checks", "--no-early-stop"]
}
```

Configure `research-python` in the worker's `workflows.runtimes` first. The
[test image recipe](examples/Dockerfile.research-test) covers the synthetic
prediction/statistics tests, not every real candidate/backend dependency.

The native evaluator owns counts, metric definitions, full-population checks,
comparators and scientific verdicts. The offload layer checks the returned plan,
candidate/benchmark/seed roster, gate chain, worker records and referenced artifact
hashes. `succeeded` means execution and required output contracts completed. A
research run can complete with a negative point/statistical verdict. Hash checks
are not independent recomputation, proof of causality or trading performance.

## Checkpoints and local continuation

`kind: testing_stage` runs native gates through `testing.stop_after`, writing a
JSON-only checkpoint when it stops short of the final `testing.through`. A later
testing-stage node declares a checkpoint input and `testing.resume_input` naming
that port. It uses the same capsule, final endpoint, args, resources, runtime and
data identities. Every earlier gate receipt is restored byte-for-byte into a fresh
attempt, verified, and not executed again. The requested boundary must advance.

Example continuation fields:

```json
{
  "kind": "testing_stage",
  "depends_on": ["first-stages"],
  "testing": {"through":"statistics","stop_after":"statistics","resume_input":"checkpoint"},
  "inputs": {"checkpoint":{"mode":"artifact_ref","job":"first-stages","output":"checkpoint"}}
}
```

This is a fragment: also supply the unchanged capsule, runtime, args and other
input ports. Use `stop_after: models` on `first-stages`. Checkpoints require the
canonical Linux-container `/work` layout, never pickle or a reused live workdir.
Returned checkpoint/code/data directories can be bundled into a new workflow on a
fresh worker with the same pinned runtime. The test suite exercises that round trip.

`resolve` locates verified returned files without editing their original receipts:

```sh
research-offload resolve --result returned-run --port test-batch.research_evidence --native-path /work/artifacts/testing/RESULT.json
```

It never executes returned code. Native path-bearing readers are not silently
monkey-patched on the host; native continuation runs in the canonical container.
Missing local inputs produce `BLOCKED_DATA`, not a substituted dataset version.

## Planned outputs and verified return

Each node declares required outputs below `artifacts/`: `file`, `json`, `jsonl`,
`csv`, or `tree`. Optional JSON `schema` and CSV/JSONL `rows` constraints are checked.
`requires: ["node.port"]` declares transitive output dependencies. Testing nodes
automatically return `research_result` plus the complete `research_evidence` tree
under `artifacts/testing`; intermediate stage nodes also publish `checkpoint`.

After writers stop, the controller commits an output envelope plus file manifests
and immutable objects. Missing/invalid outputs mark the node failed independently
of exit status, while preserving other valid ports and diagnostics. Timeouts,
cancellation and failed native gates retain a controller-observed failure envelope.
Blocked/failed candidates remain in the workflow's final index. Reports may use
`condition: all_terminal`, but report outputs cannot advance scientific jobs.

Return policy defaults to:

```json
{"profile":"full_results","ports":[],"include_inputs":false,"require_local":[]}
```

- `full_results`: all return-designated ports and their declared dependency closure.
- `summary_and_refs`: return-designated JSON/CSV ports, with bulk object references.
- `selected`: explicit `ports` plus their required output closure.
- `include_inputs: true`: explicitly export declared capsule/input objects too.
- `require_local: ["node.port"]`: reject selections omitting required local ports;
  if production fails, the delivery lists these missing requirements explicitly.

The complete native result tree includes CSV/Markdown, JSONL and binary ledgers;
it is not reduced to summary metrics. Content-addressed object archives deduplicate
identical objects; overlapping but nonidentical port trees are separate archives.
Byte estimates remain explicitly unknown until production. Approved hard limits
apply; output truncation is never used to turn an incomplete result into success.

Uploads and downloads resume against immutable digests and verified byte ranges.
Collection verifies archive hashes, safe extraction, every extracted file, native
result references when full evidence is selected, and local capacity before atomic
publication. It writes `DELIVERY.json`, `INDEX.json` and `COLLECTION_RECEIPT.json`.
The receipt distinguishes final/partial, remote-only data, missing local inputs,
workflow status and integrity from independent replay. ACKs bind that exact delivery
and **never delete remote data**. Recollection rechecks actual extracted files.

Use `collect --partial --out snapshot-one` for an immutable snapshot while other
nodes run; final collection needs a fresh directory. Connected `submit --out`
collects once the workflow is terminal, not an automatic per-node background daemon.

## Recovery, storage and release boundary

The worker owns its SQLite store exclusively. Ready claims and capacity admission
are transactional; launch intent is durable before queue submission. A restart
retains queued nodes and reconciles abandoned attempts. `resume` explicitly retries
only confirmed-stopped interrupted attempts within each node's `max_attempts`
(default 1, maximum 3), retaining prior attempt history. Semantic failures are not
automatically retried. `cancel` stops this workflow's jobs, not unrelated processes.
Storage pressure during publication retries publication without recomputing the job.

For a submission that may still be undergoing admission, use `revoke` with its
exact compiled `--workflow-sha256`. The worker durably reserves that workflow ID
against late admission and requests ordinary cancellation if the matching
workflow was already admitted. The record survives worker restart. Reusing its
ID, including with a different digest, is rejected; changed work needs a new ID.
`revocation` reads back that record after a lost response. Check ordinary workflow
and native-job status separately to establish that execution stopped. Source
verification already in progress can finish before the admission is rejected.
An absent workflow response or a stopped source submitter does not revoke a request.
These commands require a worker advertising `durable_admission_revocation: true`;
the client does not fall back to an ordinary cancellation or an assumed success.

```sh
research-offload revoke --workflow example-producer-chain --workflow-sha256 EXACT_COMPILED_SHA256 --url https://YOUR-WORKER --token-file access-token
research-offload revocation --workflow example-producer-chain --url https://YOUR-WORKER --token-file access-token
```

Worker artifacts, attempts and registrations are retained after completion/ACK.
There is no automatic worker garbage collection; size the stores and archive/remove only explicitly
selected, no-longer-referenced workflows under operator control. The simulation's
temporary-directory cleanup is separate from production retention.

Implemented: M0–M3 manifest planning, complete capsules, three input modes, resumable
transfers, durable single-worker DAG scheduling, output planning/collection; plus
canonical stage checkpoints and the release CLI/tests. Remaining design milestones:

- Independent per-candidate whole-run batches are implemented, including private
  preparation chains and independent returned results. Per-seed/repeat replay
  sharding and corrected full-family statistical assembly remain unimplemented;
  those are not implied by collecting separate candidate results together.
- A workflow has one worker; automatic multi-worker placement/replication is future work.
- Offloaded native parity is tested through metrics/statistics. Stages 08–09 and
  real market datasets still need workload-specific validation before use.
- Existing native prepared bundles with absolute paths, inode/mtime snapshots or
  undeclared external dependencies are not automatically portable. Provide portable
  raw/relative data or an explicit preparation package; do not edit signed receipts
  to make an incompatible source appear verified.
- Native Windows/macOS/Linux CI is configured; local validation here is macOS plus
  Linux containers, not evidence of a live remote host or public-tunnel deployment.

See [RUN_BATCH_VALIDATION.md](RUN_BATCH_VALIDATION.md) for the 0.5.0 multi-model and
real-data development checks, [BATCH_VALIDATION.md](BATCH_VALIDATION.md) for 0.4.0,
and [VALIDATION.md](VALIDATION.md) for the earlier workflow validation.
The original [implementation plan](PLAN.md) and [output design](OUTPUT_RETURN_PLAN.md)
remain as the broader target, not an assertion that deferred milestones are complete.
