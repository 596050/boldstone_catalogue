# CLI contract to implement

Only `python bootstrap.py ...` is shipped as executable software. The following is a specification for the future `boldstone` application, not an already implemented tool.

| Command | Required behavior | Dropbox writes |
|---|---|---|
| `import --pack PATH` | Verify source hashes, preserve all rows, import immutable membership, prior states and restrictions; idempotent import and reject changed source under same key. | No |
| `auth --profile audit --pkce --offline` | Interactive authorized OAuth; minimal read scopes; secrets go to OS credential store. | No content writes |
| `doctor --read-only` | Validate config, state disk/backup paths, supported dependency versions, account, metadata/content network connectivity; no fabricated test pass. | No |
| `root confirm --read-only` | Verify account/root/namespace and stable root ID; explicit local operator acknowledgement of scope. | No |
| `census --read-only --save-pages` | Full paginated current inventory; raw response evidence, safe cursor checkpoint and current-vs-baseline reconciliation. | No |
| `changes poll --once` | Process bounded incremental cursor updates; detect scope, parent and revision changes. | No |
| `controls validate` | Check protections, exclusions, holds, old approvals, lineage graph, state integrity and unfinished operations. | No |
| `batch list` / `batch show ID` | Exact scope and saved/local objective states; reference manifest hash. | No |
| `batch run ID --read-only` | Execute review only. Use `--new-attempt` for new attempts; no automatic reset of historical completion. | No |
| `batch run-next --max-batches N --read-only` | Bounded eligible read-only tasks; never approve/apply. | No |
| `plan --from ID --operation TYPE --max-items N` | Create exact immutable child manifest from eligible items; validate count limit and all exclusions. | No |
| `approval inspect ID` | Show exact changes, target/keeper/replacement IDs, preconditions, hashes, backup and open blocks. | No |
| `approval record ID --reviewer NAME` | Interactive local approval of exact manifest hash; verify authority basis. An approval never releases an unrelated hold. | No |
| `holds show` | Explain retained holds and normal owner/admin resolution evidence required. No force/bypass command. | No |
| `auth --profile executor --pkce --offline` | Separate explicit write authorization within user entitlement. | No content writes |
| `apply ID --approval ID` | Only exact approved mutations; write intent first, capture receipt, stop on unknown outcome, independent per-file verification required. | Yes, gated |
| `verify ID --fresh` | Independent server checks, downloads where required, operation attribution and end-state checks. | No |
| `recover --pending --read-only` | Reconcile ambiguous outcomes before further writes. | No |
| `rollback plan OPERATION_ID` | Produce inverse-action proposal with current conflicts/lineage and limitations. | No |
| `rollback apply MANIFEST --approval ID` | Execute only a reviewed inverse operation; independent verification. | Yes, gated |
| `visual prepare ID` | Build contact sheets and exact review membership from verified cache. | No |
| `visual review ID --human` | Record image/video observations, provenance and evidence-based identity decisions. | No |
| `report --batch ID` / `report --all` | CSV/JSON/HTML/Markdown/XLSX reports with separate outcomes, source levels and unresolved objectives. | No |
| `checkpoint --consistent-backup` | SQLite backup API, checksums, event exports and an immutable checkpoint bundle. | No by default |

Exit codes to implement: 0 objective succeeded/no-op; 2 invalid config/arguments; 3 blocked prerequisites; 4 partial; 5 definite API failure; 6 unknown remote outcome; 7 integrity failure. Do not use 0 for S02 failed capability simply because the test finished.

When a report command succeeds its exit code refers to writing the report, not cleanup completion. Include a machine-readable `objective_outcome` in report output.
