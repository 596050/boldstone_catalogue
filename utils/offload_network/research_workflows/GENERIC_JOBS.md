# Generic job preparation, execution and retention

Available in `fleet-offload-orchestration` 0.6.11. These are shared lifecycle
operations, not study launchers. They work with the existing workflow DAG, batch
compiler, worker resource policy, testing adapter, source queue and collector.
No model, comparator, provider, market, date range, metric or success threshold is
chosen by this layer. A software PASS or queue acknowledgement is not a research
result or performance qualification.

Existing compiled plans, queued workflows, admitted runner identities and dated
research receipts are not rewritten. New fields are opt-in; old jobs receive no
new default fields. New plans using these features require an upgraded worker
package. Installing or restarting existing workers is a separate operator action;
preparation commands do neither. Check `capabilities` for
`python_environment_bundles`, `portable_input_documents` and
`workflow_input_budget_preflight` before submitting new-feature jobs.

## Standard process

1. Declare exact runtime wheels and/or input files, if needed.
2. Use `prepare-runtime` and `prepare-input` to create fresh verified inputs.
3. Declare those inputs in an ordinary workflow or batch request. Use `plan` or
   `plan-batch`; no custom submission script is needed.
   Planning checks every static source/output coordinate and the structural DAG
   before copying or compressing any input. Artifact references still require
   explicit dependencies. Content identity, including checkpoint compatibility,
   is rechecked after capture; a structural preflight is not a content audit.
4. `validate` checks the selected worker's inputs, resources and logical input
   budget. `submit` also performs this check automatically. Or use the existing
   durable `enqueue` path for asynchronous admission and collection.
5. The existing scheduler runs dependencies and testing gates, checks declared
   outputs and returns evidence to the declared origins. Runtime/import and path
   relocation receipts are standard job outputs.
6. Inspect completed *owned local-run* retention targets. Only an explicit
   `retain-local --execute` archives and removes the selected redundant copies.

Source acquisition and domain-specific transformations remain explicit producer
jobs/adapters. The generic layer does not infer licenses, refresh history, change
source clocks, rewrite numeric algorithms or manufacture scientific hash bindings.

## Optional isolated Python runtime

An input bundle supplies exact Python distributions without changing the worker
image or installed host packages. The request declares the entire required set,
including transitive packages, using exact versions and SHA-256-bound local wheels.
For example, `runtime-request.json`:

```json
{
  "schema": "marketmaker.python_runtime_request.v1",
  "target": {
    "python": "3.12", "implementation": "cp", "abi": "cp312",
    "platforms": ["manylinux_2_28_aarch64", "manylinux2014_aarch64"],
    "system": "Linux", "machine": "aarch64"
  },
  "requirements": {"your-distribution": "1.2.3"},
  "wheels": [{"path": "wheels/your_distribution-1.2.3-py3-none-any.whl", "sha256": "REPLACE_WITH_EXACT_64_HEX_SHA256"}],
  "imports": ["your_distribution"],
  "max_bytes": 2147483648,
  "min_free_bytes": 4294967296
}
```

The names, versions, hashes, target and budgets above are placeholders/example
choices, not defaults or recommended scientific dependencies. Wheel paths are
relative to the request file, or explicit absolute requester paths.

```sh
research-offload prepare-runtime --request runtime-request.json --out prepared-runtime
```

Preparation verifies supplied wheels, checks their expansion/count and metadata
headroom, checks free space, and invokes requester-side pip with no index, cache,
dependency resolution, bytecode compilation or source builds. The requester needs
pip; the core worker package remains stdlib-only. Target packages and `.pth` files
are not imported on the requester. Foreign-platform wheels can therefore be
prepared on macOS/Windows for a Linux worker. Fetching/approving wheels is an
explicit earlier operation, not an implicit network action of this command.

`PYTHON_RUNTIME.json` records target, distribution versions, imports and every
installed file hash. Successful preparation is `PREPARED_NOT_WORKER_VALIDATED`.
Failed installation retains `REQUEST.json`, wheels, `INSTALL.log` and
`FAILURE.json`; use a fresh destination for a corrected request.

At execution, an isolated `python -I -B` checker verifies interpreter, regular
CPython ABI, OS, CPU, exact file inventory, exact distribution versions and
declared imports. It then enables this site directory for the workload and its
ordinary Python children. Failure prevents workload invocation and produces a
`runtime_validation` output. Approved packages' `.pth`/initialization code runs
only inside job isolation. This is not a sandbox for malicious libraries.

Limits: Python imports, not arbitrary external executables or system libraries;
the selected prebuilt image still supplies the interpreter and native OS
libraries. Free-threaded CPython is not supported. Import probes do not prove
that every possible optional dependency or workload code path works. Byte and
reserve checks are pre/postflight checks, not filesystem reservations against
unrelated writers; allow installation temporary space and final object packaging.
Select only `PYTHON_RUNTIME.json` and `site-packages` as the job input to avoid
uploading retained wheel/log duplicates.

## Hash-bound inputs and path-only relocation

`prepare-input` captures arbitrary explicitly named files without changing their
bytes. Optional JSON documents declare exact strings to relocate. No schema is
guessed and no missing values, numbers, clocks, hashes or rows are recomputed.

```json
{
  "schema": "marketmaker.portable_input_request.v1",
  "files": {
    "raw/observations.bin": {"path": "/approved/source/observations.bin", "sha256": "REPLACE_WITH_EXACT_64_HEX_SHA256"},
    "original.json": {"path": "original-inputs.json", "sha256": "REPLACE_WITH_EXACT_64_HEX_SHA256"}
  },
  "documents": {
    "INPUTS.json": {"source": "original.json", "paths": {"/approved/source/observations.bin": "raw/observations.bin"}}
  },
  "max_bytes": 1073741824,
  "min_free_bytes": 4294967296
}
```

```sh
research-offload prepare-input --request input-request.json --out prepared-input
research-offload relocate-input --bundle prepared-input --out inspected-documents
```

`PORTABLE_INPUT.json` binds all captured files and the document/path maps.
Relocation verifies every captured file, creates new documents in a separate
directory, and replaces only exact declared JSON string values/keys. Every mapped
string must occur; colliding keys, nonfinite/duplicate-key JSON, changed payloads,
linked files and ambiguous output names fail closed. Original files remain intact.
`RELOCATION.json` records original/derived hashes, paths and replacement counts.

Use `documents: {}` for a raw-only bundle, and omit the job's `portable_inputs`
setting in that case. Raw files are then available at `{input.port}/files/...`.
For document relocation the input token points to the newly materialized
documents; those documents reference the original verified read-only mount.
Relocated absolute paths are local to that attempt, not reusable on another
machine. Include original inputs in the return policy if later local continuation
needs them. A domain schema whose document hash is itself embedded in other
records needs an explicitly tested adapter; this operation deliberately does not
silently reseal those scientific identities.

## Ordinary workflow/batch integration

An ordinary model-neutral producer, with no custom entrypoint bootstrap:

```json
{
  "schema": "marketmaker.research_offload_workflow.v1",
  "submission_id": "explicit-new-job-v1",
  "jobs": [{
    "id": "compute", "kind": "producer", "runtime": "python",
    "capsule": {"source": "code", "include": ["main.py"]},
    "entrypoint": "main.py",
    "inputs": {
      "libraries": {"mode": "bundle", "source": "prepared-runtime", "include": ["PYTHON_RUNTIME.json", "site-packages"]},
      "observations": {"mode": "bundle", "source": "prepared-input", "include": ["PORTABLE_INPUT.json", "files"]}
    },
    "python_environment": {"input": "libraries"},
    "portable_inputs": ["observations"],
    "args": ["{input.observations}/INPUTS.json", "{output.result}"],
    "outputs": {"result": {"type": "json", "path": "artifacts/result.json"}}
  }]
}
```

These optional settings also apply to `testing`, `testing_stage` and `report`
jobs, and to batch `defaults` or individual runs. Preparation producers declare
their own inputs/settings explicitly. Existing DAG dependencies and generated
`artifact_ref` inputs still work. `runtime_validation` and `input_relocation`
are adapter-owned mandatory output names. Checkpoint continuation binds the
environment and relocation settings as well as code, inputs, arguments and
resources; changing them requires a fresh experiment, not checkpoint reuse.

For ordinary `producer` and `report` jobs, `PYTHONPATH` contains the capsule root
and the working directory is the attempt workspace. A nested `repo/` directory
is not automatically an import root; the explicitly chosen entrypoint must
handle that layout, or packages must be captured at the capsule root. A cold
host smoke check should use the same import path from outside the source checkout,
without adding extra paths that conceal a packaging error. The final Docker test
remains required for a native-runtime claim. A verified collection can contain a
failed job and zero tests; inspect node states, native exit codes and test counts
before treating a return as successful. Failed prerequisites block dependent jobs.

### Optional publication timing

`publish --timing-output NEW_TIMING.json` records monotonic publication and
capacity-check intervals in a separate diagnostic. It does not change the returned
publication result, its identities, immutable research records, or any storage
decision. The default remains unprofiled. Capacity phases distinguish locating
the store, walking its live file tree, reading free space, and checking local
capacity. Each call retains its actual byte counts and reserve limits.

Nested intervals overlap; do not add them. The trace is bounded to 10,000 phases
and explicitly counts omitted phases. This measures the caller's control plane,
not remote model computation or physical disk latency. Failure traces retain
exception types without copying exception messages or credentials. Existing
output is refused before work; a file appearing during work is also preserved.
A timing-write failure after successful work is reported separately and must not
trigger blind resubmission. A process death or incomplete diagnostic write is not
a valid completed report. Timing does not skip repeated live capacity checks or
substitute cached store sizes. The same context-local `collect` and `phase`
helpers in `operation_timing.py` can instrument other generic operations.

The input-budget check counts the capsule and **every input alias**, even if
multiple aliases share one physical object. A known lower bound above the
operator's input cap rejects the whole workflow before any producer is started.
An unresolved producer-output upper bound above the cap is reported as unresolved,
not rejected as impossible. Final produced sizes, archives, working space and
free-space reserves still receive the existing native checks.

```sh
research-offload plan --request job.json --out plan
research-offload enqueue --config project.json --plan plan --worker YOUR_EXISTING_WORKER --origins origins.json --receipt ENQUEUED.json --lock-timeout 30
```

`--receipt` exports `marketmaker.project_enqueue_receipt.v1`, including project,
workflow/hash, worker, exact origins, object identities and stable enqueue time.
It contains no authentication token. Re-export is idempotent and does not rewrite
an existing receipt. Conflicting output files fail before enqueue. Only ownership
of the source queue lock receives this bounded retry; integrity, origin, storage
and unrelated lock failures are not hidden/retried. Without `--receipt`, existing
enqueue CLI output remains compatible. The existing queue owns admission,
reconnection, retry policy, collection and publication; do not create a second
queue or directly edit queue rows. An acknowledgement does not assert execution.

## Disposable scratch versus returned evidence

The Docker worker already supplies a writable **64 MiB `/tmp` tmpfs** inside
the memory-limited container. Use it only for bounded, disposable scratch that
does not need to survive the container. Keep declared outputs and any required
research evidence under `/work/artifacts/...` for normal collection. Do not move
price archives, replay ledgers or required audit evidence into disposable scratch
to avoid storage or verification limits.

Some test tools create convenience symlinks in their temporary directories.
For example, pytest's numbered fixture directories also have `current` links.
Putting those fixtures under `/work` causes the worker's linked-workspace guard
to refuse result access, even when every assertion passed. For a synthetic
pytest job, `--basetemp=/tmp/pytest-job` and
`--junitxml={output.tests}/TESTS.xml` keep disposable fixtures separate from the
declared report. This uses the existing worker configuration; it does not add an
SSD-backed worker or relax symlink checks. Bound scratch to the existing tmpfs
and memory allowance. A passed test log is not a successful return until the
terminal workflow and collected artifact manifests verify.

## Explicit recoverable retention of completed local runs

This command is deliberately **not** a global disk cleaner. It accepts exact
targets from an owned `research-offload local` run that was collected and stopped
cleanly. It never stops a worker, prunes containers, deletes return collections,
cleans arbitrary research folders or selects active persistent worker workspaces.
The existing source repository's archive-retention policy remains separate.

```json
{
  "schema": "marketmaker.local_retention_request.v1",
  "local_run": "/approved/local-run/LOCAL_RUN.json",
  "work_attempts": ["offload-EXACT_RECORDED_ATTEMPT_ID"],
  "objects": [],
  "max_bytes": 1073741824,
  "min_free_bytes": 4294967296
}
```

Choose real attempt directory names from that local run's `state/work`, or exact
SHA-256 object directory names in `state/workflows/objects`. Inspection validates
those choices against terminal queue ownership; it does not invent targets.

```sh
research-offload retain-local --request retention.json
research-offload retain-local --request retention.json --out /approved/separate-recovery --execute
research-offload restore-retention --record /approved/separate-recovery --attempt offload-EXACT_RECORDED_ATTEMPT_ID --out /approved/fresh-restored --max-object-mb 1024
```

The ownership lock is held throughout. The recorded PID must be inactive, all
jobs must be terminal and assigned to the recorded workflow, the final collection
must verify, and no retained Docker container may mount the selected worker tree.
Unavailable Docker/liveness information fails closed. Explicit workspaces are
hashed, archived, fully extracted into a temporary verification directory, checked
byte-for-byte, and only then retired. Interrupted retirement can resume from the
same intent and verified archive. Object compaction uses the existing exact
archive-only format. Restore never overwrites a destination.

Keep `INTENT.json`, archive files, restore-verification markers and `COMPLETED.json`
together. They are the recovery evidence. The `max_bytes` limit is per selected
tree/object, not total drive usage. Available capacity is checked before archive
and restore work; it is not reserved against unrelated writers. Logical redundant
bytes are reported separately from actual filesystem space recovered, which is
not promised. Arbitrary uncooperative external writers/open handles are outside
this worker ownership contract.

## Consolidation boundary and verification

Shared implementation lives in this package: `python_runtime.py`, `input_bundle.py`,
`execution/environment.py`, `execution/portable.py`, `input_budget.py`,
`project_queue.py`, `retention.py`, and the existing planner/scheduler/CLI.
Nothing in this lifecycle imports a dated `research/utility` launcher. Old dated
folders remain historical evidence or domain-specific research adapters; moving
or rewriting their sealed contents would change prior experiment identities.

Regression tests are in `tests/test_generic_job_lifecycle.py`,
`tests/test_python_environment.py` and `tests/test_local_retention.py`, alongside
the existing workflow/batch/queue suites. The opt-in Docker test builds a tiny
offline pure-wheel bundle, executes a generic job and child interpreter, verifies
returned evidence, and archives/restores only its synthetic local workspace:

```sh
OFFLOAD_GENERIC_DOCKER_IMAGE=sha256:YOUR_ALREADY_CACHED_IMAGE_ID python -B -m pytest tests/test_generic_job_lifecycle.py::test_generic_lifecycle_real_docker_and_recoverable_retention
```

This is infrastructure validation, not trading performance or validation on a
remote configured worker. It does not install/restart persistent workers.
