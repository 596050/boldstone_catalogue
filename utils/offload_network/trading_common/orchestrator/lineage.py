"""Lineage queries: which work produced this data; which data did this work consume."""
from __future__ import annotations

from .store import get_store
from .schema import WorkItem, Artifact


def artifacts_for_workitem(workitem_id: str) -> list[Artifact]:
    _, artifacts = get_store().materialise()
    return [a for a in artifacts.values() if a.produced_by == workitem_id]


def workitems_producing_artifact(artifact_id: str) -> list[WorkItem]:
    workitems, artifacts = get_store().materialise()
    a = artifacts.get(artifact_id)
    if not a or not a.produced_by:
        return []
    wi = workitems.get(a.produced_by)
    return [wi] if wi else []


def trace_lineage(artifact_id: str, max_depth: int = 5) -> dict:
    """Walk backward: artifact ← produced_by workitem ← consumed inputs ← producing workitems …
    Returns a flat dict {depth: [item]} for display."""
    workitems, artifacts = get_store().materialise()
    out: dict[int, list] = {0: []}
    a = artifacts.get(artifact_id)
    if a is None:
        return {"error": f"no artifact {artifact_id}"}
    out[0].append({"kind": "artifact", "id": a.id, "path": a.path,
                   "size_bytes": a.size_bytes})

    depth = 0
    frontier: list[Artifact] = [a]
    while depth < max_depth and frontier:
        depth += 1
        out.setdefault(depth, [])
        new_frontier: list[Artifact] = []
        for art in frontier:
            if not art.produced_by:
                continue
            wi = workitems.get(art.produced_by)
            if not wi:
                continue
            out[depth].append({"kind": "workitem", "id": wi.id,
                               "work_type": wi.work_type.value,
                               "host": wi.host, "status": wi.status.value})
            for inp_id in wi.inputs:
                inp = artifacts.get(inp_id)
                if inp:
                    out[depth].append({"kind": "artifact", "id": inp.id,
                                       "path": inp.path})
                    new_frontier.append(inp)
        frontier = new_frontier
    return out
