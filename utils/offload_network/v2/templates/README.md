# v2 batch templates

Starter kit for running a new batch (cache builds → replays → diagnostics)
without hand-writing every JSON file.

## Operator workflow

```bash
# 1. Copy the workload config template + fill in the gaps
cp v2/templates/workload.example.json /path/to/myrun/workload.json
$EDITOR /path/to/myrun/workload.json

# 2. Generate specs + batch.json from the config
python3 -m v2.template generate --workload /path/to/myrun/workload.json --out /path/to/myrun/

# 3. (Optional) Dry-run: walks the DAG, dispatches nothing, proves every
#    spec autobundles and topology is sane
python3 -m v2 batch submit /path/to/myrun/batch.json --dry-run

# 4. If skip_cache_for is used, pre-stage those large .mat files first.
#    This keeps cache blobs outside sealed job/result archives.
python3 -m v2 batch prestage-cache-stage /path/to/myrun/batch.json

# 5. Real run, with resumable state
python3 -m v2 batch submit /path/to/myrun/batch.json \
    --state-file states/scopes/v2_bundles/myrun_state.json

# 6. Check on it later
python3 -m v2 batch status states/scopes/v2_bundles/myrun_state.json

# 7. If interrupted, resume from the same state file
python3 -m v2 batch resume /path/to/myrun/batch.json \
    --state-file states/scopes/v2_bundles/myrun_state.json
```

## workload.json schema

```json
{
  "name": "<batch label>",
  "roots": {
    "RUN":        "/Users/.../runs/<run_id>",
    "REPLAY":     "/Users/.../runs/<run_id_prepared>",
    "CACHE_ROOT": "/Volumes/.../generated_caches/<...>",
    "PRESTAGED_CACHE_ROOT": "C:/sealed/prestaged_caches"
  },
  "instruments": [
    {"key": "amazon",     "id": "amazon_260117_1000_aa2"},
    {"key": "naturalgas", "id": "naturalgas_260117_1000_aa2"}
  ],
  "cadences": [
    {"key": "30m", "rows": 30},
    {"key": "1h",  "rows": 60},
    {"key": "3h",  "rows": 180}
  ],
  "phases": ["cache", "replay", "diagnostics"],
  "skip_cache_for": ["amazon"],
  "host_pool":               ["cdec", "scan-new", "kenne"],
  "max_parallel_per_host":   2,
  "max_parallel_total":      8,
  "on_failure":              "skip_dependents"
}
```

The generator emits:

```
/path/to/myrun/
├── batch.json                              ← top-level: roots + jobs glob + policy
├── jobs/
│   ├── cache.naturalgas.json
│   ├── cache.oil.json
│   ├── ...
│   ├── replay.amazon.30m.json
│   ├── replay.amazon.1h.json
│   ├── ...
│   ├── diagnostics.amazon.30m.json
│   └── ...
```

`skip_cache_for` lets you mark instruments whose cache already exists.
The generator emits a lightweight `cache_stage` job for each one. Before
submitting the batch, run `batch prestage-cache-stage`; it rsyncs the
large `.mat` files directly to each assigned host with resume/progress.
Those `.mat` files are not embedded in sealed job archives.

## What gets bundled per phase

Defined by the templates in this directory:

| phase | entry | bundle | remote_refs |
|---|---|---|---|
| cache | `model_research/implementations/build_cutoff_emd_cache.py` | code (trading_common, c_emd/python, UOA helper paths, iq_feed tempFinal converter) + cache_jobs/<inst>.json | — |
| cache_stage | `utils/offload_network/v2/drivers/cache_stage.py` | code only; source `.mat` must be pre-staged under `<PRESTAGED_CACHE_ROOT>/<batch>/<inst>/` | — |
| replay | `trading_common.strategy_testing.emd_cache_replay` (module) | code only | cache.<inst> → `outputs/cache/*.mat` |
| diagnostics | `$REPLAY/run_diagnostics.sh` | the shell script | replay.<inst>.<cadence> → `outputs/` |

`replay.X.<cadence>` has affinity to `cache.X` so the .mat stays on the
host without round-tripping through Mac. `diagnostics.X.<cadence>` has
affinity to `replay.X.<cadence>` for the same reason.

## Customising the templates

Edit the JSON files in this directory:
- `cache.template.json`     — cache phase
- `replay.template.json`    — replay phase
- `diagnostics.template.json` — diagnostics phase

The template uses these placeholders:
- `<<INST_KEY>>`  → e.g. `naturalgas`
- `<<INST_ID>>`   → e.g. `naturalgas_260117_1000_aa2`
- `<<CAD_KEY>>`   → e.g. `30m`
- `<<CAD_ROWS>>`  → e.g. `30`
- `<<BATCH_NAME>>` → workload `name`, used for remote pre-stage paths

Just substitute these strings in any template field (name, args, env,
outputs.pull paths, etc.). The generator does the substitution.
