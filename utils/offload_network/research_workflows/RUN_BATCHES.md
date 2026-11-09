# Multi-model testing jobs and arbitrary comparisons

Package 0.5.0 adds `marketmaker.research_offload_batch.v2`. Each entry in `runs`
is one isolated native testing job containing one or more models and an explicit
set of benchmarks. Any compatible model can be a candidate in one job and a
benchmark in another. There is no frozen-model, market or comparator default.
Install the updated package on both requester and worker.

```json
{
  "schema": "marketmaker.research_offload_batch.v2",
  "submission_id": "comparison-batch-001",
  "defaults": {
    "runtime": "python",
    "capsule": {"source": "research-capsule"},
    "testing": {"through": "statistics"},
    "inputs": {
      "models": {"mode": "bundle", "source": "models"},
      "data": {"mode": "bundle", "source": "prepared-data"}
    },
    "args": ["--data", "{input.data}/cases.jsonl",
             "--criteria", "{input.data}/criteria.json",
             "--statistics-config", "{input.data}/statistics.json",
             "--checks", "--no-early-stop"]
  },
  "runs": [
    {"id": "group", "models": ["{input.models}/a.py", "{input.models}/b.py"],
     "benchmarks": ["{input.models}/c.py", "{input.models}/d.py"]},
    {"id": "head-to-head", "models": ["{input.models}/b.py"],
     "benchmarks": ["{input.models}/a.py"]},
    {"id": "reverse", "models": ["{input.models}/c.py"],
     "benchmarks": ["{input.models}/b.py"]}
  ]
}
```

Each job compares every declared candidate with every declared benchmark, under
one backend/data/measurement contract and the explicitly supplied criteria. The
example therefore requests A→C, A→D, B→C, B→D, B→A and C→B. For a sparse arbitrary
comparison graph, use separate runs with the desired groups. Models must expose
the native backend/adapter interface; incompatible populations/metrics or missing
dependencies fail rather than being coerced into a comparison.

`models` is a required nonempty array. `benchmarks` defaults to an empty array;
it can be set in defaults and replaced per run, including with `[]`. Standalone
evaluation is allowed; do not supply comparator-dependent criteria to that run.
Duplicate paths within a role or overlapping roles within one run are rejected.
The compiler owns all model/benchmark flags and model-list indirection, including
abbreviations. There is a 128-node workflow limit including producers, plus the
worker's resource/admission limits. A single group supports up to 128 models and
128 benchmarks, subject to native runtime/output limits.

## Encapsulation and dependent development jobs

All existing [data modes and preparation rules](BATCHES.md#raw-sources-and-dynamic-requirements)
apply: explicit bundled selections, registered hash-bound remote snapshots, and
producer-generated artifacts. Shared top-level `jobs` can prepare data or train
models once. Bind the resulting model tree as an input:

```json
{
  "models": ["{input.trained}/candidate.py"],
  "benchmarks": ["{input.trained}/peer.py"],
  "inputs": {"trained": {"mode": "artifact_ref", "job": "train", "output": "models"}}
}
```

The compiler adds the producer dependency. Code, learned state, configuration and
declared dependencies must all be in that output tree. Private `prepare` chains
are also supported for each run. A run cannot depend on another run's private
preparation; put shared training in a shared producer instead. The complete graph
is admitted once and continues with the requester disconnected. Failed branches
block only dependent jobs. Inside one multi-model job, native stages own individual
model failure semantics and retain their per-model records.

This does not infer arbitrary Python imports or download undeclared data. Images
must already include the required libraries; containers have no outbound network
or source/API credentials. Generated model/data dependencies are resolved after
their producer commits and are then hash-verified and mounted read-only.

## Run on this machine using the real offload service

Build the provided validation image once, or use your own approved runtime image:

```sh
docker build -f research_workflows/examples/Dockerfile.research-test -t research-offload:local research_workflows/examples
research-offload plan-batch --request batch.json --out compiled-batch
research-offload local --plan compiled-batch --dir local-run --image research-offload:local
research-offload runs --result local-run/returned
research-offload runs --result local-run/returned --run head-to-head
```

Run the Docker build from `utils/offload_network`. `local` starts a separate
loopback worker process, submits through an authenticated requester process that
then exits, reconnects to collect, verifies the delivery, and stops its owned
worker. It uses Docker, not trusted-local execution. Worker logs, configuration,
queue, submission logs, `LOCAL_RUN.json` and returned artifacts remain in the new
directory. No public tunnel or existing worker is changed. Protect its access-token.
The local helper reserves up to 1 CPU, 1 GiB RAM and 512 MiB scratch per job with
two concurrent jobs by default. Supply `--runtime-resources` and explicit object,
return and free-space limits when the workload needs different budgets.
Within a testing job, native resource arguments override the adapter's defaults:
90% of container memory for the run, one quarter for each research worker, one
native thread and a 0.01 GiB free-space reserve. Explicit `--worker-memory-gb`
therefore matters when estimating concurrency. The native resolver and Docker
still apply actual CPU/memory ceilings. Workflow-owned output locations, stage
scope and pinned-data/cache policy remain enforced.

`LOCAL_RUN.json` is written before input submission and at each controller phase.
Its timestamp and phase history distinguish upload/submission, acknowledged
submission, workflow observation, terminal execution and verified collection.
These timestamps are phase observations, not continuous worker heartbeats. A
successful submission or terminal job alone does not establish verified return
or a scientific result.

The local helper stops its owned worker after verified terminal execution, or
on failure before submission begins. If submission or later observation times
out or is interrupted, an unconfirmed worker remains alive and its recovery
coordinates are retained in `LOCAL_RUN.json`. Reconnect to that exact workflow;
do not resubmit based only on a missing acknowledgement or stale observation.
Use normal `validate`, `submit`, `collect` and `collect --partial` for managed workers.

`RUNS.json` retains every run, model/benchmark roster, preparation state, input
identity, native verdict and artifact/diagnostic paths. Full native result trees
contain each model/seed outcome, metrics, comparisons and ledgers. Collection and
the `runs` command verify the index against the immutable delivery. No results are
flattened or overwritten. ACK does not delete evidence. Inference corrections are
native per-run checks, not an automatic corrected scientific claim over all runs.

The shipped [four-node synthetic request](examples/batch/multi_model.json) works
alongside the older example: copy `examples/batch` to a new directory, pack a native
research capsule under its `research-capsule`, then plan `multi_model.json` into a
separate directory. The original v1 `candidates` schema and `CANDIDATES.json` remain
supported without changing existing delivery identities.

See the repository's [real-data candidate development exercise](../../../research/candidates/directional_forecasting/offload_treasury_ridge_development_20260910_v1/README.md)
and [run report](../../../research/candidates/directional_forecasting/offload_treasury_ridge_development_20260910_v1/RESULT.md).
The [software validation record](RUN_BATCH_VALIDATION.md) includes tests, package
checks, retained failures and archive verification.
