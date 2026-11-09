# Recovery fixes, parallel execution and IQFeed resumption

Date: 2026-09-11 UTC. This is a successor to
[`failure_audit_20260911`](../failure_audit_20260911/REPORT.md); the previous failing
test receipts and incident report remain unchanged.

## Offload outcome

All six retained failure reproductions now pass, including the IQFeed contention
case. The complete scoped suite passes: **501 passed, 13 skipped** in 125.27 s.
The skips require opt-in Docker/native research images or upstream fixtures;
they are not counted as successful deployment checks.

The fixes are packaged as `fleet-offload-orchestration` **0.6.1**. A fresh virtual
environment installed the retained wheel outside the checkout and passed a real
loopback HTTP plan, queue, execution, collection and origin-return scenario.
Forty-five installed package assets matched the source. Wheel SHA-256:

```
a4dd7005dc2246f63793b0d8009de7b74f803c5ed7ac6b218c108c3a8a6c0cd0
```

### Repairs

1. An interrupted upload initialization can resume from an empty, unbound part.
   Nonempty unbound data is retained and rejected, not silently adopted.
2. Repeating either upload initiation or commit cleans only hash-verified duplicate
   staging bytes after the committed object is verified. Interrupted cleanup is
   idempotent; conflicting bytes remain available for inspection.
3. Result download finalization retains a deterministic, discoverable recovery
   stage. A verified full prefix survives metadata failure or disk exhaustion;
   a fully prepared stage can publish after a process crash without contacting
   the worker. There is no second full archive copy for finalization. Subprocess
   hard-exit tests cover both sides of the final archive move.
4. Collection and origin import reserve physical compressed retention, with credit
   for already retained verified prefixes/stages, while preserving separate
   expanded-size verification limits. A roughly 3 MiB expanded fixture with less
   than 100 KiB of returned archives fits a 2 MiB compressed store budget.
5. Insufficient current free space is an `ENOSPC` transient failure, so the source
   queue retries when space recovers. A configured size-limit violation or
   integrity failure remains a hard error. Existing integrity holds are not
   silently cleared.
6. IQFeed retries only SQLite BUSY/LOCKED errors, retrying the same statement or
   commit without replaying the downloaded response. Retry is bounded, honors
   stop/drive guards, and preserves other operational errors. Failed transactions
   roll back before exporting error status, avoiding uncommitted queue states.

## Parallel execution: verified with explicit limits

Two separate worker services on this Mac, each with two execution slots, ran
**four actual subprocess jobs simultaneously**. Each worker executed three
independent packaged model/data jobs followed by a comparison that waited for all
three verified results. The source queue was closed and the source/planning tree
withdrawn during execution. Reconnection returned **eight independent job records
to their frozen research origins**, preserving the original local research files.

Six additional scenarios prove that one slot, or aggregate CPU, memory, process
or scratch limits, correctly serializes ready jobs; two adequately provisioned
slots permit two concurrent jobs. The capabilities endpoint advertises the slot
limit and scheduling policy. See [parallel execution and configuration](../../PARALLEL_EXECUTION.md).

These are local simulations with real authenticated loopback HTTP, isolated job
directories and subprocesses using the **trusted-local** backend. They do not
prove Docker security isolation, native Windows/Linux execution, physical remote
connectivity or a configured remote deployment. The portable tests are included
in the platform CI matrix, which was not run remotely in this turn.

The worker already supported parallel execution; this turn added measured
regression coverage and clearer configuration/capability reporting. Each admitted
DAG belongs to one worker. Separately identified batches can run on multiple
configured workers concurrently, but automatic cross-worker DAG splitting,
fleet-wide balancing and failover are **not implemented**. The checked-in source
configuration has no external endpoints. Persistent host startup services must
also be configured for unattended reboot recovery.

## Existing genuine research records

The read-only recheck of the retained Treasury ridge development run passed:
26 compressed objects verified, six origin records and 11 original candidate
files unchanged, and five native testing-stage results byte-verified. The
missing-data control still has no fabricated output. No new research fit was
launched and no improvement or profitability claim is made.

## IQFeed restart

**Resumed and verified processing requests.** The stopped-worker verification
passed for all 22,058 retained response attempts, with zero classification
corrections. It checked raw compressed/uncompressed response hashes and derived
CSV hashes/row counts before binding the repaired collector. The immutable
receipt is `metadata/COLLECTOR_REVIEW_0fd17a84d6264ea2bac029d95418887c.json` on the
Toshiba macroeconomics archive. The request scope and historical cutoff
`20260909` are unchanged; no STOP request, live lock or drive guard was overridden.

The worker launched at **00:32:35 UTC**, PID **3165**. Two exported-state/log
observations, ending at **00:34:29 UTC**, confirmed fresh processed IQFeed
responses, `DOWNLOADING`, and decreasing unfinished counts. The final exported
snapshot had **5,657 unfinished jobs** (5,656 pending and one running), down from
5,703 before maintenance. The worker remained alive at the final cleanup check.
It is deliberately left running; **downloads are not finished**.

The observed new responses were `NO_DATA` for old dated-contract probes, not
additional price bars. Retained parsed rows remained 253,419,144; this is not a
unique-observation count or proof of inception/calendar completeness. Existing
99 `NOT_AUTHORIZED` results are provider-entitlement limitations and are not
removed by this repair. Monitoring used only exported metadata and bounded log
tails, never a long reader transaction on the live SQLite queue. About 61 GiB was
free on Toshiba, above the unchanged 20 GiB acquisition reserve.

## Evidence and cleanup

- [Full scoped suite](FULL_SUITE.xml): 501 passed, 13 skipped.
- [Original failure reproductions](ORIGINAL_REPROS.xml): six passed.
- [Transfer crash recovery](TRANSFER.xml): nine passed.
- [Parallel scenarios and measured timing properties](PARALLEL.xml): seven passed.
- [IQFeed tests and original contention reproduction](IQFEED_TESTS.xml): 27 passed.
- [Installed-wheel smoke receipt](INSTALLED_SMOKE.json).
- [Existing genuine research return recheck](GENUINE_RECHECK.json).
- [IQFeed archive verification log](IQFEED_REBIND.log).
- [Verified IQFeed launch](IQFEED_RESUME.json) and [live progress receipt](IQFEED_PROGRESS.json).
- [Cleanup receipt](CLEANUP.json).

The owned `/tmp/offload-fixes-20260911-6z6fsK` test root was removed after retaining
the receipts and release wheel, reclaiming about 295 MiB of allocated storage.
This was deletion of regenerable fixtures, build scratch and a disposable test
environment, not a move to Trash. No test workers or restart helper remain running.
The existing reusable environment, production research records, source data and
earlier failing audit are preserved. IQFeed is the intentionally continuing job.
