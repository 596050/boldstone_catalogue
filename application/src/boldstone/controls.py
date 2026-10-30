from __future__ import annotations

from collections import defaultdict

from .errors import IntegrityError
from .importers import validate_import, verify_pack


def validate_controls(state, *, full=True):
    conn = state.conn
    if full:
        verify_pack(state.config.pack)
        imported = validate_import(state, state.config.pack)
    else:
        imported = None
    checks = {
        "fixed_batches": conn.execute(
            "SELECT count(*) FROM batches WHERE original_order IS NOT NULL"
        ).fetchone()[0],
        "protected_distinct_ids": conn.execute(
            "SELECT count(DISTINCT asset_id) FROM protections"
        ).fetchone()[0],
        "active_H01_holds": conn.execute(
            "SELECT count(*) FROM holds WHERE active=1 AND hold_id LIKE 'H01-%'"
        ).fetchone()[0],
        "exclusions": dict(
            conn.execute("SELECT exclusion_kind,count(*) FROM exclusions GROUP BY exclusion_kind")
        ),
        "historical_absence_rows": conn.execute(
            "SELECT count(*) FROM source_rows WHERE source_path='plan/source_registers/Boldstone_67_Absence_Exceptions_2026-10-14.csv'"
        ).fetchone()[0],
    }
    if full and (
        checks["fixed_batches"] != 350
        or checks["protected_distinct_ids"] != 1813
        or checks["active_H01_holds"] != 7
        or checks["historical_absence_rows"] != 67
        or checks["exclusions"]
        != {"do_not_replay_recorded_rename": 203, "do_not_replay_historical_delete": 54}
    ):
        raise IntegrityError("Historical control set changed")
    graph = defaultdict(list)
    for edge in conn.execute("SELECT from_asset_id,to_asset_id FROM lineage"):
        graph[edge[0]].append(edge[1])
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise IntegrityError("Lineage graph contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for successor in graph[node]:
            visit(successor)
        visiting.remove(node)
        visited.add(node)

    for node in list(graph):
        visit(node)
    pending = [
        dict(r)
        for r in conn.execute(
            "SELECT operation_id,state FROM operations WHERE state NOT IN ('VERIFIED','FAILED_DEFINITE')"
        )
    ]
    interrupted = [
        dict(r)
        for r in conn.execute(
            "SELECT attempt_id,batch_id,started_utc FROM attempts WHERE ended_utc IS NULL"
        )
    ]
    events = state.validate_events()
    return {
        "objective_outcome": "CONTROLS_VALIDATED" if not pending else "UNFINISHED_OPERATIONS_HELD",
        "counts": checks,
        "import": imported,
        "event_chain": events,
        "unfinished_operations": pending,
        "interrupted_review_attempts": interrupted,
        "current_binary_or_permission_checks_implied": False,
    }
