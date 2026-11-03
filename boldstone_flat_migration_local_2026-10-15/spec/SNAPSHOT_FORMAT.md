# Normalized input for the offline route-preview helper

`route-preview` accepts a local snapshot produced by the live read-only adapter your coding agent implements. It cannot establish that the snapshot is actually current or authentic, and its output never authorizes or executes changes.

```json
{
  "schema": "boldstone-flat-snapshot-v1",
  "account_id": "actual-authorized-account-id",
  "root_id": "actual-root-folder-id",
  "root_display_path": "/BOLDSTONE MASTER/Products/01 Wall Sculptures",
  "observed_at_utc": "actual-observation-time",
  "complete": true,
  "has_more": false,
  "folders": [
    {"id": "actual-family-id", "parent_id": "actual-root-folder-id", "name": "Actual Family", "relative_path": "Actual Family"},
    {"id": "actual-leaf-id", "parent_id": "actual-family-id", "name": "Actual Leaf", "relative_path": "Actual Family/Actual Leaf"}
  ],
  "files": [
    {"id": "actual-file-id", "parent_id": "actual-leaf-id", "name": "source.jpg", "relative_path": "Actual Family/Actual Leaf/source.jpg", "rev": "actual-revision", "size": 12345, "content_hash": "actual-dropbox-content-hash", "media_kind": "image"}
  ]
}
```

The example numbers and identifiers are placeholders. Include every folder below the root, excluding the root itself. Include every live file in scope. `media_kind` is `image`, `video`, `other`, or `unverified`; document the actual evidence used to assign it. Preserve exact IDs and individual component names. Resolve parents from fresh data; do not fill them by guessing historical paths. Keep the native raw evidence and API request context alongside this normalized representation.

Usage, once that adapter and snapshot exist:

```bash
python3 tools/check_flat_plan.py route-preview /local/path/live-snapshot.json --out /local/path/new-route-preview.json
```

Add `--decisions /local/path/reviewed-folder-decisions.csv` to preview operator-recorded storage decisions. This does not validate signatures, backup availability, live permissions or file-level mutation approval. The helper remains offline and every result has `executable: false`.
