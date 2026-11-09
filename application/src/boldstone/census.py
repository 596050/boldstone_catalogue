from __future__ import annotations

import json

from .errors import Blocked, IntegrityError, RemoteError
from .util import canonical, digest, new_id, parent_path, utc_now, within_path


def _invalidate(state, run, scan_id, asset_id, reason, details):
    invalidation = new_id("invalidation")
    state.conn.execute(
        "INSERT INTO change_invalidations VALUES (?,?,?,?,?,?)",
        (invalidation, scan_id, asset_id, reason, utc_now(), canonical(details)),
    )
    # Conservative: all pending manifests are invalidated on a folder/path change.
    if reason in ("folder_moved", "path_deleted"):
        manifests = state.conn.execute("SELECT manifest_sha256 FROM manifests").fetchall()
    else:
        manifests = state.conn.execute(
            """SELECT DISTINCT m.manifest_sha256 FROM manifests m
            LEFT JOIN operations o ON o.manifest_id=m.manifest_id
            WHERE o.source_id=? OR o.keeper_id=? OR o.replacement_id=? OR m.json_payload LIKE ?""",
            (asset_id, asset_id, asset_id, "%" + (asset_id or "") + "%"),
        ).fetchall()
    state.conn.executemany(
        "INSERT OR IGNORE INTO manifest_invalidations VALUES (?,?)",
        ((row[0], invalidation) for row in manifests),
    )
    if asset_id:
        state.conn.execute(
            "UPDATE work_items SET state='INVALIDATED_EXTERNAL_CHANGE' WHERE asset_id=? OR related_asset_id=?",
            (asset_id, asset_id),
        )
    state.event(
        "asset",
        asset_id or details.get("path_lower", "unknown"),
        "external_change_observed",
        {"reason": reason, "invalidation_id": invalidation},
        run.id,
    )


def _ingest(state, run, scan_id, metadata, *, incremental):
    conn = state.conn
    path = metadata.get("path_lower")
    if metadata.get(".tag") == "deleted":
        # Path tombstones update the derived map. They never become native deletion receipts.
        matches = conn.execute(
            "SELECT * FROM current_assets WHERE namespace_id=? AND account_id=? AND root_folder_id=?",
            (run.namespace_id, run.account_id, run.root_id),
        ).fetchall()
        for old in matches:
            if within_path(old["path_lower"], path):
                conn.execute(
                    "UPDATE current_assets SET status='not_observed_after_path_tombstone',updated_utc=? WHERE asset_id=?",
                    (utc_now(), old["asset_id"]),
                )
        for entry in conn.execute(
            "SELECT asset_id,metadata_json FROM inventory_entries WHERE scan_id=?", (scan_id,)
        ).fetchall():
            if within_path(json.loads(entry["metadata_json"]).get("path_lower"), path):
                conn.execute(
                    "DELETE FROM inventory_entries WHERE scan_id=? AND asset_id=?",
                    (scan_id, entry["asset_id"]),
                )
        _invalidate(
            state,
            run,
            scan_id,
            None,
            "path_deleted",
            {"path_lower": path, "attribution": "path_tombstone_not_app_deletion"},
        )
        return
    asset_id = metadata.get("id")
    if not asset_id:
        raise IntegrityError("Present listing entry lacks a stable ID")
    old = conn.execute("SELECT * FROM current_assets WHERE asset_id=?", (asset_id,)).fetchone()
    if old:
        if (old["account_id"], old["namespace_id"], old["root_folder_id"]) != (
            run.account_id,
            run.namespace_id,
            run.root_id,
        ):
            raise IntegrityError("Current asset map belongs to a different confirmed scope")
        changed = any(
            (old[key] != metadata.get(field))
            for key, field in (
                ("path_lower", "path_lower"),
                ("revision", "rev"),
                ("content_hash", "content_hash"),
            )
        )
        if changed:
            folder_moved = metadata.get(".tag") == "folder" and old["path_lower"] != path
            reason = "folder_moved" if folder_moved else "path_or_revision_changed"
            _invalidate(
                state,
                run,
                scan_id,
                asset_id,
                reason,
                {"old": json.loads(old["metadata_json"]), "new": metadata},
            )
            if folder_moved:
                for child in conn.execute(
                    "SELECT asset_id,path_lower FROM current_assets WHERE namespace_id=? AND account_id=? AND root_folder_id=?",
                    (run.namespace_id, run.account_id, run.root_id),
                ).fetchall():
                    if child["asset_id"] != asset_id and within_path(
                        child["path_lower"], old["path_lower"]
                    ):
                        derived = path + child["path_lower"][len(old["path_lower"]) :]
                        conn.execute(
                            "UPDATE current_assets SET path_lower=?,path_display=NULL,status='derived_path_needs_refresh',updated_utc=? WHERE asset_id=?",
                            (derived, utc_now(), child["asset_id"]),
                        )
    elif incremental:
        state.event("asset", asset_id, "supplemental_asset_observed", {"scan_id": scan_id}, run.id)
    conn.execute(
        """INSERT INTO current_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(asset_id) DO UPDATE SET namespace_id=excluded.namespace_id,
        account_id=excluded.account_id,root_folder_id=excluded.root_folder_id,
        path_lower=excluded.path_lower,path_display=excluded.path_display,parent_folder_id=NULL,
        revision=excluded.revision,content_hash=excluded.content_hash,byte_size=excluded.byte_size,
        kind=excluded.kind,status=excluded.status,latest_scan_id=excluded.latest_scan_id,
        metadata_json=excluded.metadata_json,updated_utc=excluded.updated_utc""",
        (
            asset_id,
            run.namespace_id,
            run.account_id,
            run.root_id,
            path,
            metadata.get("path_display"),
            None,
            metadata.get("rev"),
            metadata.get("content_hash"),
            metadata.get("size"),
            metadata.get(".tag"),
            "present",
            scan_id,
            canonical(metadata),
            utc_now(),
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO inventory_entries VALUES (?,?,?)",
        (scan_id, asset_id, canonical(metadata)),
    )


def census(state, run, scope, *, resume=None, incremental=False, max_pages=None):
    conn = state.conn
    cursor = None
    if resume:
        row = conn.execute(
            "SELECT s.*,d.* FROM scans s JOIN scan_details d USING(scan_id) WHERE scan_id=?",
            (resume,),
        ).fetchone()
        if (
            not row
            or row["binding_sha256"] != scope.binding
            or row["state"] not in ("RUNNING", "FAILED_READ", "PARTIAL")
        ):
            raise Blocked("Scan is not resumable in the current confirmed scope")
        if (row["scan_kind"] == "changes") != incremental:
            raise Blocked("Resume command must match the original scan kind")
        scan_id, cursor = resume, row["current_cursor"]
    else:
        pending = conn.execute(
            """SELECT scan_id FROM scan_details WHERE binding_sha256=?
            AND state IN ('RUNNING','FAILED_READ','PARTIAL') LIMIT 1""",
            (scope.binding,),
        ).fetchone()
        if pending:
            raise Blocked(
                "Resume the existing incomplete scan before starting another",
                details={"scan_id": pending[0]},
            )
        if incremental:
            track = conn.execute(
                "SELECT * FROM cursor_tracks WHERE binding_sha256=?", (scope.binding,)
            ).fetchone()
            if not track:
                raise Blocked("A complete current census is required before change polling")
            cursor = track["cursor"]
        scan_id = new_id("scan")
        with conn:
            conn.execute(
                "INSERT INTO scans(scan_id,run_id,root_folder_id,namespace_id,started_utc,current_cursor) VALUES (?,?,?,?,?,?)",
                (scan_id, run.id, run.root_id, run.namespace_id, utc_now(), cursor),
            )
            conn.execute(
                "INSERT INTO scan_details(scan_id,scan_kind,state,binding_sha256) VALUES (?,?,?,?)",
                (scan_id, "changes" if incremental else "census", "RUNNING", scope.binding),
            )
            state.event("scan", scan_id, "inventory_started", {"incremental": incremental}, run.id)
    number = conn.execute(
        "SELECT COALESCE(MAX(page_number),0) FROM cursor_pages WHERE scan_id=?", (scan_id,)
    ).fetchone()[0]
    warnings = json.loads(
        conn.execute(
            "SELECT warnings_json FROM scan_details WHERE scan_id=?", (scan_id,)
        ).fetchone()[0]
    )
    this_call = 0
    seen_cursors = {
        row[0]
        for row in conn.execute(
            "SELECT returned_cursor FROM cursor_pages WHERE scan_id=?", (scan_id,)
        )
    }
    if cursor:
        seen_cursors.add(cursor)
    try:
        while True:
            page = scope.adapter.list_folder(run.root_id, recursive=True, cursor=cursor)
            if not isinstance(page.cursor, str) or not page.cursor:
                raise IntegrityError("API returned an empty inventory cursor")
            if page.has_more and page.cursor in seen_cursors:
                raise IntegrityError("Inventory pagination made no progress")
            for entry in page.entries:
                if not within_path(entry.get("path_lower"), scope.path):
                    raise IntegrityError("Inventory page contains an out-of-root path")
                if entry.get("sharing_info", {}).get("traverse_only"):
                    warnings.append(
                        {"kind": "access_limited_subtree", "path": entry.get("path_lower")}
                    )
            evidence = state.evidence(page.raw, "inventory-page")
            with conn:
                for entry in page.entries:
                    state.observe(
                        run,
                        entry,
                        "files/list_folder/continue" if cursor else "files/list_folder",
                        outcome="path_tombstone" if entry.get(".tag") == "deleted" else "listed",
                        evidence=evidence,
                    )
                    _ingest(state, run, scan_id, entry, incremental=incremental)
                number += 1
                conn.execute(
                    "INSERT INTO cursor_pages VALUES (?,?,?,?,?,?,?,?)",
                    (
                        scan_id,
                        number,
                        digest(cursor) if cursor else None,
                        page.cursor,
                        evidence[1],
                        evidence[0],
                        int(page.has_more),
                        utc_now(),
                    ),
                )
                conn.execute(
                    "UPDATE scans SET current_cursor=? WHERE scan_id=?", (page.cursor, scan_id)
                )
                conn.execute(
                    "UPDATE scan_details SET state='RUNNING',warnings_json=? WHERE scan_id=?",
                    (canonical(warnings), scan_id),
                )
                run.heartbeat()
                state.event(
                    "scan",
                    scan_id,
                    "inventory_page_committed",
                    {
                        "page": number,
                        "entries": len(page.entries),
                        "has_more": page.has_more,
                        "response_sha256": evidence[1],
                    },
                    run.id,
                )
            seen_cursors.add(page.cursor)
            cursor, this_call = page.cursor, this_call + 1
            if not page.has_more:
                break
            if max_pages and this_call >= max_pages:
                with conn:
                    conn.execute(
                        "UPDATE scan_details SET state='PARTIAL' WHERE scan_id=?", (scan_id,)
                    )
                return {
                    "objective_outcome": "PARTIAL_ENUMERATION",
                    "scan_id": scan_id,
                    "pages": number,
                    "resume_required": True,
                }
    except (RemoteError, IntegrityError) as exc:
        with conn:
            conn.execute(
                "UPDATE scan_details SET state=? WHERE scan_id=?",
                (
                    "CURSOR_RESET"
                    if isinstance(exc, RemoteError) and exc.kind == "cursor_reset"
                    else "FAILED_READ",
                    scan_id,
                ),
            )
            state.event(
                "scan",
                scan_id,
                "inventory_read_failed",
                {"error_type": type(exc).__name__, "kind": getattr(exc, "kind", "integrity")},
                run.id,
            )
        raise
    observed = {
        r[0]
        for r in conn.execute("SELECT asset_id FROM inventory_entries WHERE scan_id=?", (scan_id,))
    }
    baseline = {
        r[0]
        for r in conn.execute(
            "SELECT asset_id FROM assets WHERE source_path='plan/source_registers/Boldstone_Original_8431_ID_Census_2026-10-14.csv'"
        )
    }
    imported = {r[0] for r in conn.execute("SELECT asset_id FROM assets")}
    reconciliation = (
        {
            "observed_ids": len(observed),
            "baseline_ids_not_observed": sorted(baseline - observed),
            "new_ids_outside_imported_assets": sorted(observed - imported),
            "absence_meaning": "not_observed_in_authorized_API_visible_scope",
        }
        if not incremental
        else {"changed_ids": len(observed)}
    )
    with conn:
        current = conn.execute(
            "SELECT asset_id,path_lower,kind FROM current_assets WHERE account_id=? AND namespace_id=? AND root_folder_id=? AND status IN ('present','derived_path_needs_refresh')",
            (run.account_id, run.namespace_id, run.root_id),
        ).fetchall()
        folder_paths = {
            row["path_lower"]: row["asset_id"] for row in current if row["kind"] == "folder"
        }
        folder_paths[scope.path] = run.root_id
        for row in current:
            if not incremental and row["asset_id"] not in observed:
                conn.execute(
                    "UPDATE current_assets SET status='not_observed_in_latest_census',updated_utc=? WHERE asset_id=?",
                    (utc_now(), row["asset_id"]),
                )
            else:
                parent_id = folder_paths.get(parent_path(row["path_lower"]))
                conn.execute(
                    "UPDATE current_assets SET parent_folder_id=? WHERE asset_id=?",
                    (parent_id, row["asset_id"]),
                )
                if parent_id is None:
                    warnings.append({"kind": "unresolved_parent_link", "asset_id": row["asset_id"]})
        conn.execute(
            "UPDATE scans SET ended_utc=?,enumeration_exhausted=1,scope_complete=?,concurrent_changes_observed=? WHERE scan_id=?",
            (utc_now(), int(not warnings), int(incremental and bool(observed)), scan_id),
        )
        conn.execute(
            "UPDATE scan_details SET state=?,reconciliation_json=?,warnings_json=? WHERE scan_id=?",
            (
                "COMPLETE_VISIBLE_SCOPE" if not warnings else "ACCESS_LIMITED",
                canonical(reconciliation),
                canonical(warnings),
                scan_id,
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO cursor_tracks VALUES (?,?,?,?)",
            (scope.binding, cursor, scan_id, utc_now()),
        )
        state.event(
            "scan", scan_id, "inventory_finished", {"pages": number, "warnings": warnings}, run.id
        )
    return {
        "objective_outcome": "ENUMERATION_COMPLETE_VISIBLE_SCOPE"
        if not warnings
        else "ACCESS_LIMITED",
        "scan_id": scan_id,
        "pages": number,
        "coverage": "authorized_API_visible_scope",
        "warnings": warnings,
        "reconciliation": reconciliation,
        "sharing_changes_covered_by_cursor": False,
        "permanent_final_state_claim": False,
    }
