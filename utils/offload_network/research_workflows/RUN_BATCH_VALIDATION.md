# Multi-model offload validation — 10 September 2026

Package 0.5.0 implements versioned run batches, with one or more models and an
explicit comparator set per isolated job. v1 candidate batches remain compatible.

| Check | Final observed result |
| --- | --- |
| Full offload suite, `tests v2/tests` | 375 passed, 13 skipped; 60.75 s |
| Docker-enabled worker/workflow/v1 batch/v2 batch/live-file suite | 113 passed; 172.74 s |
| Fitted-candidate unit checks | 2 passed |
| Clean 0.5.0 wheel | 130 packaged source/assets matched checkout bytes |
| Installed package outside checkout | Five CLI operations passed; four-node/two-run example completed in real Docker |
| Real IQFeed candidate development | Nine-node graph completed with all six expected testing-run outcomes |
| Fresh-worker replay using only collected objects | Exact declared metric/numerator/denominator/contract parity; no refit |
| Toshiba retention archive restored into a fresh directory | Both full collections independently passed archive/file/native-receipt verification |
| Ruff and scoped `git diff --check` | Passed |

The pytest suites overlap, so counts are not additive. Ten opt-in Docker/native
cases skipped by the general suite were exercised separately. Three old
model-specific retained-fixture cases remain skipped. Local controller: macOS
arm64/Python 3.14.7; job containers: Linux arm64/Python 3.12, NumPy 2.2.6 and
SciPy 1.15.3. No actual remote machine, native Windows host or public tunnel was
tested. The CI configuration includes the new suite but was not launched remotely.

## Real development run

The [candidate design and implementation](../../../research/candidates/directional_forecasting/offload_treasury_ridge_development_20260910_v1/README.md)
fit two fixed ridge variants on 9,144 pre-2019 observations from a completed,
hash-verified IQFeed Treasury futures daily capture. Its 1,931-observation holdout
was a separate artifact, never mounted into the training job.

The graph ran: source verification/splitting → training → grouped, head-to-head,
reversed-role and standalone testing jobs. It also retained intentional model-error
and missing-data branches. Native testing reached statistics, with the standalone
job ending at metrics. The requester process exited after admission and its copied
source directories were withdrawn. Containers used only the admitted/produced
objects. Original source files and the research framework were not modified.

Four testing jobs completed, one intentional model-error job failed, and one
testing job was blocked by the deliberate missing-data producer. All returned
evidence verified. Both ridge variants beat the last-return control but were
slightly worse than zero-change on MAE and MSE; the declared group comparison
therefore FAILED. The negative result was not retuned or omitted. See the
[research result](../../../research/candidates/directional_forecasting/offload_treasury_ridge_development_20260910_v1/RESULT.md)
for exact scope and metrics. This is historical forecast development, not trading
profitability, PIT/prospective evidence or satisfaction of the frozen-pair objective.

## Repairs and retained evidence

The initial Docker regression found an incorrectly qualified test-fixture import;
the corrected full suite passed. The development launcher initially assumed the
wrong central-registry entry shape; it now uses the existing resolver. A report
reader expected a long-form CSV but the native table was wide; reporting was
resumed from verified native JSON without repeating primary fitting/evaluation.
Docker's stopped VM/stale backend was recovered with a normal Desktop restart;
no factory reset, image purge or shared-cache deletion was performed.

Reports are retained under [validation/run_batch_20260910](validation/run_batch_20260910/),
including the initial failing Docker report and separate passing report.
The candidate's `frozen_models/` contains byte-verified copies of the trained
artifacts and controls. `ARTIFACTS.json` records their object identity, file hashes,
the durable collection archive, tested wheel and restore/verification commands.

```text
Tested wheel SHA-256:
d1b38ea1e610ebcca4957e10e8271ede8c16d190aac3b80e1d825f5559dd5006
Full collection retention archive SHA-256:
4972715e3d3839782ed7a4c6999ea73f8abb130ebe551d159005547439c5822f
Primary delivery:
07065d0cbfb934a70ff27ce84429bc017146baa6e31692afb76c6b140db236ac
Collected-only replay delivery:
03c803747143b92a33a383a1c66425639ca52b0bfe1ff7df7d64099d6619f832
```

The durable archive and wheel are under the central `testing_ledgers` registry
location, in `offload_development/treasury_ridge_20260910_N9lrOJ/`. The archive is
16,400,140 bytes; using one archive avoids thousands of tiny external-drive files.
Its restored primary and replay collections passed the full normal verifier.

## Cleanup

All owned worker/requester processes and containers were checked stopped. Temporary
validation state is separate from the retained candidate and central archive;
cleanup does not delete the failed or negative research evidence.

About 935 MiB of temporary stores, build copies, virtual environment, regression
fixtures and archive-readback files were moved to macOS Trash as
`offload-model-development-20260910-N9lrOJ`, where they remain recoverable. The
original temporary root is absent. The fitted model files and compact evidence
remain with the candidate; the full 16.4 MB archive and tested wheel remain on
Toshiba. Existing Docker images, shared build cache, the pre-existing test Python
environment, original data and unrelated research edits were left untouched.
The task-owned `offload-model-development-20260910:validation` image was confirmed
absent; only the three pre-existing images remained. Docker Desktop was stopped
after checking that no containers remained.
