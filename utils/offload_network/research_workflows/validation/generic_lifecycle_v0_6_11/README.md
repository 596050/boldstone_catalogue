# Generic lifecycle 0.6.11 validation

Recorded 2026-09-12. This directory contains verification evidence, not an active
job launcher or study-specific implementation. Shared functionality and schemas
are documented in [GENERIC_JOBS.md](../../GENERIC_JOBS.md).

The complete offload package suite collected **657 tests: 631 passed, 26 skipped,
zero failures/errors**, in 171.079 seconds. `TESTS.xml` is the original JUnit
report. Skips include optional Docker/research-image cases, absent aiohttp/zstandard,
and retained non-generic upstream fixtures. Eight pytest reporting-format warnings
are not runtime failures. Do not describe the skipped scenarios as validated.

The enabled generic Docker lifecycle test used the already cached immutable image
`sha256:0eef8d6fc298a7fed3f8c15eba82e0f84fbd5ff4b31dc382da8f923d4da6654d`,
one CPU, 512 MiB RAM, 16 MiB input/object limits, 32 MiB work and 8 MiB output.
It prepared a tiny offline wheel, validated it in Linux, imported it in the job
and a child interpreter, consumed path-relocated synthetic inputs and collected
verified output. `DOCKER_LOCAL_RUN.json` records clean exit of that owned temporary
worker. No existing configured worker was installed, restarted or reconfigured.

`retention/` retains the exact synthetic work archive, intent, full restore-proof
and completion receipts. The test removed only that verified redundant test work
directory, restored it byte-for-byte into a fresh directory, and exercised
idempotent retention. The archive can still be restored with `restore-retention`;
paths recorded in the historical local-run receipt need not remain live. The
source test's returned collection was verified independently before compaction.

The 0.6.11 wheel was built without network/dependency installation and installed
only into a fresh temporary target. `PACKAGE_VALIDATION.json` records isolated
imports, exact installed/source file equality for the shared lifecycle modules
and runner helpers, plus a working prepare-input/relocate-input CLI round trip.
The wheel hash is `11bf60dcfa3b6891e460fccd9baa617aceb541aff970578b3025745fbbcb33c3`.

These are infrastructure/software results, not research acceptance, trading
improvement, native Windows validation or configured remote-worker validation.
Previously queued tsfresh work and its sealed evidence were not migrated.
