# Offload network readiness implementation — 2026-09-09

The configured Docker-worker workflow is implemented and its end-to-end path
passes local and public-HTTPS synthetic tests. It is available in its own
`offload_service/` package, with an authenticated worker, requester CLI and
optional single-command Cloudflare launcher. Real workloads still require the
operator to configure their templates/data and prebuilt Linux job image.

**Deployment qualifications:** normal Quick Tunnel DNS resolution failed on
this machine. The public job test passed using a test-client-only edge-IP
override with TLS hostname verification enabled. Native Windows and native Linux
controller CI has been added but has not run remotely. The actual controller
tests ran on macOS; actual isolated workloads ran in Linux Docker containers.
No persistent worker/tunnel or production-data deployment was left running.

## Deliverables

- [Setup, configuration, API and operations guide](../../offload_service/README.md).
- [Installable 0.2.0 wheel](fleet_offload_orchestration-0.2.0-py3-none-any.whl).
- [Core/v2 JUnit receipt](SUITE.xml): **303 passed, 3 skipped**.
- Cloudflare tests: **22 passed**; SSH tunnel tests: **4 passed**.
- Total primary automated checks: **329 passed, 3 skipped**.
- [Python 3.12 repeat](PYTHON312.xml): **31 readiness tests passed**, including
  archive policy, Docker isolation/timeout/recovery, and the authenticated gateway.
- [Installed-wheel CLI round trip](INSTALLED_SMOKE.json): authentication,
  idempotent queue admission, actual Docker execution, hash-verified result and ACK.
- [Public HTTPS job round trip](PUBLIC_HTTPS.json): the same lifecycle through
  Cloudflare, using an explicit test-client DNS override.
- Retained negatives: [normal DNS failure](PUBLIC_DNS_FAILURE.json) and
  [initial edge propagation failure](PUBLIC_INITIAL_PROPAGATION_FAILURE.json).
  Adding bounded propagation retries made the subsequent edge test pass after
  one retry; it did **not** resolve the separate local DNS problem.

Three skipped upstream scenarios still require famous-model-specific fixtures.
They are not generic worker failures and were not converted into artificial passes.

## Audit findings addressed

| Previous gap | Implemented behavior / boundary |
| --- | --- |
| Result-transfer failure deleted remote evidence | SSH cleanup is conditional on successful verified retention. HTTP results are retained even after ACK; failed downloads can be retried. |
| Working-directory separation mistaken for isolation; timeout descendants survive | Default service execution uses a separate restricted Docker container. Timeout/cancellation removes the whole container before releasing the claim. The simulator/trusted-local/legacy SSH paths remain explicitly trusted-code tools, not sandboxes. |
| Python 3.12 archive escape | Streaming, bounded regular-files/directories-only extraction rejects links, traversal, device/sparse members, duplicate paths and overwrites independently of tarfile defaults. Python 3.12 and 3.14 regressions pass. |
| Queue order, duplicates, claim races and stuck restarts | Service SQLite sequence ordering, conflict-safe idempotency, transactional claims, unique attempts, store ownership lock and startup container reconciliation. Interrupted jobs are not automatically replayed. Simulator queue issues are also repaired. |
| External-drive queue abandoned lane | Legacy run-once holds an OS lane lock and has a bounded command timeout. Explicit `recover --task-id ... --confirmed-stopped` reconciles abandoned commands without replay; it refuses a live lane. Automatic recovery belongs to the new Docker service, which can enforce termination. |
| Cloudflare had no job API | The launcher starts the authenticated API plus connector; the client supports submission, status, waiting, cancellation, verified download and acknowledgement. Real Docker jobs passed through the actual gateway and the public tunnel. |
| Queued data changed after admission | Code/data are snapshotted, sealed and hash-verified at admission. Original source changes do not affect queued jobs. Consistent multi-file datasets still require an operator-frozen/versioned source. |
| Declared imports and runtime dependencies | Runner updates actual interpreter import paths. Per-job code dependencies and the Docker runtime image identity are frozen; Python/native dependencies must be prebuilt into that image. |
| Same-size seal reuse and partial extraction | Remote size AND SHA-256 checks, checksum-based retransmission, expected archive hash before extraction/bootstrap, and a hash-bound extraction-completion marker. Partial extraction alone never proves completion. |
| Returned status still said running | Result archives contain terminal job identity and exit code; the outer receipt carries the final archive SHA-256. Retrieval checks both. |
| Incomplete installed distribution | Wheel includes queue packages, service/client, simulator, tunnel modules, templates and a safe empty default inventory. Tested from outside the checkout in an empty venv. Legacy `fcntl` state imports have Windows-compatible fallbacks. |

## Isolation and operation limits

The service only accepts operator-configured templates; it is not an arbitrary
code-upload endpoint or a per-user multi-tenant authorization system. Every token
holder shares its job namespace. Templates may consume only explicitly selected
code/data, and their images must contain their runtime dependencies. The Docker
service runs Linux jobs even when its host is Windows or macOS; native Windows
binaries need a different execution environment or the legacy trusted SSH route.

Actual sandbox tests verified that a job could not read a synthetic host-only
file, inherit a controller secret marker, modify read-only bundled data, or make
an outbound connection. Declared bundled imports worked. Memory/CPU/PID limits,
read-only image, dropped capabilities and no-new-privileges are configured per
container. Docker is a security boundary, not a proof against kernel flaws.
Working-output monitoring and per-file limits are not a hard aggregate disk quota;
use OS quotas/VM isolation for adversarial workloads. Full kernel-hostile tenancy
was not claimed or tested.

Pending work survives restart. Abandoned running jobs become `interrupted` after
their named Docker container is stopped. Failed boundary termination stops the
worker and preserves its claim/diagnostics. There is no automatic execution retry,
silent data substitution or exactly-once claim for arbitrary external effects.

The old arbitrary external-drive command queue cannot safely infer that all
descendants of a crashed host command are dead. Its recovery therefore requires
explicit operator confirmation, and it should not be used as the isolated HTTP
job service. Existing queue contents and live host inventory were not migrated.

## Provenance

HEAD during implementation: `6763ff7fe69aed1a7deca9c1697ff7ae7eca9c6e`.
The worktree already contained platform-support and unrelated research changes;
those were preserved. The previous audit receipts were also preserved unchanged.

Wheel SHA-256:
`7fbe0c841feab53586b11106870f0de8370aecfc53457fd8ad37be34b4cc561e`.

[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) records the audited source identities
and confirms every wheel Python module with a matching source file is byte-identical.
The Docker image identity used in live tests was
`sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`.
The controller used Python 3.14.7; the repeat environment and container used
Python 3.12.14. Zstandard 0.25.0 and aiohttp 3.14.3 were tested.

The wheel installed without dependencies into an otherwise empty virtual
environment; worker/client imports, queue imports, `fleet --help`, template JSON
and the default inventory worked. Its installed CLI then passed the synthetic
Docker round trip without relying on the source checkout. Optional Cloudflare
dependencies were tested in separate isolated environments.

Docker Desktop was started for verification and the Python demo image was pulled.
Only synthetic test job containers/tunnels were created and stopped; no existing
Docker images/containers or live SSH hosts were removed. Temporary build/test
environments remain under `/tmp/offload-ready-20260909-IJxSAP`; persistent receipts
and the handoff wheel are retained in this directory.

## Reproduce

From `utils/offload_network`, in a virtual environment with Docker running:

```sh
python -m pip install ".[test,zstd,cloudflare]"
docker pull python:3.12-slim
OFFLOAD_TEST_DOCKER=1 python -m pytest tests v2/tests -ra
python -m offload_service.smoke_test
```

On PowerShell set `$env:OFFLOAD_TEST_DOCKER = '1'` before running pytest.
For the optional public synthetic test, add `--live` to the smoke command.
The successful local-DNS workaround was `--live --edge-ip 104.16.230.132`;
that is a recorded test endpoint, not a permanent hard-coded DNS recommendation.
Resolve the DNS issue or use a correctly configured stable named hostname before
depending on this source machine's normal HTTPS client for unattended operation.
