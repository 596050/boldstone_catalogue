from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from .binary_cache import check_binary, require_capability
from .controls import validate_controls
from .errors import Blocked, IntegrityError, RemoteError
from .historical_bootstrap import primary_ids, read_csv, safe_member
from .identity import consolidate_identity
from .naming import assess_name
from .source_comparison import compare_verified_local_source
from .util import canonical, digest, file_sha256


def batch_scope(state, batch_id):
    batch = state.conn.execute("SELECT * FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
    if not batch:
        raise Blocked("Unknown batch ID")
    path = safe_member(state.config.pack, batch["manifest_path"])
    if file_sha256(path) != batch["manifest_sha256"]:
        raise IntegrityError("Fixed batch CSV checksum changed")
    rows = read_csv(path)
    saved = list(
        state.conn.execute(
            "SELECT * FROM batch_members WHERE batch_id=? ORDER BY row_number", (batch_id,)
        )
    )
    if len(rows) != batch["item_count"] or len(rows) != len(saved):
        raise IntegrityError("Fixed batch membership count changed")
    for number, (row, member) in enumerate(zip(rows, saved, strict=True), 1):
        if member["row_number"] != number or member["row_sha256"] != digest(row):
            raise IntegrityError("Fixed batch membership content changed")
    return dict(batch), rows


def _held(state, asset_id):
    return [
        dict(r)
        for r in state.conn.execute(
            "SELECT hold_id,hold_kind,reason FROM holds WHERE asset_id=? AND active=1", (asset_id,)
        )
    ]


def _metadata_review(state, scope, row, asset_id, siblings):
    metadata = scope.resolve(asset_id, expected_kind="file")
    baseline = row.get("Original byte size")
    current = {
        "asset_id": asset_id,
        "metadata": metadata,
        "baseline_size": int(baseline) if baseline else None,
        "baseline_size_match": metadata.get("size") == int(baseline) if baseline else None,
        "content_integrity": "server_metadata_only_not_downloaded",
        "holds": _held(state, asset_id),
        "historical_completed_rename_exclusion": bool(
            state.conn.execute(
                "SELECT 1 FROM exclusions WHERE asset_id=? AND exclusion_kind='do_not_replay_recorded_rename'",
                (asset_id,),
            ).fetchone()
        ),
    }
    duplicate = row.get("Historical duplicate target", "").lower() == "true"
    identity_hold = bool(
        state.conn.execute(
            """SELECT 1 FROM batch_members WHERE
        batch_id IN ('I001','I002','I003','I004','I005','I006','I007','I008','I009')
        AND primary_object_id IN (SELECT value FROM json_each(?))""",
            (canonical(metadata.get("ancestor_folder_ids", [])),),
        ).fetchone()
    )
    name = assess_name(
        metadata,
        row,
        scope.path,
        held=bool(current["holds"]) or identity_hold,
        duplicate_target=duplicate,
    )
    current.update(name)
    if current["baseline_size_match"] is False:
        current["outcome"] = "HELD_SIZE_CHANGED_REQUIRES_REVIEW"
        current["proposed_name"] = None
    if current.get("proposed_name"):
        parent = metadata["parent_folder_id"]
        if parent not in siblings:
            siblings[parent] = scope.list_all(parent, recursive=False)
        collisions = [
            m["id"]
            for m in siblings[parent]
            if m.get("id") != asset_id
            and m.get(".tag") != "deleted"
            and m.get("name", "").casefold() == current["proposed_name"].casefold()
        ]
        if collisions:
            current.update(outcome="HELD_COLLISION", colliding_ids=collisions, proposed_name=None)
    return current


def _pair_review(state, scope, row, target_id, keeper_id, *, held_batch=False):
    target = scope.resolve(target_id, expected_kind="file")
    keeper = scope.resolve(keeper_id, expected_kind="file")
    holds = _held(state, target_id)
    protected = bool(
        state.conn.execute("SELECT 1 FROM protections WHERE asset_id=?", (target_id,)).fetchone()
    )
    same_parent = target["parent_folder_id"] == keeper["parent_folder_id"]
    size_equal = target.get("size") is not None and target.get("size") == keeper.get("size")
    hash_equal = bool(target.get("content_hash")) and target.get("content_hash") == keeper.get(
        "content_hash"
    )
    evidence = {
        "asset_id": target_id,
        "keeper_id": keeper_id,
        "target": target,
        "keeper": keeper,
        "same_immediate_parent": same_parent,
        "same_size": size_equal,
        "same_server_hash": hash_equal,
        "protected_target": protected,
        "holds": holds,
        "deletion_eligible": False,
        "backup_verified": False,
        "publication_dependencies_reviewed": False,
    }
    for key, method in (
        ("direct_sharing", scope.adapter.links),
        ("available_history", scope.adapter.revisions),
    ):
        try:
            evidence[key] = method(target_id)
            state.evidence(evidence[key], key)
        except RemoteError as exc:
            evidence[key] = {"outcome": "unknown", "error": exc.public()}
    if target_id == keeper_id:
        evidence["outcome"] = "REJECTED_SAME_ID"
    elif held_batch or holds:
        evidence["outcome"] = "REVIEW_FINISHED_HOLD_RETAINED"
    elif protected:
        evidence["outcome"] = "HELD_PROTECTED_TARGET"
    elif not same_parent:
        evidence["outcome"] = "REJECTED_DIFFERENT_IMMEDIATE_PARENTS"
    elif not size_equal or not hash_equal:
        evidence["outcome"] = "REJECTED_CONTENT_EQUALITY_NOT_ESTABLISHED"
    else:
        evidence["outcome"] = "HELD_HISTORY_BACKUP_PUBLICATION_REVIEW"
    return evidence


def _folder_review(scope, row, asset_id):
    folder = scope.resolve(asset_id, expected_kind="folder")
    descendants = scope.list_all(asset_id, recursive=True)
    return {
        "asset_id": asset_id,
        "outcome": "FOLDER_REVIEW_RECORDED_NAMING_DECISION_PENDING",
        "metadata": folder,
        "historical_label": row.get("Original relative path"),
        "descendant_ids": [m.get("id") for m in descendants if m.get("id")],
        "descendants": descendants,
        "proposed_name": None,
        "folder_merge_authorized": False,
        "semantic_identity_reviewed": False,
    }


def _bmp_review(state, run, scope, row, asset_id):
    binary = check_binary(state, run, scope, asset_id, expected_format="BMP")
    evidence = {"asset_id": asset_id, "binary": binary, "conversion_approved": False}
    if binary["exit_code"]:
        return {**evidence, "outcome": binary["objective_outcome"]}
    image = binary["image"]
    holds = _held(state, asset_id)
    protected = bool(
        state.conn.execute("SELECT 1 FROM protections WHERE asset_id=?", (asset_id,)).fetchone()
    )
    associated = bool(
        state.conn.execute(
            "SELECT 1 FROM lineage WHERE from_asset_id=? AND relation='converted_to'", (asset_id,)
        ).fetchone()
    )
    metadata = scope.resolve(asset_id, expected_kind="file")
    destination = PurePosixPath(metadata["name"]).stem + "__from-bmp.jpg"
    siblings = scope.list_all(metadata["parent_folder_id"], recursive=False)
    occupied = any(
        m.get(".tag") != "deleted" and m.get("name", "").casefold() == destination.casefold()
        for m in siblings
    )
    if holds:
        outcome = "HELD_EXISTING_RESTRICTION"
    elif row.get("Historical duplicate target", "").lower() == "true":
        outcome = "REDUNDANT_TARGET_AWAITING_DUPLICATE_DECISION"
    elif associated:
        outcome = "HISTORICAL_REPLACEMENT_ASSOCIATION_NEEDS_QA"
    elif protected:
        outcome = "PROTECTED_KEEPER_REQUIRES_LINEAGE_REVIEW"
    elif (
        image["mode"] not in ("RGB", "L")
        or image["transparency"]
        or image["frame_count"] != 1
        or image["icc_valid"] is False
    ):
        outcome = "HELD_UNSUPPORTED_FIDELITY_PROPERTIES"
    elif occupied:
        outcome = "HELD_JPG_DESTINATION_OCCUPIED"
    else:
        outcome = "ELIGIBLE_FOR_CONVERSION_POLICY_REVIEW"
    return {
        **evidence,
        "outcome": outcome,
        "holds": holds,
        "proposed_destination_name": destination,
        "jpeg_policy_accepted": False,
        "original_retained": True,
    }


def run_batch(state, run, batch_id, *, scope=None, new_attempt=False):
    batch, rows = batch_scope(state, batch_id)
    if batch_id not in ("I00", "S01") and scope is None:
        raise Blocked("A verified read-only Dropbox scope is required")
    if batch_id.startswith(("B", "J")):
        require_capability(state, scope)
    attempt = state.start_attempt(run, batch_id, new_attempt)
    results, extras, siblings = [], {}, {}
    exit_code = 0
    try:
        if batch_id == "I00":
            extras = consolidate_identity(state, run)
            results = [
                {
                    "asset_id": None,
                    "outcome": "HISTORICAL_SOURCES_LINKED_RECONCILIATION_PENDING",
                    **extras,
                }
            ]
            outcome, complete, exit_code = "PARTIAL_IDENTITY_CONSOLIDATION", False, 4
        elif batch_id == "S01":
            extras = validate_controls(state)
            results = [
                {"asset_id": None, "outcome": "LOCAL_CONTROLS_VALIDATED", "controls": extras}
            ]
            outcome, complete = "LOCAL_CONTROLS_VALIDATED", True
        else:
            for row in rows:
                asset_id, related = primary_ids(row)
                try:
                    if batch_id.startswith("M"):
                        result = _metadata_review(state, scope, row, asset_id, siblings)
                    elif batch_id == "S02":
                        expected = "BMP" if "BMP" in row["Role"] else "JPEG"
                        binary = check_binary(state, run, scope, asset_id, expected_format=expected)
                        exit_code = max(exit_code, binary["exit_code"])
                        result = {
                            "asset_id": asset_id,
                            "outcome": binary["objective_outcome"],
                            "binary": binary,
                        }
                    elif batch_id.startswith("J"):
                        binary = check_binary(state, run, scope, asset_id, expected_format="JPEG")
                        exit_code = max(exit_code, binary["exit_code"])
                        result = {
                            "asset_id": asset_id,
                            "related_source_id": related,
                            "outcome": "JPG_INTEGRITY_VERIFIED_SOURCE_COMPARISON_PENDING"
                            if not binary["exit_code"]
                            else binary["objective_outcome"],
                            "binary": binary,
                            "fresh_source_equivalence_verified": False,
                            "historical_observed_bytes": row.get("Observed bytes"),
                            "source_comparison": compare_verified_local_source(
                                state, scope, related, binary
                            )
                            if not binary["exit_code"]
                            else {"source_status": "NOT_ASSESSED_JPG_CHECK_FAILED"},
                        }
                    elif batch_id.startswith("D") or batch_id == "H01":
                        result = _pair_review(
                            state, scope, row, asset_id, related, held_batch=batch_id == "H01"
                        )
                    elif batch_id.startswith("F"):
                        result = _folder_review(scope, row, asset_id)
                    elif batch_id.startswith("B"):
                        result = _bmp_review(state, run, scope, row, asset_id)
                        exit_code = max(exit_code, result["binary"]["exit_code"])
                    elif batch_id.startswith("I"):
                        folder = scope.resolve(asset_id, expected_kind="folder")
                        descendants = scope.list_all(asset_id, recursive=True)
                        result = {
                            "asset_id": asset_id,
                            "outcome": "VISUAL_REVIEW_REQUIRED",
                            "folder": folder,
                            "candidate_ids": [
                                m["id"] for m in descendants if m.get(".tag") == "file"
                            ],
                            "actual_content_examined": False,
                            "accepted_identity_decisions": [],
                        }
                    else:
                        raise Blocked("This release only implements fixed read-only review batches")
                except (RemoteError, Blocked) as exc:
                    exit_code = max(exit_code, exc.exit_code)
                    result = {
                        "asset_id": asset_id,
                        "outcome": "UNRESOLVED_READ_OR_SCOPE",
                        "error": exc.public()
                        if isinstance(exc, RemoteError)
                        else {"message": str(exc), **exc.details},
                    }
                results.append(result)
                with state.conn:
                    state.conn.execute(
                        "INSERT INTO review_results VALUES (?,?,?,?,?)",
                        (attempt, len(results), asset_id, result["outcome"], canonical(result)),
                    )
                    run.heartbeat()
            complete = exit_code == 0
            if batch_id == "S02":
                outcome = "CAPABILITY_PASSED" if complete else "CAPABILITY_FAILED"
            elif batch_id.startswith("J"):
                outcome, complete, exit_code = (
                    "PARTIAL_JPG_QA_SOURCE_EQUIVALENCE_PENDING",
                    False,
                    max(exit_code, 4),
                )
            elif batch_id == "H01":
                outcome, complete, exit_code = (
                    "REVIEW_FINISHED_HOLDS_RETAINED",
                    False,
                    max(exit_code, 3),
                )
            elif batch_id.startswith(("I", "F")):
                outcome, complete, exit_code = (
                    "PARTIAL_SEMANTIC_REVIEW_REQUIRED",
                    False,
                    max(exit_code, 4),
                )
            else:
                outcome = (
                    "REVIEW_RECORDED_WITH_CLASSIFIED_EXCEPTIONS" if complete else "PARTIAL_REVIEW"
                )
        if batch_id in ("I00", "S01"):
            with state.conn:
                for number, result in enumerate(results, 1):
                    state.conn.execute(
                        "INSERT INTO review_results VALUES (?,?,?,?,?)",
                        (
                            attempt,
                            number,
                            result.get("asset_id"),
                            result["outcome"],
                            canonical(result),
                        ),
                    )
        counts = dict(Counter(r["outcome"] for r in results))
        state.finish_attempt(run, attempt, outcome, counts, extras, complete=complete)
        return {
            "batch_id": batch_id,
            "attempt_id": attempt,
            "objective_outcome": outcome,
            "exit_code": exit_code,
            "historical_saved_status": batch["saved_status"],
            "manifest_sha256": batch["manifest_sha256"],
            "counts": counts,
            "results": results,
            "details": extras,
            "remote_mutations": 0,
            "proposed_changes_applied": 0,
        }
    except BaseException as exc:
        state.finish_attempt(
            run,
            attempt,
            "INTERRUPTED_OR_FAILED_REVIEW",
            dict(Counter(r["outcome"] for r in results)),
            {"error_type": type(exc).__name__, "processed_rows": len(results)},
            complete=False,
        )
        raise
