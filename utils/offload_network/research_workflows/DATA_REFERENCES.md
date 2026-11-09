# Referenced data for testing stages

Since 0.6.12, an individual job or batch can declare a `data_ref`. The worker
fetches and verifies that immutable input before admitting the workflow. The
source machine needs the reference, not a local copy of the data. Tests still
receive read-only files through the existing `{input.PORT}` arguments.

Supported acquisition providers are filesystem directories (including already
mounted network storage), authenticated HTTPS, and S3/S3-compatible HTTPS
endpoints. These are separate from `dataset_ref`, which still means an already
registered worker snapshot, and `artifact_ref`, an earlier job's committed output.

## Job contract

```json
{
  "id": "test-model",
  "kind": "testing",
  "runtime": "python",
  "capsule": "REPLACE_WITH_CAPSULE_SHA256",
  "testing": {"repository": "repo", "through": "statistics"},
  "inputs": {
    "prices": {
      "mode": "data_ref",
      "source": "prices",
      "key": "frozen96/v20260909-1.tar.gz",
      "object_sha256": "REPLACE_WITH_EXACT_ARCHIVE_SHA256",
      "archive_bytes": 123456
    }
  },
  "args": ["--model", "models/candidate.py", "--data", "{input.prices}/cases.jsonl"]
}
```

The hashes and byte size above are placeholders. Supply the actual values.
Each testing/testing_stage job can use different named ports or references.
Data may be raw CSV, JSONL, NumPy, Parquet, binary or other regular files: the
selected testing backend must understand their format. The offload layer does
not reinterpret prices, dates, provenance or missing records.

`source` is an operator-approved logical location. `key` is a relative archive
key under that location, never an arbitrary URL or host path from a job. The
same logical source can map to HTTPS on one worker and a filesystem mirror on
another; the pinned object hash and size must still match. An optional
`version_id` pins an S3 object version in addition to its required SHA-256.

For existing batches, reuse the existing `data_sources` catalog:

```json
{
  "data_sources": {
    "minute-data": {
      "mode": "data_ref",
      "source": "prices",
      "key": "frozen96/v20260909-1.tar.gz",
      "object_sha256": "REPLACE_WITH_EXACT_ARCHIVE_SHA256",
      "archive_bytes": 123456
    }
  },
  "defaults": {
    "inputs": {"prices": {"mode": "source_ref", "source": "minute-data"}}
  }
}
```

This is a fragment of the existing batch request, not a new batch schema.
`source_ref` remains a batch alias resolved during planning; `data_ref` survives
in the compiled job and is resolved by the worker. A run may override a source
or explicitly prepare/select data in a dependent producer. No implicit subset
selection, provider query or source substitution is performed.

## Configure the worker's approved sources

Add `data_sources` inside `worker.json`'s existing `workflows` object:

```json
{
  "data_sources": {
    "prices": {
      "type": "https",
      "base_url": "https://data.example.com/research",
      "bearer_token_file": "/etc/offload/price-reader-token",
      "timeout_s": 300
    },
    "local-prices": {
      "type": "filesystem",
      "root": "/srv/research-snapshots"
    },
    "s3-prices": {
      "type": "s3",
      "bucket": "research-inputs",
      "prefix": "snapshots",
      "profile_name": "offload-read-only",
      "region_name": "eu-west-2"
    }
  }
}
```

Use absolute operator-local paths appropriate to macOS, Linux or Windows.
Filesystem roots are not required to be mounted at worker startup; an
unavailable source blocks acquisition rather than silently changing inputs.
HTTPS bearer tokens are optional for public objects and must be in private,
bounded credential files (mode 0600 on POSIX). HTTPS supports an optional
`ca_file` for an explicitly trusted private CA; certificate verification is
never disabled. Redirects, credential-bearing URLs and arbitrary job headers
are rejected. The HTTPS resolver does not inherit proxy settings.

S3 requires `pip install 'fleet-offload-orchestration[s3]'`. It uses the
worker's named AWS profile or normal SDK credential chain; no credentials
belong in a job. Optional `endpoint_url` must be HTTPS, and `ca_file` can supply
a private CA. See the primary [S3 GetObject documentation](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html)
and [SDK credentials documentation](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html).

Apply configuration through a controlled idle-worker restart. Existing admitted
work remains pinned to its original workflow and resolved objects; editing a
source profile does not silently remap its data. `/v2/capabilities` advertises
source names/provider types only, never endpoints, local paths or credentials.

## Prepare a raw-file snapshot once

Providers serve the existing sealed offload-object format: a deterministic
gzip/tar with `OBJECT.json` and `data/`. A generic arbitrary `.tar.gz` is not
accepted. The manifest hashes every original file and preserves its bytes.

```sh
research-offload prepare-data-reference --source /approved/raw-or-prepared-files --source-name prices --key frozen96/v20260909-1.tar.gz --out prepared-reference --max-object-mb 16384
```

This creates `object.tar.gz`, `OBJECT.json` and the ready-to-use `DATA_REF.json`.
It does not publish data or change credentials. Publish the archive at the
declared source/key using the operator's normal storage tool, then use the
reference in any job. An already retained offload object needs no repacking:
its original archive hash and size can be referenced directly.

Raw files already on a remote provider must first be exported/sealed there or
by an explicit acquisition process. This extension does not implement arbitrary
SQL queries, live feeds, SSH URLs or unpinned "latest" data. Other providers can
export snapshots to a supported location without changing testing jobs.

## Verification, retries and receipts

Planning is offline and never contacts a provider. Validation/submission
resolves references at the worker, with one acquisition at a time and no
scheduler/database control-plane lock held during transfer. Filesystem seek,
HTTPS Range and S3 Range resume a retained prefix. Servers ignoring Range may
replay an identical prefix; changed bytes fail verification.

The exact compressed size, archive hash, expanded size, file manifests, input
budgets and worker storage reserve are checked. Only fully committed objects
can be mounted. Cache hits are reverified and can work while the provider is
offline; their receipts explicitly say that the location was not contacted.

Missing/unavailable sources are retriable admission failures (HTTP 429 through
the existing source queue). Authentication, malformed references and integrity
failures are not silently retried with different inputs. Failed prefixes remain
inspectable; a corrupt complete prefix requires operator review. Resolving a
reference never creates or cancels jobs by itself.

Bound acquisition receipts are retained in worker state and included in each
job's returned output manifest. They contain declared source/key/hash, provider,
cache status and verification time, not credentials. Test containers remain
network-disabled and receive no source credentials. Transport verification is
not a scientific/PIT/comparator qualification.
