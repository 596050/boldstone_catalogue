# Parallel execution and multiple machines

Independent ready jobs run concurrently on each worker, up to both its
`concurrency` slots and its aggregate CPU, memory, process and scratch-space
budgets. Dependency consumers wait for their declared producers' verified
outputs. A model-development producer, several model-testing jobs and a comparison
can therefore share one DAG without pretending dependent stages are independent.

`research-offload init-worker` creates a worker with two execution slots, two
aggregate CPUs, 2048 MiB aggregate memory, 512 aggregate processes and 2048 MiB
aggregate scratch. The initial Python runtime permits up to one CPU, 512 MiB
memory, 128 processes and 512 MiB scratch per job. These are explicit safe example
limits, not hardware detection or suitable defaults for every large research model.

Configure the actual machine in `worker-home/worker.json` before starting it:

```json
{
  "concurrency": 4,
  "workflows": {
    "capacity": {"cpus": 4, "memory_mb": 8192, "pids": 1024, "max_work_mb": 8192}
  }
}
```

This is a partial configuration example: retain the rest of the generated config,
including approved runtime/image profiles. Adjust those profiles for the workload
too. Increasing slots alone does not override CPU/RAM/process/scratch limits. The
worker validates individual profiles against aggregate capacity and atomically
accounts for already running jobs before claiming the next one. Native testing
threads are constrained separately to avoid unchecked nested parallelism.
Production execution uses isolated Linux Docker containers on Linux or Docker
Desktop with Linux containers on macOS/Windows. Trusted-local test workers do not
provide that security boundary.

The authenticated `/v2/capabilities` response exposes `max_parallel_jobs`, aggregate
`capacity`, approved runtime limits and the scheduling policy. This slot count is
an upper bound; large jobs can reduce actual concurrency.

## More than one remote worker

Configure each authorized endpoint in the source `project.json` workers map, then
assign separately identified, self-sufficient workflows/batches:

```sh
research-offload enqueue --config PROJECT.json --plan PLANNED_A \
  --worker machine-a --origins ORIGINS_A.json
research-offload enqueue --config PROJECT.json --plan PLANNED_B \
  --worker machine-b --origins ORIGINS_B.json
research-offload sync --config PROJECT.json --watch
```

Both workers process their admitted DAGs independently and can overlap while the
source is disconnected. The source reconnects to collect each immutable delivery
and files results into its frozen local origins. Input objects and returned data
are hash-bound, with shared source retention instead of duplicate full candidate
trees. A batch can contain multiple models/comparators; its testing jobs compete
for the same worker execution slots as producers and other batches.

**A single submitted DAG belongs to one worker.** There is no automatic splitting
of that DAG across machines, fleet-wide load balancing or automatic failover.
Cross-machine stages require explicit separately packaged workflows and verified
artifact transfer, or future fleet scheduling work. Do not submit the same
workflow ID to a different worker to evade an unavailable original worker.
A single `sync --watch` services source work serially. The
[live orchestrator](ORCHESTRATOR.md) can service independent workflows through
bounded concurrent source processes, while shared publication/storage locks still
serialize their critical sections. Worker execution uses its own resource limits.

The checked-in source config has no real endpoints. It does not provision remote
machines or startup supervisors. Configure endpoints and persistent worker/source
services before expecting unattended operation following a host reboot.

## Measured validation

`tests/test_parallel_workflows.py` measures actual subprocess start/end times,
distinct PIDs/workdirs, dependency ordering, result values and origin records:

- Two worker services, two slots each: four jobs simultaneously, source queue
  closed during execution, eight independent job records returned correctly.
- One worker: concurrent ready jobs with two slots; serial execution when limited
  by one slot or the aggregate CPU, RAM, process or scratch budget.

These are repeatable local simulations with real loopback HTTP, not tests of two
physical remote hosts or native Windows/Linux machines. CI runs the portable
suite on those platforms, but its existence is not evidence that a particular
remote deployment has passed.
