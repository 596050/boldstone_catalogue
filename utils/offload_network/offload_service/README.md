# Queued, isolated offload worker

This is the supported path for **authenticated HTTPS requests → durable queue →
isolated jobs → verified results**. It lives in its own `offload_service/` package.
The external machine runs the worker and, optionally, its Cloudflare connector.
Requesters need Python and a token, but no SSH account, Docker or tunnel client.

## Install and start

Worker prerequisites: Python **3.10+**, a running **Linux-container Docker engine**
(Docker Desktop on Windows/macOS), and a prebuilt job image. Run under a non-root
OS account with Docker access. For a public URL, also install `cloudflared` using
the [connector setup guide](../external_machine_connect/cloudflare/README.md).
No VPS or inbound router/firewall port is required for this HTTP path.

From `utils/offload_network`, using your virtual environment's Python:

```sh
python -m pip install ".[cloudflare]"
docker pull python:3.12-slim
python -m offload_service init --dir ./worker-home
python -m offload_service serve --config ./worker-home/worker.json --tunnel
```

On Windows, `py -3` can replace `python`; after installation into a virtual
environment use that environment's `Scripts/python.exe`. On Linux/macOS use
`bin/python`. The installed `offload-worker` command is equivalent to
`python -m offload_service`. Initialization refuses to overwrite an existing
directory. It creates a synthetic `demo-sum` template, data, worker configuration,
and random private token file. **Configure your actual jobs/data before production use.**

`serve --tunnel` prints a `PUBLIC_URL=https://…trycloudflare.com` address when
Cloudflare allocates it; wait for **Tunnel connected** before testing. Without
`--tunnel`, the API listens on `127.0.0.1:8765` only. Stopping the command stops
the connector, HTTP listener and active job containers. Pending jobs survive.
This command does not install an auto-start OS service or create Cloudflare DNS.

A stable, pre-provisioned named tunnel can be selected with `--tunnel-args`:

```sh
python -m offload_service serve --config ./worker-home/worker.json --tunnel --tunnel-args --tunnel-id YOUR-UUID --credentials-file /private/tunnel.json --hostname worker.example.com
```

The launcher shares the worker token with its gateway, uses `X-Offload-Token`
for gateway authentication, and independently checks `Authorization` at the API.
The supplied client sends both headers automatically. Do not change the gateway
to its default Authorization-consuming mode for this service.

## Submit from the source machine

Install the same package on the requester (`python -m pip install .` from this
directory, or install the built wheel). Securely copy only the worker's
`access-token` to an authorized requester. Do not paste it into URLs or commit it.
All token holders share the worker's configured templates and job namespace;
this is not a multi-tenant per-user authorization system.

```sh
python -m offload_service.client --url https://YOUR-WORKER.trycloudflare.com --token-file ./access-token submit --template demo-sum --job-id example-job-001 -- hello
python -m offload_service.client --url https://YOUR-WORKER.trycloudflare.com --token-file ./access-token wait example-job-001
python -m offload_service.client --url https://YOUR-WORKER.trycloudflare.com --token-file ./access-token result example-job-001 --out ./returned-job-001
```

The demo's `result.json` contains `{"sum": 10, "args": ["hello"]}`. Downloaded
directories also contain terminal `status.json`, the worker/controller receipt,
logs, and `received-result.tar.gz`. A repeated download to that directory is
accepted only when its retained archive still matches this job's result hash.

Use `status JOB_ID` to inspect progress and `cancel JOB_ID` to request cancellation.
The wait deadline does **not** cancel or delete a remote job. Poll its ID again.
Retry a lost submission response with the **same explicit job ID and body**;
it returns the original job without resealing or executing twice. Different
content under that ID returns HTTP 409. Use a **new ID** for an intentional rerun.

## Configure code, data and dependencies

Paths in `worker.json` are relative to that configuration file. Only the worker
operator edits templates; HTTP requests cannot select host paths, commands,
environment variables, images or resource limits. A template resembles:

```json
{
  "entrypoint": "code/job.py",
  "code_dir": "code",
  "data": [{"path": "data/prices.csv", "rel_path": "data/prices.csv"}],
  "image": "your-prebuilt-job-image@sha256:REPLACE_WITH_REAL_DIGEST",
  "env": {"MODEL_MODE": "frozen"},
  "timeout_s": 600,
  "memory_mb": 2048,
  "cpus": 2,
  "pids": 128,
  "max_output_mb": 128,
  "max_work_mb": 512,
  "max_input_mb": 1024
}
```

The entrypoint runs with its own job directory as `cwd`. Read data at
`blobs/data/prices.csv`; imports can use modules shipped in `code_dir`. Write
results to `result.json`, other JSON/log files, or `artifacts/`. Default collection
excludes the input blobs. Python and native dependencies belong in the **prebuilt
image**, built with pinned dependencies; the worker never installs them during
execution. It resolves the configured image to a content identity at startup,
persists it with each admitted job, and uses `--pull=never`. Changing a tag or
template later does not change a queued job's runtime or bytes.

Configured code and data must already exist on the external machine. At admission
they are copied, hashed and sealed before the job becomes runnable. Changing the
originals after admission does not affect it. For consistent multi-file datasets,
point templates at a frozen/versioned dataset directory: copying a live database
or a set being concurrently rewritten is **not** a transactional database snapshot.
Sources are copied, never moved or deleted. Symlink sources are rejected.
Keep input/code directories narrow: do not bundle credentials, worker state or
an entire user profile. Explicitly configured inputs and image contents are part
of the operator-controlled trust boundary.

Top-level limits: `concurrency` (default 1, up to 32), `max_pending` (100),
`min_free_mb` (1024), and `max_store_mb` (10240). The store must be on a private
local filesystem supporting SQLite and OS locks, not a shared network drive.

## Guarantees and boundaries

- SQLite orders jobs by admission sequence and claims each with a unique attempt.
  Only one controller owns a store; execution threads claim atomically. Concurrent
  jobs can finish out of order. This is not an exactly-once guarantee for arbitrary
  external effects, and crashed jobs are never automatically replayed.
- On restart, previously running Docker containers are stopped before their jobs
  are marked `interrupted`. Queued work resumes. If termination cannot be confirmed,
  the worker stops admitting/executing jobs and leaves the claim for reconciliation.
  The terminal receipt retains the prior state and execution receipt under
  `restart_recovery`, including any original timeout and failed cleanup details.
  Those nested errors describe the previous observation, not a new unconfirmed
  termination or a successful result. Recovery does not execute the job again.
- Each job gets a separate non-root container: no network, read-only image and
  input mount, dropped capabilities, no privilege escalation, bounded memory/CPU/
  process count/time. Only that attempt's working directory is mounted writable.
  No Docker socket, controller home, token file or other job directory is mounted.
  Docker's mechanisms are described in [Docker's runtime documentation](https://docs.docker.com/engine/containers/run/).
- Working-output bytes are monitored and per-file size is limited. This is **not
  a hard aggregate filesystem quota**; use filesystem quotas/VM boundaries for
  adversarial workloads. Containers are not a proof against kernel vulnerabilities.
  Operator-owned templates and trusted images remain part of the trust boundary.
- Jobs do not inherit controller secrets. Only explicitly configured template
  environment values and the image's own environment are available in Docker.
- Results are hash-checked and safely unpacked before publication/acknowledgement.
  Downloads can be repeated after interruption. Acknowledgement records delivery;
  it **never automatically deletes results**. Capacity exhaustion rejects admission.
  Archive/export stopped worker stores according to your retention policy.
- A job exception is terminal `failed`, but its verified logs/results remain
  downloadable when packaging succeeded. Timeout/cancel/startup errors have durable
  receipts; incomplete files remain in the private worker store for diagnosis.
- Tar extraction permits only bounded regular files/directories, rejecting links,
  devices, traversal, path aliases and duplicate entries independently of Python's
  [changing default extraction filters](https://docs.python.org/3/library/tarfile.html#extraction-filters).
- The optional `--trusted-local` backend is for trusted-code testing, **not a
  sandbox**. Its combination with `--tunnel` is rejected by the launcher.

## API

All routes require `Authorization: Bearer TOKEN`; through the gateway additionally
send `X-Offload-Token: TOKEN`. Requests are JSON, at most 64 KiB, with a single
Content-Length; query tokens, redirects and chunked request bodies are unsupported.

| Route | Method | Purpose |
| --- | --- | --- |
| `/v1/health` | GET | Worker readiness and execution backend |
| `/v1/templates` | GET | Allowed template names |
| `/v1/jobs` | POST | `{job_id, template, args?, metadata?}` → 202 or idempotent 200 |
| `/v1/jobs/ID` | GET | State, input identities and terminal receipt |
| `/v1/jobs/ID/cancel` | POST | `{}` requests cancellation |
| `/v1/jobs/ID/result` | GET | Stream retained archive and X-Content-SHA256 |
| `/v1/jobs/ID/ack` | POST | `{sha256}` records verified retention by requester |

Cloudflare Quick Tunnel URLs can change, have no uptime guarantee, and depend on
requester DNS/network connectivity. Named tunnels are appropriate for a stable
address. HTTPS terminates at Cloudflare, which can process the traffic. See the
[connector's operational limits](../external_machine_connect/cloudflare/README.md#behavior-and-limits).

## Legacy paths and tests

`simulator.py` is a local trusted-code demonstration, not an OS sandbox or network
service. It now seals at enqueue, protects claims/IDs, recovers abandoned records
as interrupted failures, and stops ordinary descendant processes on timeout.
The SSH v2 path now checks whole-seal hashes before reuse/extraction/launch, uses
an extraction-complete marker, returns final status, and retains remote evidence
on unsuccessful result retrieval. It still executes **trusted code in the SSH
account**, not in the Docker service's boundary.

The older external-drive command queue is also trusted host-command tooling, not
the HTTP job queue. Run-once now holds an OS lane lock and enforces `--timeout-s`.
For an abandoned running task, first confirm the old command and all descendants
have stopped, then use `python -m trading_common.data_storage.external_queue`
with the same database/root options and `recover --task-id ID --confirmed-stopped`.
Recovery refuses a live lane lock, marks the old task interrupted, and never
replays it. Do not guess process termination for a data-writing command.

Install test dependencies with `python -m pip install ".[test,zstd,cloudflare]"`.
From the orchestration root, run `python -m pytest tests v2/tests`. Set
`OFFLOAD_TEST_DOCKER=1` to include real container isolation, timeout, restart and
authenticated gateway round trips. Tests use synthetic inputs, not trading data.
The repository CI workflow covers native Windows/macOS/Linux worker tests and a
separate Linux Docker job; adding that workflow does not mean it has run remotely.

To exercise the installed launcher and client with synthetic data and real
Docker, run `python -m offload_service.smoke_test`. Add `--live` to explicitly
publish a temporary Cloudflare tunnel. The test stops both processes afterward.
A new Quick Tunnel can briefly return 5xx while routing propagates. The smoke
test waits for that; a requester should retry a failed submission with the same ID.
The optional smoke-test `--edge-ip` overrides DNS only for that test client and
retains normal TLS hostname verification. It does not repair system DNS or prove
that other requesters can resolve the hostname normally.
