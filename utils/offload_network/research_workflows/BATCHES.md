# Self-sufficient candidate batches

This guide describes the compatible v1 one-candidate-per-job format. For one or
more models per job and arbitrary comparator groups, use [v2 run batches](RUN_BATCHES.md).

`plan-batch` compiles one native `testing.py escalate` job per candidate into the
existing durable workflow queue. Each job has a separate Docker work directory,
resource reservation, input bindings, result tree and diagnostics. Repeated seeds
and benchmarks run inside that candidate's job. Failed branches do not cancel
unrelated candidates; there is no implicit fail-fast batch policy.

The requester may disconnect **after successful admission**. All code, static
inputs and registered dataset versions must already be verified on the worker;
dependent inputs are produced from that declared supply. The runtime image must
already include every needed Python/native library. Install the updated package
on both source and worker; the worker advertises `independent_candidate_batches`.

## Minimal request

```json
{
  "schema": "marketmaker.research_offload_batch.v1",
  "submission_id": "research-batch-001",
  "defaults": {
    "runtime": "research-python",
    "capsule": {"source": "research-capsule"},
    "testing": {"through": "statistics"},
    "inputs": {
      "models": {"mode": "bundle", "source": "models"},
      "design": {"mode": "bundle", "source": "design"}
    },
    "args": ["--benchmark", "{input.models}/benchmark.py",
             "--data", "{input.data}/cases.jsonl",
             "--criteria", "{input.design}/criteria.json",
             "--statistics-config", "{input.design}/statistics.json",
             "--seeds", "0", "1", "--checks", "--no-early-stop"]
  },
  "data_sources": {
    "first": {"mode": "bundle", "source": "prepared-a"},
    "second": {"mode": "bundle", "source": "prepared-b"}
  },
  "candidates": [
    {"id": "candidate-a", "model": "{input.models}/candidate_a.py",
     "inputs": {"data": {"mode": "source_ref", "source": "first"}}},
    {"id": "candidate-b", "model": "{input.models}/candidate_b.py",
     "inputs": {"data": {"mode": "source_ref", "source": "second"}},
     "resources": {"cpus": 1, "memory_mb": 1024}}
  ]
}
```

Paths in source declarations are relative to the request file. `model` and native
file arguments use input tokens or paths relative to the capsule's repository;
source-machine absolute argument paths are rejected. `--model`/`--model-list` are
compiler-owned, including abbreviated and equals forms. Each candidate has exactly
one model, but can repeat native `--benchmark`, `--data` and `--model-input` as its
backend requires. The offload layer does not choose metrics, criteria or data.

`defaults` and candidate fields combine as follows: `inputs`, `testing`, `outputs`
and `resources` merge by key, with the candidate taking precedence. Argument arrays
concatenate (defaults first), so avoid unintentionally repeating a scalar native
option. `capsule`, `runtime` and `max_attempts` may be overridden per candidate.
Shared code/data selections are snapshotted once per exact selection within a plan
and uploaded once per content digest. Unused `data_sources` entries are not read.

## Raw sources and dynamic requirements

Use the same three input mechanisms as ordinary workflows:

- Bundle explicitly selected raw files, provenance, calendars and other necessary
  dependencies using `source` and `include`. Named `source_ref` aliases may narrow
  a catalog entry's selection, never broaden an already restricted selection.
- Use `dataset_ref` with operator-registered `dataset_id`, `version` and the exact
  `object_sha256` when source bytes already exist on the external worker. This
  is an immutable snapshot, not arbitrary access to a live host directory.
- Use candidate-owned `prepare` producers to discover/select/transform required
  inputs from supplied data and earlier producer outputs. Producers can be chained;
  committed output trees become read-only inputs to the next job.

For example, add the following to a candidate and provide `selector-config`:

```json
{
  "inputs": {
    "data": {"mode": "artifact_ref", "job": "prepare", "output": "prepared"}
  },
  "prepare": [
    {
      "id": "prepare", "runtime": "research-python",
      "capsule": {"source": "preparation-code"}, "entrypoint": "prepare.py",
      "inputs": {
        "raw": {"mode": "source_ref", "source": "declared-raw-supply"},
        "selection": {"mode": "bundle", "source": "selector-config"}
      },
      "args": ["{input.raw}", "{input.selection}", "{output.prepared}"],
      "outputs": {
        "prepared": {"type": "tree", "path": "artifacts/prepared", "delivery": "remote"}
      }
    }
  ]
}
```

This is a candidate fragment, not a complete request. It names a catalog entry
`declared-raw-supply` that must be declared in the complete request. Local producer
IDs are namespaced (`candidate-a--prepare`); artifact references and dependencies
are rewritten consistently. Every declared preparation step must succeed before
that candidate starts testing. Each preparation node inherits the candidate's
capsule/runtime only when those fields are omitted; it does not inherit testing
arguments or input ports. Declare its own inputs, outputs and bounded resources.

The complete [synthetic example](examples/batch/request.json) uses two preparation
steps per candidate: choose a raw file from a selector manifest, then make native
test cases while retaining raw bytes and a source hash. It demonstrates dynamic
selection, not automatic inference of dependencies from arbitrary Python code.

Top-level `jobs` can hold shared producer/report nodes. Refer to shared producer
outputs by their global ID. Artifact inputs automatically add explicit dependency
edges during compilation. Candidate branches cannot depend on another candidate's
testing or private preparation jobs, even indirectly through a shared node.
Use an ordinary workflow for deliberately coupled scientific jobs.

An offline job cannot discover an arbitrary new IQFeed/API requirement and ask the
disconnected source to fetch it. Supply the possible immutable data universe first,
or acquire additional data in a separately authorized preparation step before
admission. Containers retain `--network=none` and receive no source, API or broker
credentials. Missing dynamic data fails that preparation and blocks its descendant
candidate; its reason and diagnostics still return. No substitutions or hidden
downloads are performed.

Include candidate imports and retained native libraries in its capsule, and all
raw-source/PIT metadata required by the backend. Pass portable relative paths in
producer-created manifests; do not embed a producer's private scratch path. Existing
prepared inputs tied to source-host absolute paths/inodes are not automatically
portable. `pack-research --include ...` remains explicit; it does not infer arbitrary
plugin imports, required source symbols or feature lookbacks.

## Submit once and return independent results

```sh
research-offload plan-batch --request batch.json --out compiled-batch
research-offload validate --plan compiled-batch --url https://YOUR-WORKER --token-file access-token
research-offload submit --plan compiled-batch --url https://YOUR-WORKER --token-file access-token
research-offload collect --workflow research-batch-001 --url https://YOUR-WORKER --token-file access-token --out returned-batch
research-offload candidates --result returned-batch
research-offload candidates --result returned-batch --candidate candidate-a
```

`plan` also recognizes the batch schema. Use `submit --out returned-batch` to wait
and collect automatically, or reconnect later and call `collect`. A nonterminal
batch needs `collect --partial` into a fresh snapshot directory; partial results do
not overwrite the final collection. A whole plan has at most 128 nodes, including
all preparation and shared jobs. Split larger independent rosters into explicit
separate submissions. Placement currently targets one worker, with concurrent jobs
bounded by that worker's aggregate CPU, RAM, PID and scratch capacity.
Admission is also subject to the operator's pending-job and object-store limits.

The compiled plan adds `BATCH_PLAN.json`. The final collection adds `CANDIDATES.json`
with every planned candidate, its testing/preparation states, attempt, errors,
resolved input identities, native verdict and per-port local paths or remote
references. The collector verifies this view against the immutable delivery; a
changed candidate label/state/path fails verification. Reports and binary/JSONL
ledgers remain in independent content-addressed output trees, indexed by candidate
ID; they are not flattened into colliding `RESULT.json` files.

`full_results` returns complete native research evidence by default. Input export is
separate: set `return_policy.include_inputs: true` only when authorized and required
for offline reproduction. This can return substantial raw data. Failed, blocked,
negative and inconclusive outcomes are retained. ACK does not delete remote evidence.

Independent statistical verdicts are **not** a multiplicity-corrected batch-family
claim. No pooling, ranking-based omission, corrected family replay or promotion is
performed. Production isolation was checked locally with Linux Docker containers;
actual remote hosts and native Windows operation still require deployment checks.
Native end-to-end batch validation reaches statistics; execution/prospective stages
and real research backends need workload-specific validation. See the
[validation record](BATCH_VALIDATION.md).

## Run the small example

Copy `examples/batch` to a new working directory named `batch-example`, then run
from the repository root with the package installed:

```sh
research-offload pack-research --repo . --out batch-example/research-capsule
research-offload plan-batch --request batch-example/request.json --out batch-example-plan
```

Submit to a worker with an approved `python` runtime containing the testing
framework's dependencies (the synthetic Dockerfile is provided). The sample uses
toy data and stops at metrics. Do not place the compiled plan inside an input
source tree. No real candidate, source acquisition, broker or deployment is launched
by planning or by the bundled example.
