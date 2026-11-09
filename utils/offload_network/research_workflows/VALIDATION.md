# Synthetic implementation validation — 10 September 2026

Historical 0.3.0 report. Independent candidate batching was subsequently added;
see [the 0.4.0 batch validation](BATCH_VALIDATION.md) for current results and scope.

Implementation tests passed. This is offload/software evidence, not trading
performance evidence or validation of an actual remote deployment.

## Executed checks

| Check | Result |
| --- | --- |
| Full offload regression suite: `tests v2/tests` | **339 passed, 11 skipped**, 32.59 s |
| Existing worker + new workflows, Docker/native research enabled | **75 passed**, 72.75 s |
| Installed 0.3.0 wheel, outside the checkout | Four-node simulation passed; entrypoints, runner files and example assets present |
| Installed package's Python controller inside Linux | Four-node trusted-local simulation passed inside a restricted Linux container |
| Installed CLI `init-worker → serve → plan → submit → collect → verify → resolve` | Two-node example passed using the real Docker backend; worker stopped cleanly |
| Ruff and `git diff --check` on changed code | Passed |

The two pytest suites overlap; their pass counts are not additive. The default
suite skips eight opt-in Docker/research cases and three legacy cases requiring
specific retained, non-generic model fixtures. Docker/native cases were separately
enabled and passed. The legacy model-specific fixtures were not run.

Controller: macOS/Darwin 25.6.0 arm64, Python 3.14.7. Container runtime: Linux arm64,
`python:3.12-slim`. The temporary research image preinstalled NumPy 2.2.6 and SciPy
1.15.3. The Linux-controller smoke did not test per-job Docker isolation; the
separate Docker suite did. Windows execution is covered by the configured CI matrix,
not a native Windows run in this session.

## Exercised behavior

- Bundle, registered immutable remote dataset, generated artifact inputs;
  chained/fan-out/fan-in jobs and execution with the requester disconnected.
- Source mutation after admission, deterministic packaging, duplicate submission,
  changed-ID conflicts, native candidate/benchmark/seed roster and receipt binding.
- Native generic prediction batches through metrics/statistics, with two seeds;
  whole-run versus split-stage exact metric/reproduction parity; previous gate
  receipts copied byte-for-byte. Supported and negative statistical verdicts retained.
- Collected code, data and checkpoints re-submitted to a fresh worker store and
  continued successfully without original worker filesystem paths.
- JSON, CSV, Markdown, JSONL and binary return; schema/row constraints; missing
  outputs preserve other valid evidence; failed and blocked branches remain visible.
- Durable abandoned-claim recovery, explicit interrupted retry, prior attempt
  history, dispatch crash window, cancellation versus requester polling timeout,
  and transactional aggregate-resource admission.
- Upload/download prefix resume, a >4-MiB chunked object through the authenticated
  gateway, dependency scheduling through that gateway, repeated collection, safe
  extraction, archive bombs/traversal/links, corrupt bytes and extracted-file tampering.
- Partial snapshots, selected output closure, required local ports, explicit input
  export, local byte-budget rejection and exact-delivery ACK without remote deletion.
- Docker denial of undeclared host/credential/socket access and outbound networking;
  read-only input mounts; timeout, memory, PID and scratch/output limit failures;
  terminated containers verified absent after each attempt.

No public Cloudflare tunnel, normal-DNS/TLS remote endpoint, broker connection,
real market-data acquisition or real candidate evaluation was launched. Offloaded
native stages 08–09, independent per-model/repeat sharding and multi-worker placement
remain outside this validated implementation. See [scope limits](README.md#recovery-storage-and-release-boundary).

## Reproduce

From `utils/offload_network`, in an environment with `[test,cloudflare,zstd]` extras:

```sh
python -m pytest tests v2/tests -ra
docker build -f research_workflows/examples/Dockerfile.research-test -t offload-research-tests:local research_workflows/examples
```

Then set `OFFLOAD_TEST_DOCKER=1` and
`OFFLOAD_RESEARCH_TEST_IMAGE=offload-research-tests:local` in your shell and run:

```sh
python -m pytest tests/test_ready_worker.py tests/test_research_workflows.py -ra
research-offload simulate
research-offload simulate --docker
```

The native research tests need the repository's testing framework in the checkout.
The [CI workflow](../../../.github/workflows/offload-network.yml) installs the package
on Linux/Windows/macOS and includes a separate Docker/native-research job. CI was
configured, not submitted to a remote runner in this session.

## Retained evidence and cleanup

Only source, tests, examples, guides and this compact report remain in the active
workspace. Digest
records of the temporary validation artifacts:

```text
Regression JUnit: 870da723bab8c103aaaec22462b5387452c492e9ef01f24e2583016b39cfd5e5
Docker JUnit:     04e201990a97216fe8b0e63c4d81ff0c251783ab73098cd8786d7ed2f70865ee
Tested wheel:    fdb7cd09fffaebc3b9b2b6fb0b2732f7a344808e5c7936c2a3af314714e7af70
CLI delivery:    a3b75761c29744e14b2f545eb2ede3e9106cde1331bc91c3bf99dbbd0f14a29e
```

Cleanup verified: worker/gateway threads and the CLI worker stopped; no test
containers remain; the temporary `research-offload-validation-20260910:synthetic`
image was deleted (rebuildable from the included Dockerfile). About 413 MiB of
synthetic stores, receipts, logs, build copies, wheels, a temporary virtual
environment and generated bytecode were moved to the macOS Trash as
`research-offload-validation-20260910-IPk4NO`, where they are recoverable. The
original `/private/tmp/research-offload-validation-20260910-IPk4NO` is absent.
Existing images, the pre-existing test environment, Docker VM/shared build cache,
real research data and unrelated working-tree changes were left untouched.
