"""Read-only shared-record inventory, with isolated snapshots and no acceptances."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import datetime
import hashlib
import json

B = Path(__file__).resolve().parent
C = B.parents[2]
R = C / "components/reviews"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
LANE = "01a13fe6-495b-7253-b923-31823b4cbca8"
ROOT = "01a144ab-1a7c-7223-a403-73a4d53d70ff"


def read(p):
    return json.loads(p.read_text())


def digest(b):
    return hashlib.sha256(b).hexdigest()


def save(name, x):
    p = B / name
    assert not p.exists(), p
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(p), "sha256": digest(p.read_bytes())}


inputs = {}
for key, path in [("reviews", R / "specification_review_progress.json"), ("ledger", R / "user_classifications.json"),
                  ("model", C / "components/evidence/component_register.json")]:
    raw = path.read_bytes()
    p = B / ("snapshot-" + key + ".json")
    assert not p.exists()
    p.write_bytes(raw)
    inputs[key] = {"source": str(path), "snapshot": str(p), "sha256": digest(raw)}
p, u, model = [read(Path(inputs[x]["snapshot"])) for x in ["reviews", "ledger", "model"]]
transcript = Path("/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-" + LANE + ".jsonl")
owner = []
for n, raw in enumerate(transcript.read_bytes().splitlines(keepends=True), 1):
    e = json.loads(raw)
    payload = e.get("payload", {})
    if payload.get("role") == "user":
        text = "\n".join(x.get("text", "") for x in payload.get("content", []))
        if text == "Okay, go through all the rest of the batches":
            owner.append({"transcript": str(transcript), "line": n, "timestamp": e["timestamp"], "role": "user",
                          "text": text, "raw_line_sha256": digest(raw),
                          "source_raw_line_digest_includes_line_ending": True})
assert owner
owner_ref = save("OWNER_CONTINUE_ALL_EVIDENCE.json", owner[-1])
accepted_ids = {pid for ledger in ["specification_decisions", "size_finish_variant_specification_decisions", "build_variant_decisions"]
                for d in u.get(ledger, []) for pid in d.get("approved_proposal_ids", [])}
sealed = {}
for path in (C / "components/parallel-reviews").glob("*/IMPORT_PACKAGE.json"):
    package = read(path)
    batch = package.get("reserved_batch", package.get("reserved_import_batch"))
    if batch not in [92, 93, 94]:
        continue
    decisions = list(package.get("decisions", []))
    for item in package.get("existing_variants", []):
        sub = read(Path(item["package"]["path"]))
        decisions.append(sub["decision"])
    for reference in decisions:
        d = read(Path(reference["path"]))
        cid = d.get("component_id")
        scope = d.get("size_finish_variant_id") or d.get("build_variant_id") or d.get("component_layout_id") or d.get("review_scope") or "BASE"
        sealed[cid + "|" + scope] = {"batch": batch, "package_path": str(path), "package_sha256": digest(path.read_bytes()),
                                     "decision": reference}


def group(s):
    s = str(s).lower()
    for k, terms in [("dimensions", ["dimension", "depth", "size"]), ("weight", ["weight", "mass"]),
                     ("material", ["material", "finish"]), ("fixing", ["fixing", "mounting", "support"]),
                     ("price", ["price", "selling"]), ("availability", ["availability", "lead time", "stock"])]:
        if any(t in s for t in terms):
            return k
    return ""


scopes, nodes = {}, {}
components = {x["component_id"]: x for x in model["components"]}


def add(cid, scope, node, kind, identity=None, source=None):
    key = cid + "|" + scope
    if key in scopes:
        return
    nodes[key] = node
    props = node.get("specification_proposals", node.get("specifications", []))
    if isinstance(props, dict):
        props = [dict(x, field=k) if isinstance(x, dict) else {"field": k, "display": str(x)} for k, x in props.items()]
    groups, accepted_groups = set(), set()
    for x in props:
        g = group(x.get("field", x.get("group")))
        if g:
            groups.add(g)
            if x.get("owner_approved") or x.get("owner_accepted") or x.get("proposal_id") in accepted_ids | set(node.get("approved_proposal_ids", [])):
                accepted_groups.add(g)
    if node.get("proposals_approved") and node.get("specification_approval") and (
        scope == "BASE" or node.get("working_specifications_approval_scope") == "EXACT_FINISH_ALL_SIX_WORKING_VALUES"
    ):
        accepted_groups |= groups
    kept = identity if identity is not None else node.get("identity_confirmed", False)
    ref = node.get("current_dropbox_reference", {})
    name = node.get("canonical_name") or node.get("proposed_name") or node.get("canonical_source_name") or (source or {}).get("name") or cid
    if key in sealed:
        state = "SEALED_PENDING_IMPORT_EXCLUDED"
    elif len(accepted_groups) == 6 or node.get("all_six_owner_specification_fields_accepted"):
        state = "SIX_WORKING_FIELDS_ALREADY_ACCEPTED"
    elif kind == "Source alias review":
        state = "SOURCE_ALIAS_REFERENCE_NO_ADDITIONAL_PRODUCT"
    elif cid == "BC-MIX-SPIRALS" or "DEFERRED" in str(node.get("status", "")):
        state = "OWNER_DEFERRED"
    elif "RESOLVED" in str(node.get("status", "")) and "NO_ADDITIONAL_PRODUCT" in str(node.get("status", "")):
        state = "RESOLVED_REFERENCE_NO_ADDITIONAL_PRODUCT"
    elif kept and len(groups) == 6:
        state = "KEPT_SCOPE_WORKING_REVIEW_REMAINS"
    elif kept and scope == "BASE" and not any(node.get(k) for k in ["size_finish_variants", "build_variants"]):
        state = "KEPT_SOURCE_FIELDS_REQUIRE_NORMALIZED_REVIEW"
    elif kept:
        state = "KEPT_PARENT_OR_PARTIAL_SCOPE_REQUIRES_BOUNDARY_CHECK"
    else:
        state = "SOURCE_HEADER_OR_UNCONFIRMED_IDENTITY"
    scopes[key] = {
        "key": key, "component_id": cid, "scope": scope, "kind": kind, "canonical_name": name,
        "identity_kept": bool(kept), "disposition": state, "field_groups_present": sorted(groups),
        "accepted_field_groups": sorted(accepted_groups), "remaining_field_groups": sorted(set(["dimensions", "weight", "material", "fixing", "price", "availability"]) - accepted_groups),
        "primary_file_id": ref.get("file_id") or node.get("current_primary_image_id") or node.get("primary_image_id") or node.get("source_asset_id"),
        "folder_id": ref.get("folder_id") or node.get("current_primary_folder_id") or node.get("primary_folder_id") or node.get("source_folder_id"),
        "source_review": node.get("review_record") or node.get("source_review_snapshot") or node.get("specification_approval"),
        "identity_approval": node.get("identity_approval") or node.get("owner_name_approval"),
        "source_status": node.get("status"), "sealed": sealed.get(key),
    }


for cid, source in components.items():
    if cid in p.get("canonical_component_consolidations", {}):
        continue
    node = p["reviews"].get(cid, {})
    own = node.get("size_finish_variant_id") or node.get("build_variant_id")
    add(cid, "BASE", node.get("canonical_design_record") or ({} if own else node), "Source component record", source=source)
for cid, node in p["reviews"].items():
    if cid in p.get("canonical_component_consolidations", {}):
        continue
    own = node.get("size_finish_variant_id") or node.get("build_variant_id")
    if cid not in components and not own:
        add(cid, "BASE", node, "Individual review")
    if own:
        add(cid, own, node, "Depicted finish / build review")
    for k, kind in [("size_finish_variants", "Finish / size review"), ("build_variants", "Construction review"),
                    ("component_layouts", "Layout review"), ("source_reference_reviews", "Source alias review")]:
        for scope, child in node.get(k, {}).items():
            add(cid, scope, child, kind)
for key, alias in p.get("catalogue_alias_reviews", {}).items():
    adapted = deepcopy(alias)
    bindings = alias.get("historical_name_keep_bindings", [])
    if bindings:
        source = read(C / bindings[0]["source_review_snapshot"])
        adapted["specification_proposals"] = source.get("specifications", {})
    add(alias.get("catalogue_design_key", key), key, adapted, "Catalogue alias", identity=bool(bindings) or alias.get("identity_confirmed"))
for key, node in p.get("source_design_reviews", {}).items():
    if node.get("record_kind", "").startswith("INDIVIDUAL_WHOLE_SOURCE"):
        add("UGR-G310", key, node, "Owner-named whole source; no BC ID")

remaining = [x for x in scopes.values() if x["disposition"].startswith("KEPT_")]
assign = {}
for x in remaining:
    cid, name = x["component_id"], x["canonical_name"]
    if cid.startswith("MOONPHASE") or cid.startswith(("BC-DDR", "BC-DECO", "BC-DP", "BC-FDW", "BC-ECHO", "BC-EG", "BC-FOLD", "BC-FP", "BC-FFS", "BC-GLEN", "BC-LAVA-")) or cid == "BC-KNIGHT":
        lane = "A"
    elif cid in ["BC-MCP-4", "BC-ICARUS", "AM-S1", "AM-S2", "AM-L1", "AM-L2", "BC-PORTMAN-1", "BC-BARBADOS", "BC-CHELSEA"]:
        lane = "ROOT"
    else:
        lane = "B"
    assign[x["key"]] = lane
inventory = {
    "schema": "boldstone.remaining-working-review-inventory.v1", "checked_utc": NOW,
    "shared_last_import": p.get("latest_parallel_import", {}).get("batch"), "frozen_inputs": inputs,
    "owner_instruction": owner_ref, "scope_count": len(scopes), "scope_count_is_not_unique_sculpture_count": True,
    "disposition_counts": dict(Counter(x["disposition"] for x in scopes.values())),
    "remaining_kept_scope_count": len(remaining), "sealed_pending_scopes": sealed,
    "all_scopes": list(scopes.values()), "remaining": remaining,
    "canonical_consolidations_excluded": p.get("canonical_component_consolidations", {}),
    "other_group_source_records_excluded": [{"key": k, "name": v.get("canonical_name") or v.get("canonical_source_name"),
                                            "record_kind": v.get("record_kind"),
                                            "reason": "Owner group-photo policy retains whole collection/context; no new individual decomposition"}
                                           for k, v in p.get("source_design_reviews", {}).items()
                                           if not v.get("record_kind", "").startswith("INDIVIDUAL_WHOLE_SOURCE")],
    "proposed_ownership_map_not_a_lease": assign, "proposed_ownership_counts": dict(Counter(assign.values())),
    "requires_root_lease_before_new_acceptances": True, "shared_writes": False, "new_acceptances": 0,
}
report_ref = save("REMAINING_INVENTORY.json", inventory)
save("SCOPE_NODE_SNAPSHOTS.json", nodes)
print(json.dumps({"inventory": report_ref, "owner": owner[-1], "counts": inventory["disposition_counts"],
                  "ownership": inventory["proposed_ownership_counts"]}, ensure_ascii=False))
for x in remaining:
    print(assign[x["key"]], x["key"], x["canonical_name"], x["disposition"])
