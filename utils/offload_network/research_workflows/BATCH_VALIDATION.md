# Independent candidate batch validation — 10 September 2026

Implemented in package 0.4.0. These checks establish software behavior with
synthetic inputs, not predictive improvement or a configured remote deployment.

## Final checks

| Check | Result |
| --- | --- |
| Full offload suite, `tests v2/tests` | 359 passed, 12 skipped; 57.18 s |
| Docker-enabled worker/workflows/batches/live-file suite | 96 passed; 120.55 s |
| Source-only wheel build and byte comparison | 126 packaged source/assets matched |
| Installed 0.4.0 wheel outside the checkout | Eight CLI operations passed; shipped six-node/two-candidate example completed in Docker |
| Ruff on affected Python code; `git diff --check` | Passed |

The pytest suites overlap; counts are not additive. Nine opt-in Docker/research
tests skipped in the general suite were exercised in the Docker suite. Three
legacy, model-specific retained-fixture tests were not run. The controller was
macOS arm64/Python 3.14.7; isolated jobs used Linux arm64/Python 3.12 containers
with preinstalled NumPy 2.2.6 and SciPy 1.15.3. No native Windows or configured
remote-host run was performed. The CI matrix includes the added tests but was not
submitted to remote runners in this session.

## Independent native outcomes

The same five-candidate batch ran through native statistics in trusted-local and
restricted Docker modes, with two seeds and candidate-specific input supplies.
Each candidate had a private select → prepare → test chain. Only Docker is the
production isolation boundary.

| Candidate | Execution state | Retained scientific/diagnostic result |
| --- | --- | --- |
| `bundled` | succeeded | Supported synthetic comparison; 100 input cases |
| `registered` | succeeded | Supported synthetic comparison; 120 input cases |
| `negative` | succeeded | Statistical verdict FAILED, preserved rather than omitted |
| `broken` | failed | Controlled candidate evaluation error and native receipts |
| `missing` | blocked_dependency | Required raw file absent; preparation failure retained |

The requester HTTP server was stopped after admission and reopened only for result
collection. Original source data and candidate code were changed after packaging;
the immutable admitted bytes still executed. Raw hashes, prepared row counts,
producer-to-consumer input identities, native reports, metrics CSV and JSONL
ledgers were checked. Repeated collection succeeded; changing a collected candidate
ID was rejected. Partial rosters retain waiting candidates. Cross-candidate edges,
hidden extra models, absolute source-host arguments and broadened file selections
were rejected. Shared selections were snapshotted once; unused sources were not read.

Independent candidate verdicts are not a multiplicity-corrected batch-family
result. No pooling, promotion, real-data acquisition or trading run took place.
Dynamic preparation chooses/transforms from declared immutable data, not arbitrary
new online requirements. Native validation reaches statistics; later execution
and prospective gates still require workload-specific checks.

## Issues found and resolved

The initial broad run found a short test-only token, corrected in the fixture.
It also reproduced a real worker race: an atomic temporary file disappeared
between the live disk monitor's `is_file()` and `stat()` calls. Live accounting
now uses one non-following `lstat`, tolerates only disappearing live entries, and
does not hide permission or missing-root errors. Immutable artifact/source
verification remains strict. Deterministic race, error and symlink tests passed.

The first temporary wheel copies accidentally included pre-existing `build/`
artifacts. A clean-install test caught the resulting stale HTTP handler. Rebuilding
from a source-only copy excluding `build/`, `dist/`, egg-info and caches fixed that
validation-build issue; all 126 wheel source/assets then matched the checkout.
The installed example exercised pack-research, plan-batch, validate, submit,
collect, verify and both all-candidate and single-candidate result commands.

Tested clean wheel SHA-256:
`d1318484ec13273a304649375033f27a7985d207875ea19e2e132dff90453d43`.
This identifies the tested build, not a reproducible hash for future rebuilds.

## Reproduce and evidence

From `utils/offload_network` with test dependencies installed:

```sh
python -m pytest tests v2/tests -ra
docker build -f research_workflows/examples/Dockerfile.research-test -t offload-research-tests:local research_workflows/examples
```

Set `OFFLOAD_TEST_DOCKER=1` and
`OFFLOAD_RESEARCH_TEST_IMAGE=offload-research-tests:local` in the shell, then run:

```sh
python -m pytest tests/test_ready_worker.py tests/test_research_workflows.py tests/test_research_batches.py tests/test_live_files.py -ra
```

Compact reports and identities are in [validation/batch_20260910](validation/batch_20260910/).
Original failing and final passing JUnit reports are retained separately. Native
result views there are reconstructed from the immutable deliveries, because the
test deliberately tampers with the final local index to verify rejection.

## Cleanup

Final runtime checks found no test workers or containers left running. The
task-owned `research-offload-batch-validation-20260910:synthetic` image was removed
(rebuildable from the supplied Dockerfile). Docker Desktop, started for these
tests, was quit after checking that no containers remained.

Approximately 565 MiB of synthetic stores, original receipts/logs, build copies,
wheels and the temporary installed virtual environment were moved to macOS Trash
as `research-offload-batch-validation-20260910-9L7e3L`, where they remain recoverable.
The original temporary root is absent. Compact evidence remains in this repository.
The pre-existing test environment, three pre-existing Docker images, shared build
cache, source-tree build artifacts, Toshiba downloads and unrelated working-tree
changes were left untouched. No live research jobs or real data were created or
altered by this validation.
