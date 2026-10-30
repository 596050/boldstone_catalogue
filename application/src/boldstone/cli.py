from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .authentication import authorize, native_adapter
from .census import census
from .config import DEFAULT_CONFIG, DEFAULT_RUNTIME, initialize_config, load_config
from .controls import validate_controls
from .errors import BoldstoneError, RemoteError
from .importers import import_pack
from .reporting import checkpoint, report_all, save_review_report
from .reviews import batch_scope, run_batch
from .root import RootScope, confirm_root, discover
from .state import State, environment
from .util import canonical, redact


def parser():
    p = argparse.ArgumentParser(
        description="Boldstone Dropbox auditor and authorization setup (no content-write commands)"
    )
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    s = p.add_subparsers(dest="command", required=True)
    config = s.add_parser("config").add_subparsers(dest="config_command", required=True)
    init = config.add_parser("init")
    init.add_argument("--pack", required=True, type=Path)
    init.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    importing = s.add_parser("import")
    importing.add_argument("--pack", required=True, type=Path)
    auth = s.add_parser("auth")
    auth.add_argument(
        "--profile",
        choices=["audit", "executor"],
        default="audit",
        help="audit requests read access; executor also requests files.content.write",
    )
    auth.add_argument("--pkce", action="store_true", required=True)
    auth.add_argument("--offline", action="store_true", required=True)
    auth.add_argument("--app-key")
    auth.add_argument("--no-browser", action="store_true")
    doctor = s.add_parser("doctor")
    doctor.add_argument("--read-only", action="store_true", required=True)
    doctor.add_argument("--offline", action="store_true")
    root = s.add_parser("root").add_subparsers(dest="root_command", required=True)
    discovery = root.add_parser("discover")
    discovery.add_argument("--read-only", action="store_true", required=True)
    discovery.add_argument("--path")
    confirmation = root.add_parser("confirm")
    confirmation.add_argument("--read-only", action="store_true", required=True)
    confirmation.add_argument("--account-id", required=True)
    confirmation.add_argument("--namespace-id", required=True)
    confirmation.add_argument("--root-id", required=True)
    confirmation.add_argument("--known-file-id", action="append", required=True)
    inventory = s.add_parser("census")
    inventory.add_argument("--read-only", action="store_true", required=True)
    inventory.add_argument("--save-pages", action="store_true", required=True)
    inventory.add_argument("--resume")
    inventory.add_argument("--max-pages", type=int)
    changes = s.add_parser("changes").add_subparsers(dest="changes_command", required=True)
    poll = changes.add_parser("poll")
    poll.add_argument("--once", action="store_true", required=True)
    poll.add_argument("--resume")
    poll.add_argument("--max-pages", type=int, default=10)
    poll.add_argument("--rescan-on-reset", action="store_true")
    s.add_parser("controls").add_subparsers(dest="controls_command", required=True).add_parser(
        "validate"
    )
    s.add_parser("holds").add_subparsers(dest="holds_command", required=True).add_parser("show")
    batch = s.add_parser("batch").add_subparsers(dest="batch_command", required=True)
    listing = batch.add_parser("list")
    listing.add_argument("--limit", type=int, default=20)
    show = batch.add_parser("show")
    show.add_argument("batch_id")
    run = batch.add_parser("run")
    run.add_argument("batch_id")
    run.add_argument("--read-only", action="store_true", required=True)
    run.add_argument("--new-attempt", action="store_true")
    next_batches = batch.add_parser("run-next")
    next_batches.add_argument("--read-only", action="store_true", required=True)
    next_batches.add_argument("--max-batches", type=int, default=1)
    report = s.add_parser("report")
    report_scope = report.add_mutually_exclusive_group(required=True)
    report_scope.add_argument("--batch")
    report_scope.add_argument("--all", action="store_true")
    s.add_parser("checkpoint").add_argument(
        "--consistent-backup", action="store_true", required=True
    )
    recover = s.add_parser("recover")
    recover.add_argument("--pending", action="store_true", required=True)
    recover.add_argument("--read-only", action="store_true", required=True)
    return p


def _dispatch(args):
    if args.command == "config":
        path = None if args.config == DEFAULT_CONFIG else args.config
        config = initialize_config(args.pack, args.runtime, path)
        return {
            "objective_outcome": "LOCAL_READ_ONLY_CONFIG_CREATED",
            "config": str(config.path),
            "historical_database_existing": config.database.exists(),
            "app_key_configured": False,
        }, 0
    config = load_config(args.config)
    if args.command == "import":
        return import_pack(config, args.pack.expanduser().absolute()), 0
    if args.command == "auth":
        return authorize(
            config,
            app_key=args.app_key,
            open_browser=not args.no_browser,
            profile=args.profile,
        ), 0
    with State(config) as state, state.writer():
        state.migrate()
        if args.command == "batch" and args.batch_command in ("list", "show"):
            if args.batch_command == "show":
                batch, rows = batch_scope(state, args.batch_id)
                attempts = [
                    dict(r)
                    for r in state.conn.execute(
                        "SELECT * FROM attempts WHERE batch_id=? ORDER BY started_utc",
                        (args.batch_id,),
                    )
                ]
                return {"batch": batch, "exact_scope": rows, "attempts": attempts}, 0
            if not 1 <= args.limit <= 350:
                raise BoldstoneError("--limit must be between 1 and 350")
            return [
                dict(r)
                for r in state.conn.execute(
                    "SELECT batch_id,original_order,workstream,family_or_scope,item_count,saved_status,local_objective_state FROM batches ORDER BY original_order LIMIT ?",
                    (args.limit,),
                )
            ], 0
        if args.command == "holds":
            return {
                "active_holds": [
                    dict(r) for r in state.conn.execute("SELECT * FROM holds WHERE active=1")
                ],
                "releasing_holds_supported": False,
            }, 0
        if args.command == "controls":
            result = validate_controls(state)
            return result, 3 if result["unfinished_operations"] else 0
        if args.command == "report":
            return report_all(state, batch_id=args.batch), 0
        if args.command == "checkpoint":
            return checkpoint(state), 0
        if args.command == "recover":
            result = validate_controls(state)
            return {
                "objective_outcome": "READ_ONLY_RECOVERY_INSPECTION",
                "unfinished_operations": result["unfinished_operations"],
                "interrupted_review_attempts": result["interrupted_review_attempts"],
                "automatic_remote_retry": False,
            }, 3 if result["unfinished_operations"] else 0
        with state.run("read_only") as run:
            if args.command == "doctor" and args.offline:
                result = validate_controls(state)
                return {
                    "objective_outcome": "OFFLINE_LOCAL_CHECKS_PASSED",
                    "controls": result,
                    "environment": environment(),
                    "free_bytes": shutil.disk_usage(config.database.parent).free,
                    "app_key_configured": bool(config.dropbox["app_key"]),
                    "native_metadata_connectivity": "NOT_TESTED",
                    "native_binary_connectivity": "NOT_TESTED",
                    "independent_backup_verified": False,
                }, 0
            if (
                args.command == "batch"
                and args.batch_command == "run"
                and args.batch_id in ("S01", "I00")
            ):
                result = run_batch(state, run, args.batch_id, new_attempt=args.new_attempt)
                reports = save_review_report(state, result)
                return {**result, "reports": reports}, result["exit_code"]
            adapter = native_adapter(config)
            try:
                if args.command == "root":
                    if args.root_command == "discover":
                        result = discover(
                            adapter, args.path or config.dropbox["historical_display_path_hint"]
                        )
                        evidence = state.evidence(result, "root-discovery")
                        return {**result, "evidence": evidence}, 0
                    candidate = config.with_dropbox(
                        expected_account_id=args.account_id,
                        verified_namespace_id=args.namespace_id,
                        verified_root_folder_id=args.root_id,
                        known_file_ids=list(dict.fromkeys(args.known_file_id)),
                    )
                    print(
                        json.dumps({"scope_to_confirm": candidate.dropbox}, indent=2),
                        file=sys.stderr,
                    )
                    acknowledgement = input(
                        "Type the exact root folder ID to confirm this scope: "
                    ).strip()
                    return confirm_root(
                        state, run, adapter, candidate, acknowledgement=acknowledgement
                    ), 0
                scope = RootScope(state, run, adapter)
                if args.command == "doctor":
                    return {
                        "objective_outcome": "NATIVE_ACCOUNT_ROOT_METADATA_CONNECTED",
                        "root": scope.root,
                        "account_id": run.account_id,
                        "binary_connectivity": "NOT_TESTED_RUN_NEW_S02_ATTEMPT",
                    }, 0
                if args.command in ("census", "changes"):
                    if args.max_pages is not None and args.max_pages < 1:
                        raise BoldstoneError("--max-pages must be positive")
                    try:
                        result = census(
                            state,
                            run,
                            scope,
                            resume=args.resume,
                            incremental=args.command == "changes",
                            max_pages=args.max_pages,
                        )
                    except RemoteError as exc:
                        if exc.kind == "cursor_reset" and getattr(args, "rescan_on_reset", False):
                            result = census(state, run, scope, max_pages=args.max_pages)
                            result["prior_cursor_reset_preserved"] = True
                        else:
                            raise
                    return result, 4 if result["objective_outcome"] in (
                        "PARTIAL_ENUMERATION",
                        "ACCESS_LIMITED",
                    ) else 0
                if args.command == "batch":
                    if args.batch_command == "run":
                        selected = [(args.batch_id, args.new_attempt)]
                    else:
                        if not 1 <= args.max_batches <= 10:
                            raise BoldstoneError(
                                "Read-only scheduler permits 1 to 10 bounded batches"
                            )
                        selected = [
                            (r[0], False)
                            for r in state.conn.execute(
                                "SELECT batch_id FROM batches WHERE saved_status='Planned' AND local_objective_state='HISTORICAL_ONLY' ORDER BY original_order LIMIT ?",
                                (args.max_batches,),
                            )
                        ]
                    reports, code = [], 0
                    for batch_id, new_attempt in selected:
                        result = run_batch(
                            state, run, batch_id, scope=scope, new_attempt=new_attempt
                        )
                        report_paths = save_review_report(state, result)
                        reports.append(
                            {
                                k: result[k]
                                for k in (
                                    "batch_id",
                                    "attempt_id",
                                    "objective_outcome",
                                    "counts",
                                    "exit_code",
                                )
                            }
                        )
                        reports[-1]["reports"] = report_paths
                        code = max(code, result["exit_code"])
                        if result["exit_code"]:
                            break
                    return {"batches": reports, "remote_mutations": 0}, code
            finally:
                adapter.close()
    raise BoldstoneError("Command is not implemented")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result, code = _dispatch(args)
        print(json.dumps(redact(result), indent=2, ensure_ascii=False))
        return code
    except BoldstoneError as exc:
        print(
            canonical(
                {
                    "objective_outcome": "BLOCKED" if exc.exit_code == 3 else "FAILED",
                    "error": exc.public()
                    if isinstance(exc, RemoteError)
                    else {"message": str(exc), **exc.details},
                    "exit_code": exc.exit_code,
                }
            ),
            file=sys.stderr,
        )
        return exc.exit_code
    except (KeyboardInterrupt, EOFError):
        print('{"objective_outcome":"INTERRUPTED_NO_AUTOMATIC_RETRY"}', file=sys.stderr)
        return 4
    except OSError as exc:
        print(
            canonical(
                {
                    "objective_outcome": "LOCAL_IO_FAILED",
                    "error_type": type(exc).__name__,
                    "errno": exc.errno,
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
