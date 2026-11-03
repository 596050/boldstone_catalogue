# Test and acceptance matrix

The included 28 standard-library tests cover OFFLINE proposal import, structural routing previews, collision/hold classification and schema controls. They do not test production Dropbox behavior. Actual results are in `evidence/OFFLINE_TEST_RESULTS.txt`.

The following live-adapter/integration tests must be implemented and run by the local coding agent before production execution. All are NOT RUN in this preparation.

| ID | Required test | Required result |
|---|---|---|
| LIVE-01 | Wrong account or namespace | Refuse production planning/application; no writes. |
| LIVE-02 | Wrong root ID or relocated family | Hold rather than substitute same-named folder. |
| LIVE-03 | Short/empty intermediate page with has_more=true | Continue pagination; no premature complete status. |
| LIVE-04 | New direct file in empty wrapper | Preserve and hold; no recursive wrapper deletion. |
| LIVE-05 | Unknown family-root image | Explicit unallocated outcome; no silent nearest-leaf guess. |
| LIVE-06 | Nested parent/child different routes | Every file routed once by immediate parent ID. |
| LIVE-07 | Two distinct files with identical basename/content | Preserve both IDs and bytes under explicit collision plan. |
| LIVE-08 | Original and web derivative sharing a subject | Preserve both renditions and provenance. |
| LIVE-09 | Third-party destination folder at target path | Hold; no implicit adoption/merge. |
| LIVE-10 | Exact file already at target | No-op; no new attributed move without evidence. |
| LIVE-11 | Source content changes after manifest approval | Preflight fails, affected approval invalidated. |
| LIVE-12 | Destination parent moved after approval | Stop; never follow stale path to wrong parent. |
| LIVE-13 | Case-only folder change | Two journaled hops, same folder ID, verified descendants. |
| LIVE-14 | Crash after first case hop | Recover actual current state, not repeat first hop blindly. |
| LIVE-15 | Move succeeds but response is lost | OUTCOME_UNKNOWN; reconcile before another submission. |
| LIVE-16 | Async batch partial failure | Each result recorded, successful entries verified and not replayed. |
| LIVE-17 | Rate limit or namespace contention | Honor retry/backoff; no unlimited hidden mutation replay. |
| LIVE-18 | Shared-folder boundary or ownership-transfer requirement | Hold; no escalation or transfer flag fallback. |
| LIVE-19 | Failed binary backup hash | Mutation blocked; no trust in placeholder or incomplete bytes. |
| LIVE-20 | Unapproved provisional label | No applied route; identity remains unresolved. |
| LIVE-21 | Explicit provisional storage acceptance | Mechanical route may run; identity/publication status stays unresolved. |
| LIVE-22 | Empty-folder archive race with new arriving file | No deletion; detect unexpected archived content and stop/reconcile. |
| LIVE-23 | Azure source unexpectedly mixed | Do not move unknown images as video-only wholesale. |
| LIVE-24 | H01 target mutation with unclear hold scope | Hold new mutation; never clear deletion hold implicitly. |
| LIVE-25 | Previous 203 rename file newly needs a flat move | Do not replay old rename; require a new approved operation and preserve ID. |
| LIVE-26 | Protected keeper moves | Preserve exact ID/hash and update dependent path references. |
| LIVE-27 | Worker killed after intent commit/before network | Recovery proves source unchanged before resubmission. |
| LIVE-28 | Worker killed after remote success/before local status | Resolve by ID and saved job state; avoid duplicate side effects. |
| LIVE-29 | Local database backup and outbox recovery | Consistent evidence state; append-only facts survive. |
| LIVE-30 | Rollback with collaborator's subsequent edits | Hold conflict rather than overwrite newer content. |
| LIVE-31 | Final file conservation across wall/video roots | Every starting file ID, size and hash accounted for or an explicit outside-change exception. |
| LIVE-32 | Final structural audit including empty folders | No fourth-level folders, no loose images, exact approved leaves. |
| LIVE-33 | Scan after clean no-op rerun | Zero unneeded creates/moves; no suffix accumulation. |
| LIVE-34 | Full disposable end-to-end fixture | Snapshot, plan, backup, approve, apply, verify, retire, audit and rollback all supported. |

Integration fixtures must include a nested Fingerprint-like branch, a Wall Circle-like source/web-ready tree, direct family files, mixed file types, case-only changes, occupied destinations, duplicate bytes, held files and concurrent-change simulations. Disposable test roots require their own explicit authorization and must never be confused with production by path substitution alone.
