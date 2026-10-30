"""Inventory the final state of every allocated scope. Read-only shared access."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json

B = Path(__file__).resolve().parent
C = B.parents[2]
R = C / "components/reviews"


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def group(s):
    for key, terms in [
        ("dimensions", ["dimension", "depth", "size"]),
        ("weight", ["weight", "mass"]), ("material", ["material", "finish"]),
        ("fixing", ["fixing", "mounting", "support"]),
        ("price", ["price", "selling"]), ("availability", ["availability", "stock", "lead time"]),
    ]:
        if any(t in str(s).lower() for t in terms):
            return key
    return None


lease = read(R / "parallel-allocation-2026-10-20-all-remaining.json")
addendum = read(R / "parallel-allocation-2026-10-20-all-remaining-addendum.json")
shared_path = R / "specification_review_progress.json"
raw = shared_path.read_bytes()
shared = json.loads(raw)
ledger_path = R / "user_classifications.json"
ledger_bytes = ledger_path.read_bytes()
ledger = json.loads(ledger_bytes)
accepted_ids = {pid for array in ledger.values() if isinstance(array, list) for d in array if isinstance(d, dict) for pid in d.get("approved_proposal_ids", [])}
decisions = [d for array in ledger.values() if isinstance(array, list) for d in array if isinstance(d, dict)]
rows = {}
for batch, pack in lease["batches"].items():
    for r in pack["scopes"]:
        actual_batch = "97" if r["key"] == addendum["B96_excluded_key"] else batch
        assert r["key"] not in rows
        rows[r["key"]] = {**r, "allocated_batch": int(actual_batch)}
assert len(rows) == 111
records = []
for key, r in rows.items():
    cid, scope = r["component_id"], r["scope"]
    if cid == "UGR-G310":
        node = shared.get("source_design_reviews", {}).get(scope, {})
    elif cid.startswith("MOONPHASE-CURRENT-"):
        node = shared.get("catalogue_alias_reviews", {}).get(scope, {})
    else:
        parent = shared["reviews"].get(cid, {})
        if scope == "BASE":
            node = parent.get("canonical_design_record") or parent
        elif scope in [parent.get("size_finish_variant_id"), parent.get("build_variant_id"), parent.get("component_layout_id")]:
            node = parent
        else:
            node = next((parent[k][scope] for k in ["size_finish_variants", "build_variants", "component_layouts"] if scope in parent.get(k, {})), {})
    props = node.get("accepted_working_specifications", node.get("specification_proposals", node.get("specifications", node.get("specification_review_items", []))))
    if isinstance(props, dict):
        props = [dict(v, field=k) if isinstance(v, dict) else {"field": k, "display": v} for k, v in props.items()]
    groups = set()
    for p in props:
        g = group(p.get("group", p.get("field")))
        if g and (p.get("owner_approved") or p.get("owner_accepted") or p.get("proposal_id") in accepted_ids | set(node.get("approved_proposal_ids", []))):
            groups.add(g)
    full = len(groups) == 6 or node.get("all_six_owner_specification_fields_accepted", False) or node.get("all_six_working_specification_fields_accepted", False)
    if node.get("specifications_approved") or node.get("specification_fields_fully_approved"):
        full = full or {group(p.get("group", p.get("field"))) for p in props} >= {"dimensions","weight","material","fixing","price","availability"}
    disposition = {
        k: v for k, v in node.items() if any(x in k for x in
            ["disposition", "boundary", "record_kind", "reference_only", "header", "review_state", "source_role", "all_remaining"])
    }
    canonical_disposition = shared.get("working_review_reference_dispositions", {}).get(key)
    dups = [d.get("decision_id") for d in decisions if d.get("decision_id") in
            [key + ":WORKING-SPECS:POLICY80"]]
    records.append({
        "scope_key": key, "allocated_batch": r["allocated_batch"], "canonical_name": node.get("canonical_name", r["canonical_name"]),
        "all_six_working_fields_accepted": bool(full), "accepted_groups_visible": sorted(groups),
        "node_status": node.get("status"), "specification_approval": node.get("specification_approval"),
        "terminal_reference_disposition_fields": disposition,
        "canonical_reference_disposition": canonical_disposition,
        "working_review_closed": bool(full) or bool(canonical_disposition),
        "matching_B96_ledger_decisions": len(dups) if r["allocated_batch"] == 96 else None,
        "physical_specs_verified": node.get("physical_specs_verified", False),
    })
result = {
    "schema": "boldstone.all-remaining-allocation-final-inventory.v1",
    "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source_last_import": shared.get("latest_parallel_import"),
    "source_progress_sha256": hashlib.sha256(raw).hexdigest(), "source_ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
    "allocated_scopes": len(records), "allocation_by_batch": dict(Counter(x["allocated_batch"] for x in records)),
    "six_working_fields_accepted": sum(x["all_six_working_fields_accepted"] for x in records),
    "reference_dispositions": sum(bool(x["canonical_reference_disposition"]) for x in records),
    "remaining_open_allocated_working_reviews": [x["scope_key"] for x in records if not x["working_review_closed"]],
    "status": "PASS" if all(x["working_review_closed"] for x in records) else "INCOMPLETE",
    "not_six_field_acceptances": [x for x in records if not x["all_six_working_fields_accepted"]],
    "records": records,
    "counts_are_review_scopes_not_unique_sculptures_or_physical_stock": True,
    "shared_master_writes_by_lane": 0, "remote_mutations": 0,
}
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out = B / ("ALL_REMAINING_SCOPE_AUDIT_" + stamp + ".json")
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"path": str(out), "sha256": sha(out), "allocated": len(records),
                  "accepted": result["six_working_fields_accepted"],
                  "status": result["status"], "reference_dispositions": result["reference_dispositions"],
                  "open_working_reviews": result["remaining_open_allocated_working_reviews"],
                  "not_six": [x["scope_key"] for x in result["not_six_field_acceptances"]],
                  "B96_duplicate_ledger_ids": [x["scope_key"] for x in records if x["matching_B96_ledger_decisions"] not in [None, 1]]}))
