# Commands to implement in the live local application

These are requirements, NOT executable commands supplied by this package. The sole supplied utility is `python3 tools/check_flat_plan.py`, which is offline. Integrate these commands into an existing tested local application or implement a new adapter. Use help output and integration tests before use.

| Proposed command | Contract |
|---|---|
| `boldstone-flat auth` | PKCE authorization, minimum scopes, OS credential store. No file writes. |
| `boldstone-flat bind-root` | Display and record account, namespace, root and sample family IDs for operator confirmation. |
| `boldstone-flat import --package <directory>` | Import source rows and protections; never collapse intentional repeated family IDs. |
| `boldstone-flat snapshot --out <path>` | Exhaust recursive file/folder pagination; capture raw evidence plus normalized snapshot. |
| `boldstone-flat drift --snapshot <id>` | Reconcile older folders and file controls by stable ID, not old path. |
| `boldstone-flat review-targets` | Record storage decisions separately from identity verification; no self-approval. |
| `boldstone-flat plan --family <exact-name>` | Generate canonical folder choices, direct-file routes, collisions, provenance, dependencies and holds. No writes. |
| `boldstone-flat backup --manifest <id>` | Save and hash-check exact source revisions outside synchronization. No remote mutations. |
| `boldstone-flat approve --manifest <id> --sha256 <digest>` | Bind explicit operator approval to immutable manifest; do not alter pending source decisions. |
| `boldstone-flat apply --child <id> --approval <id>` | Preflight, journal, execute exact creates/moves with no overwrite/deletion, then independently verify. |
| `boldstone-flat verify --child <id>` | Fresh reads of exact IDs/parents/hashes and unrelated membership checks. |
| `boldstone-flat recover --run <id>` | Reconcile unknown requests before any retry; no blind replay. |
| `boldstone-flat retire-empty --manifest <id>` | Fresh zero-file-and-zero-child check, approved external archive move, post-archive race check. |
| `boldstone-flat audit --run <id>` | Fresh end-state inventory, exact depth, target names, file-ID/byte/hash conservation and exceptions. |
| `boldstone-flat rollback-plan --run <id>` | Propose dependency-aware inverse actions from actual outcomes. No rollback writes until approval. |
| `boldstone-flat export --run <id>` | Reports, manifest evidence, authoritative database backup, derived CSV/workbook and checksums. |

Required stage order: import/bind -> fresh snapshot -> storage decisions -> dry plan -> source backup -> exact approval -> pilot apply/verify -> more approved families -> external exceptions -> empty-folder retirement -> final audit/report. Recover uncertain earlier operations before scheduling new ones.

The CLI must not accept `--force` to bypass holds, permissions, missing backups, unknown outcomes or conflicts. It must not offer a wildcard bulk-delete function. An executor with write scope must have an application-level allowlist, because the OAuth content-write scope is broader than the allowed move-only behavior.
