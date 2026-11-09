# Offload network validation — 2026-09-09

**Verdict: the requested queued, isolated, encapsulated offload service is not yet ready.**
The component tests and basic local job lifecycle pass. Independent failure
probes reproduce queue, isolation, dependency, integrity, and result-retention
problems. An HTTP job API joining the Cloudflare connector to the job system is
also absent.

## What was checked

| Area | Evidence | Assessment |
| --- | --- | --- |
| Fleet/v2 tests, including platform routing | Latest working tree: **272 passed, 3 skipped**, 18.54s | Passing component suite; three upstream project-specific scenarios remain unavailable |
| Cloudflare gateway tests | **22 passed** | Local authentication, HTTP forwarding, limits, signals and configuration checks pass |
| SSH tunnel tests | **4 passed** | Command construction and input checks pass; not a live SSH round trip |
| Local simulated lifecycle | Five fresh jobs: two successes; expected exception, timeout and missing-source failures | Basic configured-data, seal, execution and result-return path passes |
| Independent lifecycle probes | [PROBES.json](PROBES.json), 12 cases | Reproduced gaps described below; no probe errors |
| Archive boundary and integrity | [Python 3.12](ARCHIVE_PYTHON312.json), [Python 3.14](ARCHIVE_PYTHON314.json) | Extraction escapes the destination on 3.12; 3.14 blocks that fixture |
| Standalone wheel | Wheel built and installed into an empty virtual environment; `fleet --help` works | Queue package, templates and default host inventory are omitted |
| Live remote workers | Inventory contains disabled example SSH aliases | Not validated on live machines |

Total existing automated checks: **298 passed, 3 skipped**. This count does not
turn the independently reproduced gaps into passes. All execution took place
on macOS arm64, primarily Python 3.14.7; archive checks additionally used Python
3.12.14. POSIX shell tests execute on this Mac, including tests labelled Linux.
Windows process/PowerShell paths are tested through mocks, not a Windows kernel.

The Cloudflare public smoke test from the preceding implementation was recorded
separately in [its validation report](../../external_machine_connect/cloudflare/VALIDATION.md).
It required a test-client DNS override. That public test was not rerun here and
does not establish a queued-job HTTP endpoint.

## Findings, ordered by operational importance

### 1. Failed result transfer triggers remote deletion

`submit_one()` runs `_cleanup_remote()` from `finally`, including after
`fetch_and_unpack()` fails. The probe injected a transfer interruption after a
successful job and observed deletion requests for both the remote job directory
and the seal. This can remove the only complete results before they are retained
locally. A deadline exception uses the same cleanup path without a confirmed
remote process-tree stop. Remote calls were mocked; nothing on a live host was
deleted.

Source: [v2/submit.py](../../v2/submit.py:54). Probe: `result_transfer_failure_cleanup`.
Required: retain remote evidence on unsuccessful pull/verification, and make
cleanup conditional on acknowledged result retention or explicit abandonment.

### 2. Job isolation is limited to working directories and the runner process

A synthetic job read a marker outside its job directory and inherited a
synthetic controller environment value. There is no container/OS sandbox or
environment allowlist. The timeout probe spawned a bounded child process: the
queue recorded a timeout, but the child subsequently wrote its marker.

Sources: [simulator.py](../../simulator.py:219), [v2/runner.py](../../v2/runner.py:282).
Probes: `isolation_boundary`, `timeout_descendant`. This may be acceptable only
for trusted code if directory separation is the intended boundary; it does not
satisfy host/sibling-job/credential isolation. Required for stronger isolation:
an enforced execution boundary, explicit environment/data access, resource
limits, and cancellation of the complete process tree.

### 3. Python 3.12 archive extraction can escape its destination

Both `result._safe_extract()` and `seal._safe_extract_tar()` accepted a synthetic
archive containing a symlink followed by a file beneath that link. The file
landed in a sibling fixture directory outside the extraction destination on
Python 3.12.14. The pre-scan checks member names before the symlink exists and
does not enforce the link target. The same fixture was blocked on Python 3.14.7.
Python 3.14 changed the default tar extraction filter to `data`; older versions
used behavior equivalent to `fully_trusted`. [Python documentation](https://docs.python.org/3/library/tarfile.html#extraction-filters)

Sources: [v2/result.py](../../v2/result.py:72), [v2/seal.py](../../v2/seal.py:414).
All writes stayed inside the audit's temporary fixture tree. Required: explicit
version-independent extraction policy covering link targets, member types,
paths and extraction limits; do not rely on the interpreter's default filter.

### 4. Queue delivery and restart behavior are incomplete

The filesystem simulator queue has four reproducible limitations:

- Jobs execute by lexicographic random job ID, not enqueue time. Enqueuing
  `zz-first` before `aa-second` executed `aa-second` first.
- Reusing a pending job ID silently replaces the first request.
- Two consumers racing to claim the same file cause one consumer to raise
  `FileNotFoundError` rather than continue to another job.
- An interruption after pending-to-running leaves the job in `running` after
  reconstruction; `process_next()` returns no job and produces no receipt.

The separate SQLite external-drive queue correctly serializes a lane, but a
worker that disconnects after acquiring a task leaves that lane blocked for
its replacement. No automatic lease/heartbeat recovery was found. It is a local
command queue, not the networked sealed-job queue.

Sources: [simulator.py](../../simulator.py:108),
[external_queue.py](../../trading_common/data_storage/external_queue.py:138).
Probes: `fifo`, `duplicate`, `queue_concurrent_claim`, `queue_restart`,
`sqlite_recovery`. Required: a defined queue order, identity conflict handling,
atomic claims with fencing/leases, restart reconciliation and bounded retries.

### 5. Cloudflare connectivity is not integrated with job submission

The Cloudflare connector forwards HTTP to an existing service. The v2 job
lifecycle pushes and polls through SSH/rsync. No implemented authenticated HTTP
job-submit/status/result API or HTTP transport adapter links these components.
The simulator uses filesystem copies instead of either network transport.

Sources: [Cloudflare README](../../external_machine_connect/cloudflare/README.md),
[v2/submit.py](../../v2/submit.py), [simulator.py](../../simulator.py).
Required: choose and implement the worker/controller service contract, including
authenticated submission, job identity, queue admission, status and verified
result retrieval. A public URL alone does not make jobs remotely runnable.

### 6. Queued data is not immutable at admission

`enqueue()` stores source/entrypoint paths; it does not seal their bytes or
record an expected content identity. Changing configured source content after
enqueue caused the job to consume the changed bytes successfully. Hashes are
established later, when the job is processed. Source root traversal rejection
and normal data delivery do pass.

Source: [simulator.py](../../simulator.py:108). Probe: `queued_data_identity`.
Required if a queued job must be reproducible: seal/snapshot at admission, or
require immutable data versions and verify the requested hashes before execution.

### 7. Declared dependency paths do not work for a direct entrypoint

A bundle containing both an entrypoint and its helper module, with
`extra_pythonpath=["blobs/code"]`, failed with `ModuleNotFoundError` and exit
code 73. The runner changes the `PYTHONPATH` environment variable but executes
the entrypoint in the already-running interpreter with `runpy.run_path()`.
It does not update that interpreter's `sys.path`. The generic driver has its
own path setup, so this finding specifically covers direct sealed entrypoints.
No per-job dependency environment/lock is provisioned by the generic runner.

Source: [v2/runner.py](../../v2/runner.py:282). Probe: `declared_dependency_import`.
Required: apply declared import paths to the executing interpreter and define
how each job's Python/native dependencies are pinned and made available.

### 8. Retry shortcuts do not prove artifact identity or complete extraction

`push_seal()` accepts equal byte size as proof an existing remote seal matches;
the probe confirmed it skips transfer without checking a content hash.
`extract_seal_remote()` skips extraction when only `manifest.json` exists, even
though that is one of the first archive members written during extraction.
An interrupted extraction can therefore be mistaken for a complete one.

Separately, changing `runner.py` inside an archive was accepted by
`verify_seal()` without an external expected archive hash. Supplying the original
whole-archive hash correctly rejected it. The remote launch path does not pass
or verify that expected whole-archive hash before executing the bootstrap.

Sources: [v2/transport.py](../../v2/transport.py:202),
[v2/launcher.py](../../v2/launcher.py:78), [v2/seal.py](../../v2/seal.py:301).
Required: bind reuse and launch to the expected complete artifact hash and use
an atomic extraction-complete marker written only after verification.

### 9. Returned status does not describe the completed job

A successful job's envelope and remote `status.json` reported completion, but
the returned archive's `status.json` still said `running` and omitted the exit
code. Results are packed before final status is written.

Source: [v2/runner.py](../../v2/runner.py:329). Probe: `result_terminal_status`.
Required: include an authoritative final execution record in the returned
artifact, with identity and integrity checks at the controller.

### 10. Installed distribution is incomplete

An independently built wheel installed successfully and `fleet --help` ran.
However, `python -m trading_common.data_storage.external_queue --help` failed
with `ModuleNotFoundError`. `_load_template("cache")` failed because no template
JSON files were included. The default `hosts.json` and simulator are absent too.
An editable checkout can mask these packaging omissions. The controller also
imports POSIX `fcntl` unconditionally; a portable worker does not imply a
Windows-compatible controller.

Sources: [pyproject.toml](../../pyproject.toml:37), [fleet/state.py](../../fleet/state.py:37).
Required: include runtime packages/resources and test the installed distribution
separately from a source checkout; declare controller and worker OS support.

## Provenance and reproduction

Repository HEAD during validation: `6763ff7fe69aed1a7deca9c1697ff7ae7eca9c6e`.
The working tree had concurrent edits from other work. An initial moving-tree
run produced 242 passes, nine manifest-schema failures and three skips. Those
schema failures disappeared after the concurrent compatibility change. An
isolated snapshot then passed 266 tests; the final working tree passed 272.
The independent lifecycle and Python 3.12 archive probes were repeated against
that final working tree and reproduced the findings above.

[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) records 96 audited Python files.
Its SHA-256 is
`98f7cd2d4e143c4049921d4b6b8beec8cf22ae71aedb8385da6dea0d54a48518`.
[FINAL_COMPARE.json](FINAL_COMPARE.json) confirms those files matched at the
final comparison. [SUITE.xml](SUITE.xml) contains the latest core/v2 test results.
The Python 3.14 archive checks used the isolated snapshot; its two extraction
implementations were unchanged in the final comparison.

The tested wheel SHA-256 was
`4d9616b4058a8a2dd9cc589aa580040bf27063a1128ada7c58a10913f5483956`.
It was built from the isolated snapshot. Packaging metadata did not change
during this audit.

Reproduce from `utils/offload_network` with a fresh output path:

```sh
python3 -m pytest tests v2/tests -ra
python3 validation/20260909T152018Z/audit_probes.py --source . --out /tmp/offload-probes-new
python3.12 validation/20260909T152018Z/archive_probes.py --source . --out /tmp/offload-archives-new
```

The archive reproduction uses only a synthetic sibling directory under the
specified fresh output path. The probes never contact remote hosts; SSH deletion
and transport calls are intercepted. Fixtures, installed test environment,
initial suite receipts and isolated source snapshot are retained under
`/tmp/offload-validation-20260909-FZUYLM`. This audit added only validation
artifacts to the repository; it did not fix runtime code, configure live hosts,
modify existing queues or expose real job/data services.
