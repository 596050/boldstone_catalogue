# Bounded JSON stream I/O probe

`io_probe.py` measures synthetic JSON serialization and file flush/fsync in any
selected job runtime. It has no model, source archive, comparator or metric
defaults. The caller declares row count, repetitions, buffers and a byte budget.
Every trial's raw writes are counted and its complete bytes are checked against
one independently serialized payload. Buffer order alternates between rounds.

```sh
python3 utils/offload_network/research_workflows/io_probe.py \
  --directory new-io-trials --output IO_PROBE.json \
  --rows 2048 --rounds 3 --buffer-bytes default 1048576 \
  --max-bytes 16777216
```

Existing trial directories and reports are refused. Synthetic trial files are
retained; the probe does not clean up existing files or worker state. It caps the
declared trial bytes at 64 MiB and validates the request before creating scratch.
The normal Python file buffer is measured with `default`; its size and the Python
version are reported rather than assumed equal across runtimes. The probe fails
if raw-write instrumentation cannot account for every byte.

For local offload, use the ordinary `plan` and `local` commands. Select only
`io_probe.py` into the job capsule, use it as the entrypoint, give `--directory` a
new relative scratch directory, and pass `{output.report}/PROBE.json` as output
for a tree port at `artifacts/report`. No special queue or worker is required.
Choose an existing approved image, explicit scratch/output limits and the normal
free-space reserve. `max_input_mb` belongs in `--runtime-resources`, not the
per-job `resources` mapping. Collect and verify the result normally.

The reported intervals are measurements under the observed shared load. They do
not include source packaging, atomic report publication, directory durability,
storage-budget scans, result collection or market simulation. One paired trial
can regress while the median improves. Do not convert these numbers into a
general disk-speed claim, an end-to-end replay speedup or model improvement.
Raw-write instrumentation adds common overhead. No running job is modified.
