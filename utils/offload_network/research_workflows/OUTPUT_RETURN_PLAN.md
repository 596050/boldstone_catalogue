# Planned test outputs and verified return

Design supplement to [PLAN.md](PLAN.md), 10 September 2026. The implemented
output/return API and its limits are documented in [README.md](README.md).
The sections below retain the target design; illustrative proposed fields are
not the runtime schema. Use the executable examples linked in the runtime guide.

## 1. Plan the result before running the test

The planner must compile an `OUTPUT_PLAN.json` alongside `WORKFLOW.json`.
Its hash becomes part of the submitted workflow. It declares what each node
must produce, what downstream jobs require, what the source will receive, and
how delivery will be verified. An output plan describes evidence, schemas and
coverage; it never prescribes favorable metric values.

Derive outputs from the selected backend, candidate/benchmark/seed roster,
requested stages, checks, criteria, statistical design and downstream input
ports. Output collection is part of the initial capsule implementation, not
a reporting feature deferred until the final release.

The dry-run should show:

- Required output ports, schemas, native file locations and conditional outputs
  for each requested stage.
- Full retained metric definitions, units, numerator/denominator requirements,
  population/calendar identities and machine-readable verdicts.
- Artifacts required by the next remote or local job, including their transitive
  result-file dependencies rather than only a top-level JSON reference.
- Expected and maximum uncompressed bytes/file counts, archive/transfer limits,
  temporary packaging space and source-side free-space requirements. Estimates
  may be unknown; mark that explicitly and require an approved capacity budget.
- Which outputs return automatically, which remain remote, and whether the
  chosen return profile supports the requested local continuation.

No implicit truncation, omitted required ledger or reduced metric vector is
permitted to meet a transfer budget. An infeasible plan reports a capacity or
output-contract problem before execution where detectable.

## 2. Output contract

| Field | Purpose |
| --- | --- |
| `name`, `schema`, `schema_version` | Stable output port and machine-readable interpretation |
| `path` or bounded `tree` | Relative location below the approved output root; no arbitrary host path |
| `required_when`, `cardinality` | Whether the file is mandatory for successful/failed/started stages and how many entries to expect |
| `identity_constraints` | Candidate/seed/plan, measurement/population/calendar, producer and predecessor bindings |
| `validation` | Presence, format/schema, full-vector/count checks, completeness, hashes and required native verification |
| `consumers` | Declared downstream input ports; consumers add non-optional output obligations |
| `delivery` | Return to source, retain remote, or both; applicability is checked against local continuation |
| `limits`, `classification` | File/count/byte limits, authorized data scope and permitted export |
| `retention` | Keep while referenced; acknowledgement does not authorize deletion |

Stage-specific requirements are conditional. A job stopped before replay owes
its execution/failure record and any completed gate receipts, not invented
statistics. A job claiming a completed replay must contain all required replay
artifacts. Zero observations, failed criteria and missing evidence remain
explicit native outcomes.

Actual file hashes cannot be known before computation. At completion, the worker
validates the output plan and emits an `OUTPUT_MANIFEST.json` containing exact
relative filenames, lengths, hashes, port membership and dependency references.
Dynamic shard names must fit predeclared port rules and bounded counts; unknown
files do not silently enter the returned package.

Commit only after writers stop. The manifest binds the output-plan digest,
workflow/node/attempt, input and code identities, native result digest and
completeness. A missing mandatory output produces `OUTPUT_INVALID`, independently
of exit code; it cannot satisfy a downstream scientific input.

The worker, not the candidate code, creates an execution/failure envelope from
controller-observed state. Reserve a small bounded receipt budget so timeout,
OOM, cancellation or packaging failure can still be reported when the job did
not write a usable native result. Host/storage failure may delay that report;
do not claim a receipt exists until it has been durably recorded.

## 3. What returns

| Output group | Contents | Default treatment |
| --- | --- | --- |
| Control/evidence envelope | Workflow/node/attempt IDs, execution status, original receipt hashes, output inventory and collection status | Always collect when durably available, including failure-only results |
| Native test reports | `RESULT.json`, `SUMMARY.json`, Markdown/CSV tables, full defined metric vector, point/statistical verdicts | Return for every candidate and the batch; retain negative/inconclusive outcomes |
| Reproducibility and continuation | Native plans, gate receipts, replay/observation/accounting ledgers, checks, statistical and holdout artifacts, required checkpoints | Return the complete required result closure by default |
| Large producer intermediates | Prepared inputs, feature shards, generated datasets, fitted states or predictions | Keep remote for consumers; return when explicitly selected or needed for a planned local continuation |
| Diagnostics | Bounded logs, resource/progress events and partial-output inventory | Return with clear terminal/partial labels; never substitute for completed evidence |
| Original input data | Already bundled or registered datasets and code | Reference existing immutable identities; do not automatically transfer all source data back |

Return profiles:

- `full_results` (default): complete native result/evidence tree and result
  dependencies required for requested reporting and continuation.
- `summary_and_refs` (explicit): reports and receipts plus verified remote
  artifact references. Mark missing local dependencies; this is not a complete
  offline research package.
- `selected` (explicit): named output ports plus their required result dependency
  closure. Reject a selection that cannot satisfy an explicitly requested local
  continuation.

These profiles change transfer selection, not which metrics a test calculates
or which evidence qualifies it. Remote retention remains in force for every
referenced artifact. A return-profile change after execution needs a new recorded
delivery request, not an edit to the frozen computation/output plan.

Distinguish complete returned results from a package containing every original
input needed to rerun the experiment. A full result archive may still reference
a remote price dataset. Report `required_inputs_available_locally` separately.
Before a local next-stage job runs, verify all its input identities and availability;
retrieve authorized missing objects or leave it `BLOCKED_DATA`. Do not silently
substitute a locally available version.

Illustrative configuration fragment; proposed fields, not an existing CLI schema.
The 1-GiB example cap is arbitrary and must be sized for the real workload.

```json
{
  "schema": "marketmaker.research_output_plan.v1",
  "node_id": "test-candidates",
  "native_output_root": "artifacts/testing",
  "outputs": {
    "research_result": {
      "path": "artifacts/testing/RESULT.json",
      "schema": "marketmaker.progressive_gate_result.v1",
      "required_when": "native_run_returns",
      "delivery": "return_and_retain"
    },
    "research_evidence": {
      "tree": "artifacts/testing",
      "inventory": "backend_and_requested_stages",
      "validation": "complete_native_result_closure",
      "delivery": "return_and_retain"
    }
  },
  "limits": {
    "max_uncompressed_bytes": 1073741824,
    "max_files": 10000
  },
  "return_policy": {
    "profile": "full_results",
    "collection": "automatic_while_client_connected",
    "on_disconnect": "retain_until_client_reconnects",
    "delete_after_ack": false
  }
}
```

The compiler resolves the inventory rule to an explicit schema/port plan before
submission and records runtime filenames in the final manifest. Overlapping
ports reference the same stored bytes, not duplicate copies. If the native process
returns without its required result, publish the failure envelope and mark the
output contract invalid. Stages that never ran remain `NOT_RUN`.

## 4. Return protocol

Use authenticated requester-initiated downloads. The source does not need a
public address, SSH server or open inbound port; the worker does not need to
call back to its original IP. No arbitrary callback URL or destination path is
accepted from job code.

```text
Output plan bound before admission
  -> native job writes private outputs
  -> validate and commit immutable manifest/artifacts
  -> publish small result index
  -> source fetches selected artifacts
  -> verify in source-side staging
  -> publish fresh local result directory
  -> acknowledge exact delivery manifest
```

1. The connected submission client can automatically poll and collect each node
   as it finishes. After disconnection the worker keeps results; collection
   restarts when the client reconnects or the user runs `collect`. This does
   not assume a background client keeps running after its process exits.
2. Fetch the small index first, including failure-only envelopes. Resolve the
   requested return profile and missing digests. Check destination free space,
   source-side size limits and authorized scope before bulk download.
3. Initially use the existing authenticated archive download with whole-file
   retries. Add resumable immutable objects/chunks for large outputs, binding each
   resumed range to the same manifest and content digest; never combine versions.
4. Verify transport hash and length, safe extraction, every manifest file and
   every required result reference. Run the requested native result validation
   via the portable resolver. Hash agreement is not independent recomputation
   or proof of scientific correctness; record those verification levels separately.
5. Write to a private staging directory beside the selected source destination,
   then atomically publish a fresh result directory. An existing directory is
   never overwritten. Repeated collection rechecks the actual extracted files
   and manifest, not merely the retained compressed archive.
6. Write `COLLECTION_RECEIPT.json` with the output-plan/delivery-manifest hashes,
   fetched and remote-only artifact IDs, local validation results, available
   continuation inputs and all unresolved references. Preserve remote evidence
   bytes and add a separate local path-resolution index.
7. Acknowledge exactly the delivered manifest/digests after durable local storage
   and selected-contract verification. A reports-only delivery is not an ACK
   of uncollected bulk artifacts. Lost ACK responses are retried idempotently.
   ACK never deletes remote data or marks a failed research criterion as passed.

Store the collection destination in source-side client configuration, scoped to
a chosen result root, for example
`received/<workflow-id>/<node-id>/<attempt-id>/`. Never use a remote-provided
absolute path as the local destination. Consumers are explicitly wired to output
ports; collecting an archive does not automatically execute its code.

Track delivery independently of research/execution status:
`PENDING -> AVAILABLE -> TRANSFERRING -> VERIFIED_LOCAL -> ACKNOWLEDGED`.
An unavailable/corrupt/incomplete delivery gets an explicit error. A failed
experiment can have fully delivered failure evidence; a completed experiment can
still have `DELIVERY_PENDING`. Do not rerun computation just because download,
disk allocation or acknowledgement failed.

Partial results/progress can be collected while other nodes run, but are marked
nonfinal. The batch finalizer runs after all nodes are terminal, includes failed,
cancelled and blocked candidates, and publishes a final index. A partial batch
must not be labelled a complete statistical comparison.

## 5. Integration with the current code

The current [ResultSpec](../v2/manifest.py) and [runner](../v2/runner.py)
collect JSON/log patterns and `artifacts/**`; CSV, Markdown, JSONL and binary
ledgers outside that directory are not reliably included by the defaults.
For M1, put the full native output tree under `artifacts/testing/`, validate
its planned inventory and retain native relative structure. Do not return only
the top-level JSON or convert binary evidence into summary numbers.

The current [client](../offload_service/client.py) already downloads an archive,
checks length/hash and terminal identity, safely extracts into staging, publishes
without overwrite and acknowledges delivery. The [worker](../offload_service/core.py)
retains results after ACK. Reuse these mechanisms, but add:

- Mandatory output/schema/dependency validation and a durable failure-only
  envelope when no result archive exists.
- A planned output inventory and return profile, plus complete-file verification
  on repeated collection. Current repeated-download handling checks the retained
  archive, not every already-extracted file.
- Per-workflow collection, per-profile manifests/ACKs, automatic collection while
  connected, explicit remote-only references and a source-side continuation check.
- Large-artifact chunk/range resume; current archive downloads restart on retry.
  Readiness/backpressure must budget uncompressed files, archives and temporary
  copies on both machines, not just network payload bytes.

Proposed modules are `output_plan.py`, `output_manifest.py` and `collect.py`
in this subdirectory, with narrow integration in existing worker/client code.
The offload adapter interprets native results; it does not rewrite their metric
definitions, count conventions or gate/performance verdicts.

## 6. Acceptance criteria

- Dry-run lists the expected files/ports, sizes/unknowns, transfer profile and
  local next-stage requirements before any test executes.
- A supported candidate and a batch return the full native artifact tree,
  including CSV, Markdown, JSONL/compressed ledgers and binary arrays.
- A later stage consumes the returned package through the resolver without
  undeclared worker paths. Missing original inputs are reported separately;
  requesting self-contained local continuation requires their availability.
- Reject missing required files, wrong schemas, mismatched candidate/seed,
  truncated archives, path traversal, oversized outputs and altered extracted
  files on recollection. No successful-download label hides `OUTPUT_INVALID`.
- Exercise summary-only and selected profiles, shared artifact deduplication,
  remote intermediates, explicit local dependency closure and export restrictions.
- Return honest failure/timeout/cancellation/budget-exhaustion evidence without
  inventing metrics or dropping that candidate from the batch index.
- Interrupt and resume downloads and ACKs, restart the client, exhaust local
  destination space and reconnect after worker completion. Reuse existing
  computed results; no duplicate research attempts or automatic remote deletion.
- Changing return selections never changes the computed metric vector, trial
  family or comparison verdict. Collection, integrity, independent replay and
  scientific acceptance remain separate reported properties.
