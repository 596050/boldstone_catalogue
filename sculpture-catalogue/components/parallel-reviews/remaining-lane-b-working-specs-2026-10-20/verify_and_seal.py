"""Independent readback checks for B96, then seal its isolated import package."""
from pathlib import Path
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs, unquote
import datetime
import hashlib
import json

B = Path(__file__).resolve().parent
C = B.parents[2]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
FIELDS = ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"]
checks = []


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


def save(name, obj):
    p = B / name
    assert not p.exists(), p
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    return ref(p)


def check(name, condition, detail=None):
    checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})
    assert condition, (name, detail)


def hash_ref(r):
    return Path(r["path"]).is_file() and sha(r["path"]) == r["sha256"]


def dbhash(data):
    return hashlib.sha256(b"".join(hashlib.sha256(data[i:i+4194304]).digest()
                                  for i in range(0, len(data), 4194304))).hexdigest()


def user_evidence(e):
    path = e.get("transcript", e.get("transcript_path"))
    lines = Path(path).read_bytes().splitlines(keepends=True)
    raw = lines[e["line"] - 1]
    obj = json.loads(raw)
    payload = obj["payload"]
    text = "\n".join(x.get("text", "") for x in payload["content"])
    result = payload["role"] == "user" and text == e["text"]
    if e.get("raw_line_sha256"):
        if "source_raw_line_digest_includes_line_ending" in e:
            hashed = raw if e["source_raw_line_digest_includes_line_ending"] else raw.rstrip(b"\r\n")
            result = result and hashlib.sha256(hashed).hexdigest() == e["raw_line_sha256"]
        else:
            result = result and e["raw_line_sha256"] in [hashlib.sha256(raw).hexdigest(), hashlib.sha256(raw.rstrip(b"\r\n")).hexdigest()]
    return result


index = read(B / "PREPARED_PACKAGE_INDEX.json")
discovery = read(B / "DISCOVERED_EVIDENCE.json")
visual = read(B / "VISUAL_INDEX.json")
inspection = read(B / "VISUAL_INSPECTION_RECEIPT.json")
reference = read(B / "CURRENT_REFERENCE_BINDING.json")
heads = {r["request_id"]: r[r["metadata_type"]] for r in reference["metadata"]}
lease = read(B / "ALLOCATION.json")
addendum = read(B / "ALLOCATION_ADDENDUM.json")
expected = {r["key"] for r in lease["batches"]["96"]["scopes"]} - {addendum["B96_excluded_key"]}
check("Exact allocation and exclusion", expected == {r["scope_key"] for r in index["items"]} and len(expected) == 40)
check("Frozen input references", all(hash_ref(r) for r in [index["allocation"], index["allocation_addendum"], index["owner_continue_all_evidence"], *discovery["policies"].values()]))
check("Owner continuation evidence", user_evidence(read(B / "OWNER_CONTINUE_ALL_EVIDENCE.json")))
for policy_name, p in discovery["policies"].items():
    d = read(p["path"])
    check("Authoritative owner policy: " + policy_name, user_evidence(d.get("authoritative_user_evidence", d.get("owner_evidence"))))
check("All bounded metadata requests resolved", set(heads) == set(discovery["metadata_requests"]) and len(heads) == 125)
check("67 selected files and58 containing folders", sum("rev" in h for h in heads.values()) == 67 and sum("rev" not in h for h in heads.values()) == 58)
check("Raw throttle history retained and retry succeeded", reference["all_initial_throttles_resolved"] and reference["initial_throttled_requests"] == 25 and all(hash_ref(r) for r in reference["source_receipts"]))
media = {r["file_id"]: r for r in visual["media"]}
for r in media.values():
    blob = Path(r["path"]).read_bytes()
    h = heads[r["file_id"]]
    check("Cached image SHA and stable size: " + r["file_id"],
          hashlib.sha256(blob).hexdigest() == r["sha256"] and len(blob) == r["bytes"] and h["size"] == r["source_asset"]["bytes"])
    candidates = r.get("historical_metadata_candidates", [])
    if candidates:
        check("Historical revision match: " + r["file_id"], any(x["rev"] == h["rev"] and (x.get("size") is None or x["size"] == h["size"]) for x in candidates))
    if r["media_type"] == "CACHED_ORIGINAL":
        check("Original Dropbox block hash: " + r["file_id"], dbhash(blob) == r["dropbox_content_hash"] == r["source_asset"]["content_hash"] and len(blob) == h["size"])
    else:
        check("Preview-only boundary: " + r["file_id"], not r.get("current_remote_bytes_verified") and r["media_type"] == "CACHED_PREVIEW_ONLY_ORIGINAL_BYTES_UNVERIFIED")
check("61 cached originals and6 preview-only references", Counter(r["media_type"] for r in media.values()) == {
    "CACHED_ORIGINAL": 61, "CACHED_PREVIEW_ONLY_ORIGINAL_BYTES_UNVERIFIED": 6})
check("All67 selected images represented in12 rehashed sheets", len(visual["contact_sheets"]) == 12 and
      {x["file_id"] for s in visual["contact_sheets"] for x in s["cells"]} == set(media) and
      all(sha(s["path"]) == s["sha256"] for s in visual["contact_sheets"]))
check("Visual inspection explicitly bounded to derivatives", inspection["status"] == "COMPLETED" and inspection["distinct_images_viewed"] == 67 and
      not inspection["full_resolution_inspection_claimed"] and not inspection["complete_folder_census_claimed"])

shared_path = C / "components/reviews/specification_review_progress.json"
shared_bytes = shared_path.read_bytes()
shared = json.loads(shared_bytes)
source_map = {r["key"]: r for r in discovery["scopes"]}
allcards = read(B / "REVIEW_CARDS.json")["entries"]
check("Review card count and scope equality", len(allcards) == 40 and {x["scope_key"] for x in allcards} == expected)
decisions, individual_checks = [], []
for item in index["items"]:
    start = len(checks)
    key = item["scope_key"]
    source_item = source_map[key]
    check(key + ": decision, review and context hashes", all(hash_ref(item[k]) for k in ["decision", "prepared_review", "context"]) and all(hash_ref(r) for r in item["source_snapshots"].values()))
    decision = read(item["decision"]["path"])
    review = read(item["prepared_review"]["path"])
    node = read(item["source_snapshots"]["node"]["path"])
    source = read(item["source_snapshots"]["original_review"]["path"])
    original = source.get("specification_review_items", source.get("specifications"))
    current = node.get("specification_proposals", node.get("specifications", node.get("specification_review_items")))
    check(key + ": original/current complete dictionaries exact", decision["source_specification_proposals_retained"] == original and decision["source_current_specification_proposals_retained"] == current)
    specs = decision["specifications"]
    check(key + ": exactly six working approvals", set(specs) == set(FIELDS) and set(decision["approved_field_groups"]) == set(FIELDS) and
          len(decision["approved_proposal_ids"]) == 6 and all(x["owner_approved"] and x["owner_accepted"] and x["approval_basis"] == "STANDING_OWNER_POLICY" for x in specs.values()))
    check(key + ": no invented reply, identity, measurement or stock", not any(decision[k] for k in
          ["per_card_owner_reply_received", "synthetic_owner_reply_created", "new_identity_inferred", "physical_specs_verified", "actual_stock_verified"]) and
          all(not x["physical_value_verified"] and not x["independently_measured_or_certified"] for x in specs.values()) and
          decision["new_owner_approval_events"] == decision["new_owner_policy_events"] == decision["new_name_approvals"] == 0 and decision["new_BC_component_ids"] == [])
    check(key + ": canonical source fields preserved per group", all(
          specs[f]["source_original_field_retained"] == review["specifications"][f]["source_original_field_retained"] and
          specs[f]["source_current_field_retained"] == review["specifications"][f]["source_current_field_retained"] for f in FIELDS))
    check(key + ": offered choice without installed hardware claim", specs["fixing"]["value"]["offered_options"] == ["Keyhole fixing", "French cleat"] and
          specs["fixing"]["value"]["actual_fitted_count"] is None and not specs["fixing"]["value"]["offered_choice_is_installed_confirmation"])
    check(key + ": historical source/public price boundary", not specs["individual_price"]["current_public_selling_price_verified"] and
          decision["platform_mapping"] == node.get("platform_mapping", source.get("platform_mapping", {})))
    if item["component_id"] != "BC-AZURE":
        check(key + ": existing weight display exact", specs["weight"]["display"] == specs["weight"]["source_current_field_retained"]["display"] and
              specs["weight"]["existing_approximation_accepted_under_weight_policy"])
    p, f = heads[decision["primary_file_id"]], heads[decision["folder_id"]]
    image = urlparse(decision["image_link"])
    folder = urlparse(decision["folder_link"])
    check(key + ": current native image/folder links", image.netloc == folder.netloc == "www.dropbox.com" and
          unquote(image.path.removeprefix("/home")) == p["path_display"].rsplit("/", 1)[0] == f["path_display"] and
          unquote(folder.path.removeprefix("/home")) == f["path_display"] and parse_qs(image.query)["preview"] == [p["name"]])
    ctx = read(item["context"]["path"])
    check(key + ": context and image evidence scope", ctx["context_images"] == decision["context_images"] and
          not ctx["context_images"]["complete_folder_census_performed"] and ctx["context_images"]["new_group_scene_components_identified"] == 0 and
          not ctx["context_images"]["exact_cast_linked_rear_hardware_established_this_pass"])
    if item["variant_kind"] == "whole_source_review":
        actual = shared["source_design_reviews"][item["variant"]]
    elif item["variant_kind"] == "source_component_record":
        parent = shared["reviews"][item["component_id"]]
        actual = parent.get("canonical_design_record") or parent
    else:
        parent = shared["reviews"][item["component_id"]]
        actual = parent if parent.get(item["id_key"]) == item["variant"] else parent[item["variant_kind"]][item["variant"]]
    check(key + ": no duplicate shared six-field approval at preflight", not actual.get("all_six_owner_specification_fields_accepted") and
          not actual.get("specifications_approved") and not actual.get("specification_fields_fully_approved"))
    check(key + ": reader document content matches decision", next(x for x in allcards if x["scope_key"] == key) == decision)
    individual_checks.append({"scope_key": key, "checks_passed": len(checks)-start, "status": "PASS"})
    decisions.append(item["decision"])

bykey = {d["scope_key"]: d for d in allcards}
azure = read(B / "AZURE_CONDITIONAL_NET_WEIGHT_ESTIMATE.json")
check("Azure net and shipping records distinct", azure["estimated_kg"] == 7 and azure["estimated_range_kg"] == [4, 10] and
      azure["shipping_record"]["approximately_kg"] == 15 and not azure["shipping_weight_used_as_net_weight"] and
      not azure["assumed_face_is_measured_or_owner_confirmed"] and not azure["superseded_2_to_4_kg_light_board_guess_reactivated"])
check("Azure conditional scaling arithmetic", azure["unrounded_scaled_range_kg"] == [8*16/22, 10*16/22] and abs(azure["shipping_record"]["converted_kg"] - 15.0002996759) < 1e-9 and hash_ref(azure["comparison"]["source"]))
check("Bone owner working face retained", "80 cm wide × 60 cm high — owner-accepted working version" in bykey["BC-BONE-WATER|BASE"]["specifications"]["dimensions"]["display"] and
      hash_ref(bykey["BC-BONE-WATER|BASE"]["owner_face_correction"]))
check("Coral55face andSoundwave80x60owner records retained", read(bykey["BC-CORAL|CORAL-WHITE"]["owner_face_correction"]["path"])["approved_face_dimensions_cm"] == {"height":55,"width":55} and
      read(bykey["UGR-G310|SOUNDWAVE-WHITE-G310003"]["owner_face_correction"]["path"])["face_dimensions_cm"] == [80,60])
check("Spiralmoon conflicting weights not averaged", "10–12" in bykey["BC-SM-SPIRAL|SM1-WHITE"]["specifications"]["weight"]["display"] and
      "15" in bykey["BC-SM-SPIRAL|SM1-WHITE"]["specifications"]["weight"]["display"])
check("Rust unit interpretation remains conditional", not bykey["BC-RUST-PANEL|BASE"]["specifications"]["weight"]["source_current_field_retained"]["native_unit_confirmed"])
check("Whole-source Soundwave stays source-scoped", bykey["UGR-G310|SOUNDWAVE-WHITE-G310003"]["source_design_key"] == "SOUNDWAVE-WHITE-G310003" and
      bykey["UGR-G310|SOUNDWAVE-WHITE-G310003"]["new_BC_component_ids"] == [])
check("Bone cropped andBlackWhite room-only gaps explicit", bykey["BC-BONE-WATER|BASE"]["context_images"]["primary_is_cropped_detail"] and
      bykey["BC-MSW-MOON|MSW-HALF-MOON-BLACK-WHITE"]["context_images"]["isolated_front_not_established"])
check("Water adaptation boundaries retained", all(
      "dry" in bykey[key]["specifications"]["weight"]["display"].lower() or
      "excludes basin, pump and water" in bykey[key]["specifications"]["weight"]["display"].lower()
      for key in expected if bykey[key]["variant_kind"] == "build_variants" and
      ("WATER-WHITE" in key or "WATER-FEATURE" in key)),
      "Dry-panel wording or explicit exclusion of basin, pump and water; do not infer filled-system weight.")
check("No shared file write during QA", shared_path.read_bytes() == shared_bytes, "Read-only preflight snapshot hash " + hashlib.sha256(shared_bytes).hexdigest())


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = Counter()
        self.links = []
    def handle_starttag(self, tag, attrs):
        self.tags[tag] += 1
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))


doc = Document()
doc.feed((B / "REVIEW_CARDS.html").read_text())
check("Readable document40 cards240 rows and80 primary/folder links", doc.tags["article"] == 40 and doc.tags["tr"] == 240 and len(doc.links) >= 80 and
      all(urlparse(u).netloc == "www.dropbox.com" for u in doc.links))
check("Package totals andzero policy replay", index["new_specification_approvals"] == 40 and index["new_approved_field_groups"] == 240 and
      index["existing_applicable_weight_displays_retained"] == 39 and index["new_conditional_net_weight_estimates"] == 1 and
      index["new_owner_policy_events"] == index["new_owner_approval_events"] == index["new_name_approvals"] == 0)

verification = save("BATCH_VERIFICATION.json", {
    "schema": "boldstone.independent-isolated-bulk-verification.v1", "checked_utc": NOW,
    "status": "PASS", "checks_passed": len(checks), "checks_failed": 0,
    "checks": checks, "scopes": individual_checks, "same_agent_separate_readback_pass": True,
    "independent_human_review_claimed": False, "shared_preflight_sha256": hashlib.sha256(shared_bytes).hexdigest(),
    "scope_limit": "Selected metadata and cached-image references only; no fresh original downloads, complete folder census, physical measurements or current price/stock verification.",
})
package = save("IMPORT_PACKAGE.json", {
    "schema": "boldstone.canonical-policy-working-specification-batch.v1",
    "status": "READY_FOR_SOLE_WRITER_IMPORT", "created_utc": NOW, "reserved_batch": 96,
    "source_owner_session": index["source_owner_session"], "shared_writer_session": index["shared_writer_session"],
    "allocation": index["allocation"], "allocation_addendum": index["allocation_addendum"],
    "owner_continue_all_evidence": index["owner_continue_all_evidence"],
    "standing_working_specification_policy": discovery["policies"]["standing"],
    "offered_fixing_choice_policy": discovery["policies"]["fixing"], "approximate_weight_policy": discovery["policies"]["weight"],
    "owner_manufacture_policy": discovery["policies"]["manufacture"],
    "policy_id": read(discovery["policies"]["standing"]["path"])["policy_id"],
    "existing_scopes": index["items"], "decisions": decisions, "verification": verification,
    "current_reference": ref(B / "CURRENT_REFERENCE_BINDING.json"), "visual_inspection": ref(B / "VISUAL_INSPECTION_RECEIPT.json"),
    "reader_document": ref(B / "REVIEW_CARDS.html"), "reader_records": ref(B / "REVIEW_CARDS.json"),
    "azure_conditional_net_weight_estimate": ref(B / "AZURE_CONDITIONAL_NET_WEIGHT_ESTIMATE.json"),
    "new_specification_approvals": 40, "new_approved_field_groups": 240,
    "existing_applicable_weight_displays_retained": 39, "new_conditional_net_weight_estimates": 1,
    "new_owner_policy_events": 0, "new_owner_approval_events": 0, "new_name_approvals": 0, "new_BC_component_ids": [],
    "shared_master_writes_by_lane": False, "remote_mutations": 0, "private_original_downloads": 0,
    "requested_import": "Exact40 B96 scopes only; exclude Flower under the allocation addendum. Preserve all raw six-field original/current dictionaries and owner face corrections. Accept working details under80 with87 offered choices and90 applicable approximations. Add Azure conditional7kg net range4–10 separately from15kg shipping; do not replay90. Keep source/build/layout/finish boundaries, Soundwave whole-source without a BC ID, unresolved platform/source conflicts, and per-scope contextual photo flags and gaps. Publication remains sole-writer work.",
})
sealed_files = [{**ref(p), "bytes": p.stat().st_size} for p in sorted(B.rglob("*")) if p.is_file()]
manifest = save("SEALED_MANIFEST.json", {
    "schema": "boldstone.immutable-bulk-package-manifest.v1", "sealed_utc": NOW,
    "status": "SEALED", "reserved_batch": 96, "package": package, "verification": verification,
    "files": sealed_files, "file_count_excluding_manifest": len(sealed_files),
    "source_cached_images_outside_package": [{k:r[k] for k in ["file_id","path","sha256","bytes","media_type"]} for r in media.values()],
    "frozen_after_seal": True, "subsequent_import_readback_must_be_additive_outside_this_package": True,
})
assert all(hash_ref(r) for r in sealed_files)
print(json.dumps({"status": "SEALED", "checks_passed": len(checks), "scope_count": 40, "field_count": 240,
                  "package": package, "verification": verification, "manifest": manifest,
                  "files_rehashed_after_seal": len(sealed_files)}))
