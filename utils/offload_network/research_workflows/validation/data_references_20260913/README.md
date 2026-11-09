# Referenced testing data — implementation and live validation

Implemented `data_ref` in offload package 0.6.12, including individual jobs,
testing/testing_stage inputs, batch data-source aliases, input-budget accounting,
worker-side acquisition, retained resolution receipts and returned manifests.
Existing bundle, registered dataset and upstream-artifact contracts are unchanged.

See [the reference contract and examples](../../DATA_REFERENCES.md).

## Final release

Wheel SHA-256:
`1d87ee4f512c8a846a20a0f46cdf2533cc1048bad49a140e7701fba9613c0a2a`.

The release was installed in separate retained environments on both machines:

- Mini: `/Users/tomprice/marketmaker-offload/runtime-0.6.12`.
- Source: `utils/offload_network/.source-state/data-reference-source-0.6.12/venv`.

The Mini's old environment and the source's exact old controller snapshot remain
available for rollback. The Mini was verified idle before restarting. The source
coordinator restarted on port 8766 with the same project configuration and was
verified running without a coordinator error. The persistent Mini endpoint
remains behind the original private SSH forward on source port 18765.

No queued job definitions, dataset versions, source credentials, worker source
profiles or project worker registrations were changed. Zero worker jobs were
cancelled. The source's new coordinator now understands reference-based jobs;
the actual price archive's approved location still needs to be configured.
The primary Mini worker currently advertises an empty `data_reference_sources`.

S3's optional host SDK was also installed on the Mini (boto3/botocore 1.43.93).
No AWS/S3 account credentials were read or configured and no live bucket was
contacted during validation.

## Checks performed

- Final focused regression: **127 passed, 12 skipped**. Includes old workflows,
  batches, multi-model runs, input budgets and planning, plus reference tests.
  The skips are opt-in Docker cases in that local suite, not claimed passes.
- New reference tests: **38 passed, 1 skipped**, included in the count above.
  Covers real filesystem and authenticated local HTTPS transfers, SHA/size and
  manifest verification, TLS, redirects, authentication failures, resume with
  and without Range support, cache reuse/corruption, concurrency, safe paths,
  native testing stages, and SDK-stubbed S3 versioning/ranges/errors.
- Separate source queue/collection regression: **49 passed** (overlaps some
  input/planning tests above; do not add counts as unique tests).
- Final wheel modules were byte-compared with their source implementation.
- Installed source CLI `prepare-data-reference` reproduced the live test's exact
  object hash and byte count from the returned raw files.
- `git diff --check` passed.

JUnit for the final focused run is retained at
`utils/offload_network/.source-state/data-reference-validation-20260913-v1/regression.xml`.

## Final-wheel live Mini test

`LIVE_RESULT.json` is the final-release run, not a simulator or mocked SSH test.
The source host served an authenticated HTTPS snapshot on loopback. A private
SSH reverse forward let the Mini fetch it from the source host. Its fresh worker
store had no cached dataset. The Mini verified the pinned archive and manifest,
ran native testing through **statistics** in an ARM64 Docker container, and
returned the inputs, native evidence and results for source-side verification.

- Dataset: 100 synthetic cases, not market prices.
- Native result: `REQUESTED_GATES_PASSED`; all requested stages ran.
- Acquisition: `provider=https`, `cache_hit=false`, `location_accessed=true`.
- Container backend: `docker`; job inputs remained read-only and network-disabled.
- Collection: final, archive and file manifests verified, required inputs retained.
- Delivery SHA-256:
  `4ee97d01a3c5fbeed91d20cec2fc7b2f1ff3275ee0345c0c0a03afd1dad1ee30`.

Temporary smoke workers, HTTPS servers and smoke-only SSH forwards were stopped.
Their data, manifests and results remain inspectable under
`utils/offload_network/.source-state/data-reference-live-20260913-v2/result-release`
and the Mini's separate smoke directory. The normal worker and dashboard remain
running. Nothing here establishes model profitability, real-price replay,
point-in-time source qualification or a live S3 deployment.

The first harness attempts exposed a test-helper import error and a capsule
staging-inside-checkout rejection. Both harness issues were corrected before
the passing runs. Earlier retained attempts and the pre-release wheel remain
separate; the published `LIVE_RESULT.json` uses the final release runtime.

## Current operational commands

On this source machine, use the new installed CLI:

```sh
utils/offload_network/.source-state/data-reference-source-0.6.12/venv/bin/research-offload --help
```

If the Mini worker needs a later controlled idle restart, use
`/Users/tomprice/marketmaker-offload/runtime-0.6.12/bin/offload-worker`,
`DOCKER_CONTEXT=colima-marketmaker`, and its unchanged
`/Users/tomprice/marketmaker-offload/worker/worker.json`.
The earlier `venv/bin/offload-worker` is retained version 0.6.11, not the current
entrypoint. These are background processes, not new reboot/login services.

`upgrade_mini.py` and `upgrade_source.py` are one-time, identity-checked deployment
receipts/scripts, not arbitrary repeated restart commands. Do not rerun them
over their retained target directories.
