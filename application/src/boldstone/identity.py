from __future__ import annotations

import json
from collections import defaultdict

from .util import canonical, digest

SUPPLEMENTAL = (
    "supplemental_identity/Historical_29_Inventory_Review_Rows.csv",
    "supplemental_identity/Historical_18_Identity_Review_Rows.csv",
    "supplemental_identity/Historical_14_Held_Folder_Rows.csv",
)
CONTEXT = (
    "checkpoint/I00_Consolidated_Known_Identity_Queue.csv",
    "checkpoint/I00_Historical_Folder_Risk_Context.csv",
    "checkpoint/I00_Historical_Resolved_Composition.csv",
    "checkpoint/I00_Source_Completeness_Gaps.csv",
)


def consolidate_identity(state, run):
    conn = state.conn
    paths = defaultdict(set)
    for folder in conn.execute(
        "SELECT asset_id,baseline_relative_path FROM assets WHERE kind='folder'"
    ):
        if folder["baseline_relative_path"]:
            paths[folder["baseline_relative_path"]].add(folder["asset_id"])
    matrix, scope_groups = [], defaultdict(list)
    assertions = 0
    with conn:
        for source in (*SUPPLEMENTAL, *CONTEXT):
            source_record = conn.execute(
                "SELECT * FROM sources WHERE source_path=?", (source,)
            ).fetchone()
            rows = list(
                conn.execute(
                    "SELECT row_number,row_json FROM source_rows WHERE source_path=? ORDER BY row_number",
                    (source,),
                )
            )
            matrix.append(
                {
                    "source_path": source,
                    "recovered": bool(source_record),
                    "rows": len(rows),
                    "representation": "normalized_historical_transcription"
                    if source in SUPPLEMENTAL
                    else "preserved_checkpoint_csv",
                    "native_original_workbook_bytes_verified": False,
                    "new_visual_review": False,
                }
            )
            if source not in SUPPLEMENTAL and source != CONTEXT[0]:
                continue  # Keep context and scoped resolutions; do not manufacture new issues from them.
            for original in rows:
                row = json.loads(original["row_json"])
                folder = row.get("Dropbox folder ID") or row.get("Stable folder ID")
                path = row.get("Historical relative folder path") or row.get("Recorded folder path")
                match_basis = "explicit_historical_folder_ID" if folder else "no_stable_ID_link"
                if not folder and path and len(paths[path]) == 1:
                    folder = next(iter(paths[path]))
                    match_basis = "unique_exact_dated_folder_path_match_not_live_validation"
                question = (
                    row.get("Normalized source finding and constraint")
                    or row.get("Source identity constraint")
                    or row.get("Normalized reason held")
                    or row.get("Evidence needed")
                    or row.get("Subject")
                    or "Historical question requires reconciliation"
                )
                # Object overlap is a relation, not evidence that the questions are identical.
                issue_id = (
                    "I-SOURCE-" + digest({"source": source, "row": original["row_number"]})[:24]
                )
                scope = {
                    "historical_folder_id": folder,
                    "historical_path": path,
                    "stable_ID_link_basis": match_basis,
                    "fixed_visual_batch": row.get("Related allocated batch"),
                    "source_assertion_not_distinct_unresolved_identity": True,
                    "later_scoped_evidence_sources": list(CONTEXT[1:]),
                }
                conn.execute(
                    "INSERT OR IGNORE INTO identity_cases(issue_id,question,folder_id,issue_scope_json,state) VALUES (?,?,?,?,?)",
                    (issue_id, question, folder, canonical(scope), "HISTORICAL_UNRECONCILED"),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO identity_source_links VALUES (?,?,?,?)",
                    (
                        issue_id,
                        source,
                        original["row_number"],
                        "source_question_preserved_without_semantic_merge",
                    ),
                )
                if folder:
                    scope_groups[folder].append(issue_id)
                assertions += 1
        relations = 0
        for folder, issues in scope_groups.items():
            for n, first in enumerate(issues):
                for second in issues[n + 1 :]:
                    conn.execute(
                        "INSERT OR IGNORE INTO issue_relations VALUES (?,?,?,?)",
                        (
                            first,
                            second,
                            "same_dated_folder_scope_questions_not_merged",
                            canonical({"folder_id": folder, "semantic_identity_accepted": False}),
                        ),
                    )
                    relations += 1
        details = {
            "source_completeness": matrix,
            "preserved_source_assertions": assertions,
            "supplemental_source_rows": sum(
                m["rows"] for m in matrix if m["source_path"] in SUPPLEMENTAL
            ),
            "same_scope_relations": relations,
            "distinct_unresolved_identity_count": None,
            "semantic_consolidation": "pending_review_of_related_questions_and_later_scoped_resolutions",
            "native_source_completeness": "not_verified_transcriptions_only",
            "new_visual_decisions": 0,
            "fixed_batches_rewritten": 0,
            "remaining_work": "Review related questions and later scoped evidence; recover/verify native sources where required",
        }
        state.event("batch", "I00", "historical_identity_sources_linked", details, run.id)
    return details
