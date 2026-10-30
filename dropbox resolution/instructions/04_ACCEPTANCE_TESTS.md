# Acceptance tests for the complete application

These are **required tests to implement**, not claims that the future Dropbox application already passed them. The small executed test suite shipped under `tests/` covers only the offline bootstrap, fixed scopes, state seeding, append-only guards and hash helper. See `OFFLINE_TEST_RESULTS.txt` for those actual results.

Use synthetic fixture data and a fake Dropbox adapter first. An explicitly authorized disposable Dropbox sandbox is required for real endpoint integration tests. Do not use production IDs in sandbox fixtures.

| ID | Scenario | Required result |
|---|---|---|
| AUTH-01 | User authorizes a different account | Root confirmation fails; no production writes. |
| AUTH-02 | Token lacks a required read/write scope | Specific missing-scope error; no permission escalation or weaker verification. |
| AUTH-03 | Access token expires; refresh token valid | Refresh correctly, preserve run state and retry only safely. |
| AUTH-04 | Refresh token revoked | Authentication hold; no reset of completed operations. |
| AUTH-05 | Full Dropbox root differs from home namespace | Resolve valid path-root; do not send historical connector namespace strings blindly. |
| AUTH-06 | A recorded H01 target would otherwise pass hash checks | It remains nonexecutable until legitimate documented hold resolution. |
| IMP-01 | Import supplied package | Exactly 350 fixed batches, expected scopes and historical counts; no live-completion claims. |
| IMP-02 | Same immutable CSV imported twice | Idempotent source handling; no duplicate rows/operations. |
| IMP-03 | Previously imported source changes | Preserve new version or reject conflict; never overwrite history silently. |
| IMP-04 | IDs differ only in case | Preserve distinct opaque IDs; never lowercase them. |
| IMP-05 | Quoted CSV names contain commas/newlines/Unicode | Correct record parsing, exact values retained. |
| IMP-06 | Path traversal, zip slip or local symlink escape | Reject without writing outside the workspace. |
| IMP-07 | First-ten statuses imported | S02 failed capability and H01 retained hold do not count as successful cleanup. |
| IMP-08 | 29/18/14 identity sources plus nine flags | Preserve source rows, deduplicate by issue evidence, no 70-distinct-issues assertion. |
| INV-01 | Recursive listing returns several pages | Consume all pages; record has_more and checkpoint each page. |
| INV-02 | Crash after page commit but before next request | Resume without duplicated entries. |
| INV-03 | Cursor reset or invalid cursor | New recorded scan; retain earlier evidence. |
| INV-04 | Inaccessible nested folder | Scope marked incomplete, not absent or empty. |
| INV-05 | External file addition during scan | Record external addition and allocate supplemental scope. |
| INV-06 | Folder moves and descendant paths change | Preserve IDs, rebase current paths, invalidate stale manifests. |
| INV-07 | Incremental deletion has path but no stable ID | Do not fabricate a native stable-ID deletion receipt. |
| NAM-01 | Name already matches recorded approved destination | No-op, no second move. |
| NAM-02 | Existing stable asset suffix | Preserve it unless separately reviewed, never churn it. |
| NAM-03 | Same target basename occupied by another ID | Hold collision, no overwrite or server autorename. |
| NAM-04 | Two candidates normalize to one destination | Deterministic reviewed disambiguation before approval. |
| NAM-05 | Historical prefix matches old but not current parent | Flag stale-prefix exception, honor any H01/duplicate hold. |
| NAM-06 | Generated source and web-ready images | Preserve distinction and generation provenance. |
| NAM-07 | Case-only file/folder rename | Hold by default or execute approved two-step temporary plan with recovery. |
| BIN-01 | Empty file, short file, exact 4 MiB and multiblock hash | Match official Dropbox algorithm; distinct from ordinary file SHA-256. |
| BIN-02 | Stream returns short reads | Hash block boundaries correctly. |
| BIN-03 | File downloads but size/hash differs | Integrity failure; no cache promotion, conversion or deletion. |
| BIN-04 | Extension says BMP but actual file is JPEG | Actual-format mismatch disposition; not a completed conversion. |
| BIN-05 | Truncated/corrupt image or oversized decompression | Decode/security hold; do not disable protections globally. |
| DUP-01 | Same basename/dimensions, different bytes | Keep both. |
| DUP-02 | Same current hash/size, different immediate parents | Keep both under existing policy. |
| DUP-03 | Target also serves as active keeper/replacement | Prevent orphaning; require explicit lineage-safe resolution. |
| DUP-04 | Duplicate graph has a cycle or no survivor | Block execution. |
| DUP-05 | Target has direct link/unique revisions/comments/dependencies | Review/archive/decision as applicable; not automatically redundant. |
| DUP-06 | Sharing API returns no links for authorized user | Record limited visibility, not universal no-sharing proof. |
| DUP-07 | ID-mode history cannot exhaust available revisions | History completeness unknown; destructive action held or explicit policy decision. |
| DUP-08 | Already-absent excluded target returns later | Restoration/external-change exception, not automatic redeletion. |
| CON-01 | Ordinary eligible RGB BMP | Same dimensions, declared JPEG options, decoded JPEG and explicit lineage. |
| CON-02 | Source has transparency/high bit depth/unsupported mode | Hold, no silent flattening or data loss. |
| CON-03 | Valid ICC/EXIF/DPI exists | Preserve according to accepted policy; verify output, no incompatible ICC attachment. |
| CON-04 | Orientation would change stored dimensions | No silent transformation; explicit policy and stored/displayed dimension evidence. |
| CON-05 | Output destination already occupied | No overwrite, no automatic suffix selection after approval. |
| CON-06 | Local candidate good but remote uploaded content differs | Fail independent remote verification; retain original. |
| CON-07 | Source changes after candidate creation | New JPG not accepted as replacement for changed source. |
| CON-08 | Upload succeeds | Source BMP still present; C cannot execute Q. |
| CON-09 | Historical source unavailable for J but JPG matches history | Current JPEG integrity can pass; source comparison remains unavailable/partial unless explicit accepted policy. |
| APP-01 | Manifest contents changed after approval | Reject checksum mismatch; require new approval. |
| APP-02 | Valid approval plus unrelated active hold | Refuse execution. |
| APP-03 | Deleted target revision differs from preflight | Conditional delete conflict; no unconditional fallback. |
| APP-04 | Crash immediately before API call | Reconcile intent; no blind duplicate write. |
| APP-05 | API commits but response is lost | OUTCOME_UNKNOWN; resolve by ID/path/hash before any retry. |
| APP-06 | Server job returns mixed success/failure | Per-item outcomes, verify successes, hold failures. |
| APP-07 | Async poll fails/times out | Preserve job ID; no resubmission, resume polling/reconciliation. |
| APP-08 | Keeper concurrently disappears during target deletion | Stop destructive run, activate recovery, no orphaned success claim. |
| APP-09 | Rename content changes concurrently | Record conflict; do not overwrite or blindly undo another user's changes. |
| APP-10 | Folder move succeeds but child absent | G incomplete/failed; no dependent writes until reconciled. |
| APP-11 | File update has same size but different hash | Must fail content-preservation check. |
| APP-12 | Delete proposal accidentally contains folder | Reject before calling API. |
| RET-01 | HTTP 429 with Retry-After | Honor server backoff and record attempt. |
| RET-02 | Permission denial | Block rather than retry indefinitely. |
| RET-03 | SDK automatically retries mutating call | Configure/test so unknown outcomes are reconciled, not silently repeated. |
| RET-04 | Local disk full before backup/write intent | No destructive API call. |
| RET-05 | Database lease expires but remote outcome is unknown | Recovery required before new overlapping work. |
| VIS-01 | In Situ folder contains detail image | Detail-only classification, not full-scene coverage. |
| VIS-02 | Realistic generated room | Generated/unknown provenance unless independent evidence supports real installation. |
| VIS-03 | Group image shows repeated design | Separate unique design count from physical instances/order. |
| VIS-04 | Similar Moon/Spiral names | No alias from string similarity alone. |
| VIS-05 | Vision model proposes rename/delete | Proposal only; no executor permission. |
| VIS-06 | Private image needs external model | No transmission until explicit permission. |
| VIS-07 | Video reviewed only by sampled frames | Record sampled coverage; no exhaustive-video claim. |
| VIS-08 | Exact identical bytes in different contexts | Pixel findings may be reused with evidence; context/provenance stays distinct. |
| REC-01 | Original rollback path occupied | Hold, no overwrite. |
| REC-02 | Deleted file recoverable by revision | Approved restore and independent ID/content verification. |
| REC-03 | Revision not recoverable, verified backup available | Approved reupload, record new ID and limits to history/link restoration. |
| REC-04 | State DB copied while live | Use consistent SQLite backup, never unverified file copy. |
| REC-05 | Event/export checksum mismatch | Integrity stop and evidence-preserving recovery. |
| END-01 | Metadata review complete but identity unresolved | Separate objective states; no global complete claim. |
| END-02 | Historical event lacks stable ID | Preserve association evidence level in final report. |
| END-03 | New duplicate discovered at close-out | Supplemental review, no automatic deletion during T/Z01. |
| END-04 | Aggregate file balances | Match disjoint ID sets and explicit lineage; no double counting across workstreams. |
| END-05 | Re-run completed child | No duplicate mutation; independently verify/no-op or explicit new approved action. |
| END-06 | Malicious formula-like filename in Excel/CSV report | Safe rendering, original literal preserved in JSON. |
| END-07 | User accepts documented exception | Show accepted-by-policy, not erased or falsely passed. |

## Completion gate

The local developer must supply runnable automated tests, not merely tick this table. Log fake-adapter and live-sandbox tests separately. A successful offline importer test does not certify native Dropbox API behavior, permissions, upload quality, execution safety or visual correctness.
