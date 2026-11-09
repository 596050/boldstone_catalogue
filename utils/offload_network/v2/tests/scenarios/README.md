# v2 scenario tests

Config-driven manifest-builder tests. Each subdirectory here is one
test case. Pytest auto-discovers them via `v2/tests/test_scenarios.py`.

## Layout

```
v2/tests/scenarios/
├── _runner.py                   ← engine (don't edit unless changing schema)
├── README.md                    ← this file
├── <scenario_name>/
│   ├── scenario.json            ← INPUT
│   ├── expected_manifest.json   ← GOLDEN (auto-generated on first run)
│   └── expected_summary.json    ← OPTIONAL, for live mode (`live: true`)
└── ...
```

## scenario.json schema

```json
{
  "name": "<human-friendly label>",
  "workflow": "random_windows | emd_cache_replay | ig_trading | generic",
  "args": {
    "<workflow-specific input bag>": "..."
  },
  "hosts": {
    "<host_alias>": {
      "type": "ssh",
      "ssh_alias": "<alias>",
      "repo": "C:/Users/.../Downloads/fleet-offload",
      "rsync_path": "C:/.../rsync.exe",
      "has_libemd": true,
      "cores": 24,
      "results_root": "c_emd/results"
    }
  },
  "job_id": 1,
  "live": false
}
```

### `args` per workflow

**random_windows**

```json
{
  "cohort": "new10",
  "host": "cdec",
  "out_subdir": null,
  "into": "live_data",
  "pipeline_args": null
}
```

**emd_cache_replay**

```json
{
  "instrument": "microsoft_260117_1000_aa2",
  "host": "cdec",
  "cadence_rows": 30,
  "extra_args": ["--trade-cost=-0.000125"]
}
```

**ig_trading**

```json
{
  "submodule": "offload_replay_status",
  "host": "cdec",
  "extra_args": ["--all"]
}
```

**generic** (free-form: any python module/script)

```json
{
  "workflow_tag": "my-custom-job",
  "module": "trading_common.some_module",
  "pass_args": ["--foo", "bar"],
  "host_results_root": null,
  "host": "cdec"
}
```

## Workflow

### Add a new scenario

```bash
mkdir v2/tests/scenarios/my_new_scenario
# Write scenario.json (see schemas above)
UPDATE_GOLDEN=1 pytest v2/tests/test_scenarios.py::ScenarioTests::test_my_new_scenario
# Inspect the generated expected_manifest.json
git add v2/tests/scenarios/my_new_scenario/
```

### After an intentional API change to a manifest builder

Re-run with `UPDATE_GOLDEN=1` to refresh all goldens, then `git diff` to
review the manifest changes before committing:

```bash
UPDATE_GOLDEN=1 pytest v2/tests/test_scenarios.py
git diff v2/tests/scenarios/
```

### Live mode (real-remote end-to-end)

Scenarios with `"live": true` additionally run the manifest on a real
remote when `V2_LIVE_TESTS=1` is set:

```bash
V2_LIVE_TESTS=1 pytest v2/tests/test_scenarios.py
```

Without that env, live scenarios skip silently. Lets CI stay fast while
the operator can do end-to-end validation before merging.

## What's normalised before diff

Volatile fields (timestamps, sha256s, sizes, absolute paths) are replaced
with portable tokens before the diff:

| Field | Placeholder |
|---|---|
| `created_at` | `<TIMESTAMP>` |
| `seal_sha256` | `<SEAL_SHA>` |
| `seal_size_bytes` | `<SEAL_SIZE>` |
| `seal_path_local` | `<SEAL_PATH>` |
| `blobs[].sha256` | `<BLOB_SHA>` |
| `blobs[].size_bytes` | `<BLOB_SIZE>` |
| `blobs[].local_src` (absolute path) | `<REPO>/...`, `<HOME>/...`, etc. |
| `result.local_dir` (per-bundle tmp) | `<TMP>/...` or `<BUNDLES>/...` |

So a manifest built today and the same manifest built next year produce
byte-identical normalised JSON — the goldens stay stable.
