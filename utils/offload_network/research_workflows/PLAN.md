# Research offload workflow plan

Status: implementation added on 10 September 2026. See [the runtime guide](README.md)
for the actual CLI/schema, implemented milestones and remaining limits. The design
below is retained as the original target, not a claim that every release criterion
or future milestone has been completed. Testing-stage development remains active;
capsules bind their exact selected source bytes at submission.

## 1. Outcome and recommended shape

Add an artifact-based workflow layer in `utils/offload_network/research_workflows/`
over the existing isolated `offload_service`. A workflow accepts one candidate
or a frozen candidate list, its testing configuration, and a graph of dependent
jobs. The external worker accepts the complete graph once, queues ready jobs,
executes each in its own container, and retains verified outputs for downstream
jobs and eventual collection by the source machine.

Support three composable input modes:

| Mode | What is sent | What the job receives |
| --- | --- | --- |
| `bundle` | Required files, code and configuration, with sizes and hashes | A sealed read-only input tree, independent of the source machine |
| `dataset_ref` | Registered dataset ID, immutable version/digest and declared selection | A verified read-only worker-local snapshot; no bulk retransmission |
| `artifact_ref` | Upstream job/output name, then its committed artifact identity | Verified output from a self-contained producer job, mounted read-only |

These are per-input choices, not three incompatible workflow types. For example:
send candidate code and small configs, reference a large remote price snapshot,
run a feature-building package there, and pass its output to the testing stages.
A fully self-contained generator may have no data inputs if that is genuinely
its contract; generated or synthetic observations never become raw market data.

Keep evaluation, accounting, criteria and stage decisions in the existing
testing framework. This is an execution/data-transfer integration, not another
evaluator or a new predictive mechanism.

The first useful release should support a producer chain followed by one complete
`escalate` job containing one or many candidates. Distributing individual testing
stages is a subsequent milestone requiring explicit checkpoint interfaces.

Plan outputs as well as inputs before submission: compile an `OUTPUT_PLAN.json`
defining required reports, ledgers, schemas, downstream consumers and the return
policy. Complete capture and verified return belong to the first capsule release.
See [planned outputs and return](OUTPUT_RETURN_PLAN.md) for the detailed contract.

## 2. What exists and what must be added

| Existing component | Reuse | Gap for this request |
| --- | --- | --- |
| [HTTP worker](../offload_service/core.py) and [API](../offload_service/http_api.py) | Durable SQLite queue, attempt fencing, isolated Docker execution, configured limits, authenticated requests, result receipts | Requests currently select worker-owned templates only. No uploaded candidate capsules, workflow DAG or dataset/artifact mounts |
| [Sealing](../v2/seal.py) and [safe extraction](../v2/safe_archive.py) | Hashes, bounded archives, rejection of links/traversal and unsafe members | Resumable content-addressed transfers and reusable immutable artifact storage |
| [SSH batch executor](../v2/batch.py) and [specs](../v2/spec.py) | Dependency validation, host affinity, parallelism policies and dependency tests as prior implementation | SSH-specific, topological-layer scheduling and remote workdir references; not the HTTP service's isolation or durable DAG authority |
| [Progressive runner](../../../research/testing_stages/runtime/escalation.py) | Ordered stages 00–09 and predecessor-bound gate receipts | Uses an in-memory state dictionary and a fresh output directory; no public stage checkpoint/resume API |
| [Generic evaluator](../../../research/testing_stages/runtime/experiment.py) | Candidate lists, benchmarks, seeds, repeats, declared checks and verified caches | Path-bearing plans/results need portable resolution; externally computed per-model results need a supported assembler |
| [Source registry](../../../research/testing_stages/docs/CENTRAL_SOURCES.md) | Central source IDs, universes, immutable preparation receipts | Worker-specific physical mappings and verified immutable dataset registrations |
| [Resource controls](../../../research/testing_stages/docs/PARALLEL_PROCESSING.md) | Model/repeat/source/statistical worker budgets and deterministic scheduling | Host-wide admission across multiple offload jobs, respecting container allocations |

Important existing boundaries:

- Configured HTTP inputs must already exist on the worker and are currently
  copied into every admitted seal. That is not yet zero-copy dataset reference.
- SSH `remote_refs` are paths into retained upstream workdirs, not published,
  typed artifacts. Do not mount one job's writable workdir into another.
- The legacy batch's stale-heartbeat retry and cleanup behavior must not be
  carried into the isolated service unchanged. A lost connection is not proof
  that the old attempt stopped; result retention must remain explicit.
- Current research stages 08–09 implement simulated execution and a historical
  forward holdout. Deployment/broker/future-observation evidence is a separate
  workflow and is excluded from this implementation's default authority.

## 3. Workflow model

Example target graph; each box is an isolated job, not a shared process:

```text
Bundled inputs / registered immutable remote snapshot
                         |
                  prepare source
                         |
               produce features / inputs
                         |
            bind complete experiment and trial family
                         |
               required stage prerequisites
                         |
          +--------------+--------------+
          |              |              |
     benchmark(s)    candidate A    candidate B ... N
          |              |              |
          +--------------+--------------+
                         |
             verify and assemble full replay
                         |
               metrics -> comparison -> statistics
                         |
              simulated execution -> forward holdout
                         |
             verify export -> collect on source
```

Initially, the complete testing portion is one `escalate` capsule. Later the
replay fan-out and stage boundaries become independent jobs without changing
their evaluator semantics.

Rules:

1. Freeze the ordered candidate/benchmark/seed roster and testing design before
   scoring. A batch directory or model-list file is resolved to explicit entries;
   later file additions cannot silently join a running experiment.
2. Every input edge names an output port and expected schema/identity constraints.
   Reject cycles, unknown producers, conflicting roles and incompatible inputs
   before admission. Bind dynamic output hashes when producers commit.
3. A job becomes ready when its own prerequisites are verified, without waiting
   for unrelated jobs in a topological layer. Run independent branches within
   the host budget; stateful histories remain chronological.
4. Shared deterministic preprocessing runs once per exact input/code/parameter
   identity. Learned preprocessing is scoped to its legal training fold, label
   maturity, model and seed; never fit shared features on the evaluation suffix.
5. Benchmark-first ordering is mandatory when candidate early rejection needs
   its measured thresholds. Full replays can overlap when early stopping is
   disabled. Retain all required comparator results.
6. A bad artifact or failed prerequisite blocks descendants, not independent
   branches. A final batch report still records every planned candidate.
   Computation edges require eligible verified outputs; report-only finalizers
   can explicitly use an `all_terminal` condition to include failed branches.
   That exception cannot authorize a downstream scientific gate.
7. Paired statistics use the complete predeclared hypothesis/trial family and
   aligned ledgers. Do not compute separate candidate p-values and call their
   concatenation a corrected batch comparison. Missing required members make
   that family unevaluable unless the original design explicitly handles them.
8. All inputs needed for an admitted offline workflow must be on the worker or
   obtainable from its declared producers. The source can disconnect after the
   admission receipt; no callback to a requester-local path is required.

## 4. Contracts to implement

Use versioned JSON schemas and reject unknown operational fields. Human labels
are not content identities.

| Contract | Required information |
| --- | --- |
| `WorkflowSpec` | Schema, client submission ID, candidate roster, research purpose/intensity, backend, requested endpoint/checks, criteria/statistics/holdout configs, DAG, retention and bounded retry policy |
| `JobSpec` | Node ID, kind, approved capsule/template/runtime, inputs/outputs, dependencies, resource request, timeout, seed, eligibility and retry rules |
| `InputSpec` | Logical mount name; bundle/dataset/artifact source; digest and schema; declared population, coverage and clocks where relevant; no requester-selected host path |
| `OutputPlan` / `OutputSpec` | Required and conditional output ports, schemas, full metric/evidence obligations, consumers, size limits and return/retention policy bound before execution |
| `ArtifactManifest` | Artifact type/schema, producer job and attempt, file hashes/sizes, upstream identities, population/calendar/contract IDs, completeness, availability and verification status |
| `ExecutionReceipt` | Workflow/node/attempt IDs, committed spec and input hashes, image/platform/dependencies, timestamps, exit/termination reason, resource usage, output manifest digest |
| `StageCheckpoint` | Original plan and gate-plan identities, completed gate/receipt chain, explicit serialized state, artifact references, supported continuation stage and checkpoint-schema version |
| `CollectionReceipt` | Output-plan/delivery-manifest hashes, delivered and remote-only artifacts, validation and continuation readiness, local retention and scoped acknowledgement; original remote evidence stays unchanged |

Keep three distinct identity layers:

- Logical experiment identity: selected models, common measurement/criteria,
  exact data and code, seeds, fitting/availability rules and statistical family.
- Submission/execution identity: workflow run, node, attempt, image/platform,
  allocation and concrete resolved paths.
- Artifact identity: immutable bytes plus their typed provenance manifest.

Transport mode alone should not change the logical experiment when the consumed
bytes and semantics are identical. It must remain visible in execution receipts.
Changed datasets, preparation/model code, scientific options or image/runtime
identity invalidate affected reuse; do not erase old records or manufacture
matching current `plan_id` values.

Illustrative request fragment below is a proposed schema, not runnable today.
The compiler supplies real digests, approved runtime details, resource limits
and the complete frozen testing configuration.

```json
{
  "schema": "marketmaker.research_offload_workflow.v1",
  "submission_id": "example-batch-001",
  "workflow": "research",
  "jobs": [
    {
      "id": "make-inputs",
      "kind": "producer",
      "capsule": "feature-builder-v1",
      "inputs": {
        "prices": {
          "mode": "dataset_ref",
          "dataset_id": "example-price-snapshot",
          "version": "immutable-version",
          "manifest_sha256": "REQUIRED_REAL_SHA256"
        },
        "settings": {
          "mode": "bundle",
          "object_sha256": "REQUIRED_REAL_SHA256"
        }
      },
      "outputs": {
        "features": {"schema": "example.features.v1"}
      }
    },
    {
      "id": "test-candidates",
      "kind": "testing_workflow",
      "capsule": "testing-adapter-v1",
      "depends_on": ["make-inputs"],
      "inputs": {
        "candidate_package": {
          "mode": "bundle",
          "object_sha256": "REQUIRED_REAL_SHA256"
        },
        "features": {
          "mode": "artifact_ref",
          "job": "make-inputs",
          "output": "features",
          "schema": "example.features.v1"
        }
      },
      "testing": {
        "command": "escalate",
        "through": "statistics",
        "configuration": "candidate_package/testing-request.json"
      },
      "outputs": {
        "research_result": {"schema": "marketmaker.progressive_gate_result.v1"}
      }
    }
  ]
}
```

The example feature schema needs a real adapter accepted by the selected
backend. A file called `features.json` is not automatically valid testing input.
Additional producers can feed either job, forming arbitrary validated DAGs.

## 5. Data and code packaging

### Bundled inputs

- Build a minimal capsule from declared model/backend imports, retained
  dependencies, configurations and required data partitions. Include constructor
  history and auxiliary feature symbols even when they lie outside scored dates
  or the traded roster. Do not infer required inputs from only successful reads.
- Preserve source provenance, PIT membership, missingness, price basis, publication,
  observation, fit, model-availability and event clocks. Include preparation
  receipts, calendars, corporate actions and any declared FX/funding inputs.
- Package from immutable snapshots. Detect concurrent changes while inventorying;
  refuse inconsistent multi-file sources or live database copies.
- Existing testing compatibility paths include symlinks. Resolve only declared,
  allowlisted repository links at build time and emit regular files with recorded
  source/target hashes; keep archive extraction's no-links rule.
- Include a pinned prebuilt Linux image with Python/native dependencies, or
  reference one already installed by the operator. Do not assume that a Python
  source archive contains NumPy, SciPy or retained sibling-repository libraries.
  No package installation or image building inside research jobs.
- Add a separate bounded streaming object-upload protocol. Do not put large
  files/base64 inside the current 64-KiB job JSON API. Support resumable fixed-size
  chunks, total-size limits, digests, quarantine and atomic finalization.
- Deduplicate by content digest within the authorized namespace; upload only
  missing objects. A job is not runnable until every required object is verified.
  Start with resumable result archives; add selective large-artifact downloads.

### Worker-local dataset references

- Extend the existing central source-ID approach. An operator maps a dataset
  ID/version to an allowed physical snapshot on each worker. Users submit logical
  identities and declared partitions, never arbitrary host filesystem paths.
- Verify the immutable manifest and required partition hashes before admission/use.
  Record the complete universe/calendar/coverage even when a physical partition
  selection reduces I/O. No silent intersection, shorter history or source fallback.
- Mount only declared data read-only. A read-only container mount does not stop
  another host process changing the source: require an immutable snapshot or
  registered lock/snapshot mechanism. Reject mutable/unverifiable registrations.
- A missing version waits for explicitly authorized transfer or reports
  `BLOCKED_DATA`; it never switches to another vintage or downloads automatically.
- Retain provenance identity separately from host location. Existing Toshiba
  mount checks still protect acquisition on that source host; remote copies get
  their own storage mapping, not fabricated Toshiba hardware credentials.

### Self-contained producer jobs

- Each producer has a code capsule, pinned runtime, explicit input/output schemas
  and parameters. Examples: source normalization, lawful feature generation,
  fold-scoped fitting, model export, prediction generation, or input-format conversion.
- Write outputs only to the attempt's private directory. Verify schema, file
  hashes, expected rows/calendar, completeness and required clock evidence;
  publish into the immutable artifact store only after the process tree stops.
- Downstream jobs see only committed outputs through read-only mounts. They never
  consume partially written files or the producer's writable scratch directory.
- Numerical fitted state requires an explicit serializer/schema. Do not unpickle
  uploaded checkpoints in the controller or worker daemon. Any approved executable
  deserialization stays inside the isolated job.
- Data acquisition requiring provider access is a separate authorized preparation
  action. The worker control plane may transfer declared objects; research
  containers retain network isolation and receive no provider/broker credentials.

## 6. Testing-stage integration

Use `research/testing_stages/testing.py escalate`, not a direct `test` success,
to claim that requested stages ran. Do not imply that `--through statistics`
also completed stages 08–09.

| Boundary | Integration |
| --- | --- |
| Before stage 00 | Resolve latest completed session once, acquire/prepare if explicitly requested, freeze sources and bind the complete design |
| 00 Contracts | Run the existing comparator, metric and backtest-period validation |
| 01 Data | Verify capsule/dataset/generated-input bindings and existing source checks |
| 02 Models | Resolve adapters and dependencies inside the isolated runtime |
| 03 Causality | Run supported prechecks; producer and fitted-state clocks remain part of the evidence |
| 04 Replay | Initially retain existing internal scheduling; later distribute model/seed/repeat units and use a validated result assembler |
| 05 Metrics | Verify the complete vector, observation counts, artifacts and independent checks using current code |
| 06 Comparison | Preserve separate point verdicts; a completed negative research comparison can proceed |
| 07 Statistics | Consume complete aligned ledgers, the prebound family and shared paired resampling design |
| 08 Execution | Existing independent simulation validation; no orders, broker mutation or credential access |
| 09 Prospective | Existing historical holdout with explicit exposure, inherited portfolio, full suffix metrics/statistics and prebound forward design |

Portability work is essential:

- `experiment.plan()` currently calls source preparation, which may refresh data.
  A new offload dry-run must not call that default path as a supposedly read-only
  inspection. Separate static planning from explicit acquisition and isolated
  plugin description; report unresolved dependencies without starting downloads.
- Seal a concrete cutoff. Execute remote research against pinned prepared inputs,
  preserving the original acquisition receipt. Do not resolve `latest` independently
  on different nodes, or use `pinned` to conceal an already-stale requested dataset.
- Keep current full-history floors for trading: daily execution starts
  2011-01-03, minute execution 2007-01-03. These follow execution cadence, not
  feature cadence; unrelated generic domains retain their explicit contracts.
- Plans, model dependencies, gate bindings and result references currently carry
  absolute paths, including retained sibling-repository references. Introduce
  an explicit logical artifact resolver and a canonical container layout.
  Preserve original signed/hash-bound bytes and a relocation map; never rewrite
  sealed receipts or strip path/identity checks to make a comparison pass.
- Validate imports without access to the source checkout, user home or undeclared
  sibling files. Stage code includes POSIX facilities; Windows/macOS hosts run
  Linux containers, not native Windows research subprocesses. Pin actual image
  platform/architecture; cross-architecture equality is a tested property.
- Keep original remote receipts intact on collection. Revalidation occurs through
  the resolver or in an isolated verifier with the original logical layout; local
  summaries are derived artifacts, not replacements for the original evidence.

For stage-granular execution, add supported `export_checkpoint`,
`verify_checkpoint` and `continue_from_checkpoint` interfaces to the existing
runner. Serialize only declared state and artifact references; bind all previous
gate receipts. Continuing uses a new attempt directory. No edited `RUN.lock`,
shared output tree, skipped gate or arbitrary pickle-based state restoration.
Parallel replay children are not independent passes of gate 04: its parent gate
passes only after the complete required population and fresh-process repeats
are assembled and verified.

## 7. Durable scheduling and failure semantics

One worker-side workflow coordinator owns graph transitions in the existing
private SQLite store. Containers execute tasks only and never receive the
Docker socket. Avoid a nested Docker orchestrator capsule.

Proposed node lifecycle:

```text
WAITING_INPUTS -> READY -> RUNNING -> VERIFYING -> SUCCEEDED
                         |             |
                         +-------------+-> FAILED / INTERRUPTED / CANCELLED
upstream cannot qualify ----------------> BLOCKED_DEPENDENCY
```

Persist the graph, resolved input hashes, claims, attempt IDs, resource reservations,
events and committed outputs. Transactional publication makes output eligibility
and downstream readiness agree. A crash before commit leaves outputs quarantined;
after commit, a restart discovers the same artifact without duplicate publication.

- Resend an uncertain submission with the same submission ID and identical spec;
  changed content under that ID is a conflict. Poll before creating another attempt.
- A stopped requester is not a cancelled workflow. A polling deadline never kills
  the remote job. Report disconnection separately from execution state.
- Retry only predeclared retryable infrastructure failures after confirming the
  previous attempt has stopped. Keep new attempt IDs and all old evidence. Do
  not retry semantic rejection, bad input, unsupported checks or criteria failure.
- Current worker restart behavior stops owned containers and marks running jobs
  interrupted. Build reconciliation on that behavior; no exactly-once claim for
  arbitrary side effects. Fail closed when termination cannot be established.
- Cancellation is scoped to this workflow's queued/running attempts. Never kill
  unrelated work or delete source data. Keep interrupted logs and partial evidence.
- Track execution status, output completeness, gate status, point/statistical
  verdicts and overall research qualification separately. `BUDGET_EXHAUSTED`,
  `NOT_EVALUABLE` and exact early `REJECTED` are not full-population success.
- Research-negative but complete outputs remain available for statistics and
  reporting when existing gates allow it. Missing/failed scientific gates cannot
  be turned into passes because the container exited successfully.

The adapter retains the native command's exit code and result verbatim. In
particular, exit code 2 can accompany a research rejection, budget exhaustion
or invalid evidence; it must be classified from the verified result, not treated
uniformly as a retryable infrastructure failure. Producing a valid negative-result
artifact is distinct from qualifying that artifact for a later computation.

Retain unchanged finite-population optimistic-bound early rejection. For full
statistics/holdout workflows require complete replays; an early-rejected prefix
is preserved but cannot feed complete-population downstream stages.

## 8. Isolation, resource allocation and access

Preserve existing non-root containers, read-only code/inputs/image, disabled
network, capability restrictions, CPU/RAM/PID/time limits and per-attempt scratch.
New dataset/artifact mounts expose only explicitly authorized read-only inputs.

Uploaded code expands today's operator-owned-template trust boundary. Add an
opt-in capsule-submission policy and approved runtime/adapter profiles; preserve
the existing template-only API unchanged by default. Never permit submitted
Docker options, arbitrary host mounts, host commands or privilege escalation.
Hash matching proves identity, not that code is safe or scientifically causal.

Start with one owner/trusted research team. Current tokens share one namespace;
multi-tenant authorization would be separate work. Authenticate uploads, workflow
control, artifact reads and cancellation consistently. Keep tokens out of
capsules, URLs, logs and result archives.

The host scheduler reserves aggregate memory, CPU, scratch/output space, PIDs
and I/O slots before claiming each job. Pass explicit allocations into the current
testing resource controls; do not let every job independently assume half the
host's RAM. Account for model workers, repeats and native numerical threads
inside the same allocation. Large source parsing and statistics need separate
bounded I/O/batch allowances.

Advertise worker architecture, installed image identities, dataset versions and
available capacity. Initial workflows run on one external worker, keeping large
artifacts local. Later fleet placement can prefer data-local workers; cross-worker
edges transfer only verified immutable artifacts, with no implicit host fallback.

Container and sampled output limits are not an adversarial hard filesystem quota
or a proof against kernel exploits. Require quota-backed scratch or a stronger
host boundary before claiming those guarantees. An operator-authorized dataset
inside a capsule is visible to its code: job isolation does not by itself enforce
label secrecy within that capsule. Stronger untrusted-model causality needs
separate scorer/feature processes and restricted data channels, outside this MVP.

## 9. Results, cache and retention

The [output and return plan](OUTPUT_RETURN_PLAN.md) specifies advance output
planning, automatic collection while connected, retained results on disconnect,
return profiles and separate execution/research/delivery statuses. A test can
finish remotely while delivery remains pending; a failed test can still return
complete failure evidence.

Keep the native output tree and required referenced artifacts: `PLAN.json`,
`GATE_PLAN.json`, ordered `GATE.json` receipts, `RESULT.json`, `SUMMARY.json`,
full metric tables, replay/observation/accounting ledgers, checks, statistics,
holdout evidence and logs as applicable. A CSV or headline score alone cannot
serve as input to later stages.

Return a workflow index joining candidate/node/attempt identities, input modes,
artifact hashes, stage progress, completed/expected population, point/statistical
verdicts, resource use and all failure reasons. Preserve the existing
`helped`, `hurt`, `mixed`, `inconclusive` and `blocked` research observations
where supplied; do not invent findings from infrastructure outcomes.

Collection verifies archives and referenced files into a fresh staging directory,
then atomically publishes a local index after verification. It never overwrites
the candidate source, existing research runs, frozen models or a live run's lock.
Only the source-side research workflow owns any explicit result registration;
the remote job cannot promote models, update canonical research status or trade.

Separate content deduplication from evaluation-cache reuse. The latter retains
the existing requirement for complete repeated fresh-process reproduction and
exact declared dependency/runtime/artifact identities. Record cache provenance;
a cache hit is neither new independent evidence nor a new research trial.

Keep producer artifacts while any queued/running downstream job or retained
result needs them. Acknowledgement means verified delivery, not deletion. Start
with explicit retention/export and no automatic garbage collection. Any later
cleanup requires reference checks, a declared policy and recoverable evidence.
Capacity exhaustion pauses/rejects admission rather than deleting required inputs.

## 10. Implementation sequence

| Milestone | Deliverable and likely files | Exit criterion |
| --- | --- | --- |
| M0: contracts and dry-run | New `research_workflows/spec.py`, `planner.py`, `output_plan.py`, schemas and examples | A frozen candidate or model list compiles to an explicit DAG/input/output inventory and return budget; unknown dependencies and unsafe plans fail without acquisition or job submission |
| M1: portable testing capsule and return | `capsule.py`, `testing_adapter.py`, `output_manifest.py`, `collect.py`, image/dependency recipe; narrow resolver integration | One complete candidate/batch `escalate` capsule reproduces locally/remotely; the full native tree returns with verified output completeness, failure evidence and a collection receipt |
| M2: all input modes and large artifacts | `artifacts.py`, `datasets.py`, `offload_service` upload/mount support and producer adapter; resumable large-result objects | Same fixture runs with bundled, remote and generated inputs; return profiles and large transfers retain identical data semantics and verified receipts |
| M3: autonomous dependent queue | `scheduler.py`, worker-store migration, workflow API and event/status client | Upload a producer -> producer -> multi-candidate testing graph once; disconnect source; worker finishes dependencies, retains outputs and delivers the complete batch index on reconnection |
| M4: stage and replay distribution | `stage_adapter.py`; checkpoint interfaces in `runtime/escalation.py` / `gate_support.py`; verified replay assembler integrated with `runtime/scheduling.py` | Split-stage/model/repeat execution reproduces the unsplit gated run, receipt chain and full-family statistics without skipped or repeated completed gates |
| M5: hardening and release | `cli.py`, package discovery/entry points, docs, tests and CI | Cross-platform host tests, full recovery/security/resource matrix, installed-wheel smoke, normal-network authorized remote round trip and explicit remaining deployment limits |
| Later: multi-worker placement | Capability/data-aware coordinator and artifact replication | Cross-worker edges and coordinator restart preserve ownership, identities and exactly one committed result per logical node |

M0–M3 deliver the requested dependent-job workflow using complete testing
capsules. M4 provides finer-grained distributed testing without making it a
prerequisite for useful offloading. Start with a synthetic generic fixture,
then a supported pinned research fixture; use real large-source candidates only
after the same contracts pass portability and parity checks.

Future user interface, not existing commands:

```sh
research-offload plan --request request.json --out planned-run
research-offload validate --plan planned-run/WORKFLOW.json --worker external-01
research-offload submit --plan planned-run/WORKFLOW.json --worker external-01
research-offload status --workflow WORKFLOW_ID --worker external-01
research-offload resume --workflow WORKFLOW_ID --worker external-01
research-offload collect --workflow WORKFLOW_ID --worker external-01 --out received-run
```

`plan` performs static compilation; code-importing preflight runs only in an
isolated validation job. `resume` first reconciles remote state and only schedules
policy-authorized retries after termination checks. Client worker profiles hold
endpoint/token-file references, never credentials in the workflow manifest.

## 11. Acceptance tests

Release requires all applicable checks, not just a passing demo:

1. Single candidate, multi-candidate list, mixed input modes and a chain with
   at least two producers; fan-out/fan-in, independent failure branches and
   admission/resource backpressure.
2. All three modes consume the same declared bytes and reproduce full metric
   vectors, counts, actions, ledgers and verdicts against the unsplit local
   capsule. Use exact equality for identities/counts; any numerical tolerance
   must be predeclared and may not change acceptance thresholds.
3. Exercise every supported requested endpoint; a supported all-ten-stage
   research fixture preserves prebound statistics and historical holdout state.
   Unsupported backend/stage combinations remain explicit, not fake passes.
4. Test that attempted access to another attempt, host home, worker token,
   Docker socket or undeclared dataset is denied. Test traversal, symlinks,
   archive bombs, oversized files,
   Windows path aliases, unsafe checkpoints and invalid image/mount requests.
5. Missing/changed remote dataset; changed code, config, dependencies or image;
   corrupt/truncated transfer; schema/calendar/clock mismatch; stale sources.
   Every affected cache or dependent job fails closed without changing evidence.
6. Future-suffix mutation, training-label maturity, fold isolation and prefix
   replay equivalence. Retain missing-price masks, forecast/execution clocks,
   portfolio continuity, all seeds and the predeclared statistical family.
7. Drop a submission response, disconnect the requester, interrupt an upload,
   restart the worker during execution/output publication, and cancel a branch.
   Verify idempotent admission, fenced publication, bounded retries and safe
   reconciliation when the old process cannot be confirmed stopped.
8. Exhaust RAM, scratch capacity, output size, PID and time budgets; include
   simultaneous jobs with nested numerical workers. No unrelated process or
   dataset is touched; partial outputs never satisfy complete-replay gates.
9. Collect twice, interrupt collection, acknowledge, then verify retained output
   and extracted files still support every downstream reference and original
   receipt hash. Cover all [output/return acceptance tests](OUTPUT_RETURN_PLAN.md#6-acceptance-criteria),
   including missing binary ledgers, failure-only envelopes and local continuation.
10. Installed requester/worker support on Linux, Windows and macOS with Linux
    containers; architecture-specific image tests and clean-checkout imports.
    Public deployment additionally needs normal DNS/TLS/authentication and a
    stable configured endpoint. A test-only DNS override is not that validation.

## 12. Scope and handoff

Defaults: generic models, explicit purpose/intensity and optional benchmarks;
`workflow=research`; one external worker per workflow; mixed input modes;
offline isolated jobs; original evaluator and research contracts; no automatic
promotion, broker orders, source mutation or destructive cleanup.

When the frozen-pair 50% objective is explicitly selected, carry its entire
current contract and evidence requirements unchanged. Diagnostic arithmetic,
transport integrity, cache hits and workflow completion do not establish it.
Historical holdouts are not future prospective evidence.

Implementation can begin with M0 without selecting real market data or a worker.
Actual execution needs an authorized endpoint/runtime, selected candidate list,
testing design and datasets the user is permitted to transfer. Dataset licenses,
size/capacity and export restrictions must be checked before data leaves its
current machine.
