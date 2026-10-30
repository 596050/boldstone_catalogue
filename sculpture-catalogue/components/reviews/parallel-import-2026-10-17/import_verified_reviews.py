"""Serialize verified peer decisions into review overlays, preserving the active review."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / "components/reviews"
PEERS = ROOT / "components/parallel-reviews"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return str(path.relative_to(ROOT))


SOURCES = [
    ("BC-CR-SPIRAL", "cup-ring-spiral-crs1-2026-10-17", "owner-approval.json", "pre-approval-component-review.json", "source_review_sha256_before_approval"),
    ("BC-DP-PALM1", "deco-palm-palm1-2026-10-17", "identity-approval.json", "pre-identity-approval-component-review.json", "source_review_sha256_before_answer"),
    ("BC-DP-PALM2", "deco-palm-palm2-2026-10-17", "identity-approval.json", "pre-identity-approval-component-review.json", "source_review_sha256_before_answer"),
]
TRANSCRIPTS = {
    "01a13fbf-1cbc-7511-8416-cf339051083e": Path("/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl"),
    "01a13fe6-495b-7253-b923-31823b4cbca8": Path("/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-01a13fe6-495b-7253-b923-31823b4cbca8.jsonl"),
}


def user_evidence(path, wanted):
    found = {}
    with path.open() as handle:
        for number, line in enumerate(handle, 1):
            if not ('"role": "user"' in line or '"role":"user"' in line):
                continue
            obj = json.loads(line)
            payload = obj.get("payload", {})
            if obj.get("type") != "response_item" or payload.get("role") != "user":
                continue
            text = "\n".join(x.get("text", "") for x in payload.get("content", []) if isinstance(x, dict))
            if text in wanted:
                found[text] = {"transcript_path": str(path), "line": number, "timestamp": obj.get("timestamp"), "user_statement": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    assert set(found) == set(wanted), "Missing authoritative user statement"
    return found


def main():
    if (HERE / "import-receipt.json").exists():
        text = read(HERE / "import-receipt.json")
        assert text["status"] == "APPLIED_AND_VERIFIED"
        print(json.dumps({"status": "ALREADY_APPLIED", "receipt": rel(HERE / "import-receipt.json")}))
        return
    now = datetime.now(timezone.utc).isoformat()
    paths = {"user": REVIEWS / "user_classifications.json", "progress": REVIEWS / "specification_review_progress.json", "walkthrough": REVIEWS / "walkthrough_checkpoint.json", "component": ROOT / "components/checkpoint.json", "root": ROOT / "checkpoint.json"}
    docs = {k: read(p) for k, p in paths.items()}
    cp, user, progress, component = (docs[k] for k in ["walkthrough", "user", "progress", "component"])
    assert cp["current_component_id"] == "BC-DDR-WAVE" and cp["current_size_finish_variant_id"] == "DDR-WAVE-VERDIGRIS"
    assert not cp["current_answer_recorded"] and not cp["current_specification_answer_recorded"]
    active_keys = [k for k in cp if k.startswith("current_")] + ["state", "proposed_name", "primary_image", "containing_folder", "question_scope", "answer_state", "next_review_after_keep", "active_family", "family_review_order", "family_review_evidence", "last_completed_component_id", "last_completed_review_number", "last_identity_approval"]
    active_before = {k: copy.deepcopy(cp[k]) for k in active_keys}
    protected_paths = [ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"], ROOT / cp["current_review_record"]]
    protected = {p: sha(p) for p in protected_paths}
    master_before = {p: sha(p) for p in paths.values()}
    reference = read(HERE / "current-reference-check.json")
    live_files = {x["file"]["id"]: x["file"] for x in reference["primary_metadata"] if x.get("metadata_type") == "file"}
    copied_sources = []

    def freeze(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        assert sha(source) == digest == sha(target)
        copied_sources.append({"source": str(source), "snapshot": rel(target), "sha256": digest})
        return target

    prepared = []
    peer_wanted = []
    for cid, sub, receipt_name, before_name, hash_key in SOURCES:
        directory = PEERS / sub
        receipt, review = read(directory / receipt_name), read(directory / "component-review.json")
        assert receipt["component_id"] == review["component_id"] == cid
        assert receipt["identity_confirmed"] and not receipt["physical_specs_verified"]
        assert sha(directory / before_name) == receipt[hash_key]
        assert len(review["specification_review_items"]) == 6
        primary = review["primary_image"]
        current = live_files[receipt["primary_file_id"]]
        assert current["id"] == primary["id"] and current["rev"] == primary["rev"] and current["size"] == primary["size"]
        assert receipt["primary_folder_id"] == review["containing_folder"]["id"]
        assert current["path_display"] == primary["path"]
        if cid == "BC-CR-SPIRAL":
            assert receipt["proposals_approved"] and len(receipt["approved_proposal_ids"]) == 6
            assert sha(directory / "Current_Metadata.json") == receipt["source_metadata_sha256"]
        else:
            assert not receipt["proposals_approved"] and not receipt["specifications_approved"] and not receipt["approved_proposal_ids"]
        dest = HERE / "components" / cid
        for name in [receipt_name, "component-review.json", before_name, "Current_Metadata.json", "Approval_Presentation.md"]:
            freeze(directory / name, dest / "sources" / name)
        peer_wanted.append(receipt["user_statement"])
        prepared.append((cid, receipt, review, dest))
    peer_user = user_evidence(TRANSCRIPTS["01a13fbf-1cbc-7511-8416-cf339051083e"], peer_wanted)

    family_dir = PEERS / "wall-circle-2026-10-17/family-keep"
    package = read(family_dir / "IMPORT_PACKAGE.json")
    family = read(Path(package["family_approval_record"]))
    family_user = user_evidence(TRANSCRIPTS[family["owner_session"]], [family["user_statement"]])
    assert family["decision_id"] == "WALL-CIRCLE:family-keep:2026-10-17"
    source_census = read(family_dir / "dropbox-current-census.json")
    current_census = reference["wall_circle_current_census"]
    assert source_census["pagination_complete"] and not current_census["has_more"]
    previous = {x["file_id"]: x for x in source_census["entries"]}
    current = {x["file_id"]: x for x in current_census["entries"]}
    assert set(previous) == set(current)
    for iid, entry in current.items():
        assert entry["object_type"] == previous[iid]["object_type"]
        if entry["object_type"] == "file":
            assert entry["file"]["size"] == previous[iid]["file"]["size"]
            assert entry["modified_time"] == previous[iid]["modified_time"]
    assert sum(x["object_type"] == "file" for x in current.values()) == 167
    assert sum(x["object_type"] == "folder" for x in current.values()) == 13
    index = read(Path(package["visual_pattern_index"]))
    media = read(Path(package["media_group_register"]))
    options = read(Path(package["native_option_register"]))
    candidates = read(Path(package["native_image_similarity_candidates"]))
    assert len(index) == 7 and len(media) == 13 and len(options) == 144 and len(candidates) == 18
    assert len({x["variant_id"] for x in options}) == 144
    assert len({x["attributes"]["Pattern"] for x in options}) == 18
    media_ids = [iid for group in media for iid in group["file_ids"]]
    assert len(media_ids) == len(set(media_ids)) == 167
    assert set(media_ids) == {iid for iid, x in current.items() if x["object_type"] == "file"}
    family_dest = HERE / "wall-circle"
    for name in ["IMPORT_PACKAGE.json", "family-approval.json", "visual-pattern-index.json", "media-group-register.json", "native-option-register.json", "native-image-similarity-candidates.json", "dropbox-current-census.json", "VALIDATION.json"]:
        freeze(family_dir / name, family_dest / "sources" / name)
    native_item = read(family_dir / "squarespace-current.json")["item"]
    write(family_dest / "native-product-source.json", {"source": str(family_dir / "squarespace-current.json"), "source_sha256": sha(family_dir / "squarespace-current.json"), "item": native_item})
    visual_records = []
    for entry in index:
        source = Path(entry["record"])
        record = read(source)
        iid, fid = record["primary_image"]["id"], record["containing_folder"]["id"]
        assert iid in current and fid in current and current[fid]["object_type"] == "folder"
        parent_path = current[iid]["path"].rsplit("/", 1)[0]
        assert parent_path == current[fid]["path"]
        assert len(record["specification_review_items"]) == 6
        freeze(source, family_dest / "visual-pattern-records" / (entry["review_id"] + ".json"))
        visual_records.append({"review_id": entry["review_id"], "working_name": entry["working_name"], "group_ref": entry["group_ref"], "primary_file_id": iid, "primary_folder_id": fid, "current_primary_path": current[iid]["path"], "current_folder_path": current[fid]["path"], "image_url": entry["image_url"], "folder_url": entry["folder_url"], "working_entry_kept": True, "physical_manufacture_confirmed": bool(entry["physical_manufacture_confirmed"]), "physical_specs_verified": False, "specification_review_items": copy.deepcopy(record["specification_review_items"]), "source_record_snapshot": rel(family_dest / "visual-pattern-records" / (entry["review_id"] + ".json"))})
    assert [x["review_id"] for x in visual_records if x["physical_manufacture_confirmed"]] == ["WC-01"]
    wc01 = read(PEERS / "wall-circle-2026-10-17/working-entry.json")
    assert wc01["weight"] == "Approximately 12 kg" and wc01["dimensions"] == "50 cm diameter × 2.5 cm deep"
    assert wc01["lighting"] == "RGB lighting" and wc01["fixings"] == "French cleat"
    freeze(PEERS / "wall-circle-2026-10-17/working-entry.json", family_dest / "wc01-owner-stated-entry.json")
    for name in ["manufacture-status-decision.json", "dimension-decision.json", "material-decision.json", "weight-decision.json", "fixings-lighting-decision.json", "price-decision.json", "availability-decision.json"]:
        freeze(PEERS / "wall-circle-2026-10-17" / name, family_dest / "wc01-decisions" / name)
    family_catalogue = {"schema_version": 1, "recorded_utc": now, "component_id": "BC-WALL-CIRCLE", "scope_kind": "SUPPLEMENTAL_FAMILY_WORKING_CATALOGUE", "family_approval": family, "authoritative_user_evidence": family_user[family["user_statement"]], "visual_working_records": visual_records, "media_group_register": media, "native_option_register": options, "native_pattern_candidates": candidates, "native_squarespace_product_id": native_item["id"], "native_squarespace_url": "https://boldstonesculpture.com" + native_item["fullUrl"], "shopify_handle_confirmed": False, "native_pattern_alias_mapping_status": package["matching_status"], "native_options_preserved_without_template_overwrite": True, "wc01_owner_stated_entry": wc01, "counts": {"visual_working_records": 7, "media_groups": 13, "media_files": 167, "native_named_patterns": 18, "native_option_rows": 144, "owner_reported_manufactured_visual_records": 1}, "counting_rule": "These layers overlap and must not be summed as distinct designs, manufactured pieces or sale stock. The main123 working-component baseline is unchanged. Only WC-01 has explicit owner-reported physical existence; no current quantity or full physical verification is inferred.", "native_stock_verified": False, "physical_specs_verified": False, "workbook_contains_import": False, "remote_files_changed": False}
    write(family_dest / "approved-working-catalogue.json", family_catalogue)

    # All evidence checks finish before shared records change.
    assert all(sha(p) == expected for p, expected in master_before.items())
    backup = HERE / "before-import.json"
    write(backup, {"recorded_utc": now, "files": {rel(paths[k]): v for k, v in docs.items()}})
    imported = []
    for cid, receipt, review, dest in prepared:
        source_statement = peer_user[receipt["user_statement"]]
        identity_id = f"{cid}:identity:keep"
        identity = {"schema_version": 1, "decision_id": identity_id, "recorded_utc": receipt["recorded_utc"], "imported_utc": now, "component_id": cid, "review_number": receipt["review_number"], "canonical_name": receipt["canonical_name"], "confirmed_name": receipt["canonical_name"], "proposed_name_at_review": review["proposed_name"], "action": "keep", "identity_status": "USER CONFIRMED", "identity_confirmed": True, "confirmed_fields": ["component name", "depicted individual component identity", "retain individual component record"], "user_statement": receipt["user_statement"], "source_owner_session": receipt["owner_session"], "source_decision_id": receipt["decision_id"], "source_receipt_snapshot": rel(dest / "sources" / ("owner-approval.json" if cid == "BC-CR-SPIRAL" else "identity-approval.json")), "authoritative_user_evidence": source_statement, "evidence_file_id": receipt["primary_file_id"], "containing_folder_id": receipt["primary_folder_id"], "evidence_file_ids": [receipt["primary_file_id"]], "containing_folder_ids": [receipt["primary_folder_id"]], "image_link": review["image_url"], "folder_link": review["folder_url"], "specifications_approved": bool(receipt["proposals_approved"]), "physical_specs_verified": False, "scope": receipt.get("scope", "Name/identity and the explicitly accepted six working groups; source conflicts and physical uncertainty retained."), "not_confirmed": receipt.get("pending_specification_fields", receipt.get("retained_limits", []))}
        identity_path = dest / "identity-approval.json"
        write(identity_path, identity)
        assert not any(x["component_id"] == cid for x in user["decisions"])
        user["decisions"].append(identity | {"approval_record": rel(identity_path)})
        items = [{"proposal_id": x["proposal_id"], "field": x["field"], "display": x.get("approved_displayed_detail", x["displayed_detail"]), "source_evidence": copy.deepcopy(x["source_evidence"]), "owner_approved": bool(receipt["proposals_approved"]), "physical_specs_verified": False} for x in review["specification_review_items"]]
        record = {"reviewed_utc": now, "identity_confirmed": True, "identity_confirmed_utc": receipt["recorded_utc"], "canonical_name": receipt["canonical_name"], "identity_approval": rel(identity_path), "specifications_approved": bool(receipt["proposals_approved"]), "proposals_approved": bool(receipt["proposals_approved"]), "physical_specs_verified": False, "specification_proposals": items, "source_specifications_recorded": True, "review_record": rel(dest / "sources/component-review.json"), "primary_image_id": receipt["primary_file_id"], "primary_folder_id": receipt["primary_folder_id"], "platform_mapping": copy.deepcopy(review.get("platform_mapping", [])), "source_conflicts": copy.deepcopy(review.get("source_conflicts", [])), "remaining_unknowns": copy.deepcopy(review.get("open_questions", receipt.get("retained_limits", []))), "imported_from_owner_session": receipt["owner_session"]}
        if cid == "BC-CR-SPIRAL":
            spec = {"schema_version": 1, "decision_id": f"{cid}:specifications:keep:2026-10-17", "recorded_utc": receipt["recorded_utc"], "imported_utc": now, "component_id": cid, "canonical_name": receipt["canonical_name"], "review_number": receipt["review_number"], "family_review_number": 1, "action": "keep", "user_statement": receipt["user_statement"], "status": receipt["status"], "scope": "Six displayed working groups explicitly accepted; historical estimates and source conflicts remain. No physical verification, actual stock/lead time or new platform offer inferred.", "approved_proposal_ids": receipt["approved_proposal_ids"], "approved_specification_items": items, "approved_details": receipt["approved_details"], "proposals_approved": True, "physical_specs_verified": False, "shopify_match_confirmed": False, "primary_file_id": receipt["primary_file_id"], "primary_folder_id": receipt["primary_folder_id"], "source_receipt_snapshot": identity["source_receipt_snapshot"], "authoritative_user_evidence": source_statement, "remaining_unknowns": receipt["retained_limits"], "retained_source_conflicts": receipt["retained_source_conflicts"], "image_link": review["image_url"], "folder_link": review["folder_url"], "remote_files_changed": False, "live_platform_records_changed": False}
            spec_path = dest / "specification-approval.json"
            write(spec_path, spec)
            user["specification_decisions"].append({k: spec[k] for k in ["decision_id", "recorded_utc", "component_id", "canonical_name", "review_number", "family_review_number", "action", "user_statement", "status", "scope", "approved_proposal_ids", "proposals_approved", "physical_specs_verified", "primary_file_id", "primary_folder_id"]} | {"approval_record": rel(spec_path), "shopify_match_confirmed": False})
            record.update({"specification_approval": rel(spec_path), "approved_specification_items": items, "specification_proposals_status": spec["status"]})
            progress["latest_parallel_specification_approval"] = rel(spec_path)
        else:
            queue = cp.setdefault("pending_specification_reviews", [])
            if not any(x.get("component_id") == cid for x in queue):
                queue.append({"component_id": cid, "canonical_name": receipt["canonical_name"], "identity_approved": True, "specifications_approved": False, "pending_fields": receipt["pending_specification_fields"], "review_record": record["review_record"], "identity_approval": rel(identity_path), "image_link": review["image_url"], "folder_link": review["folder_url"]})
        assert cid not in progress["reviews"]
        progress["reviews"][cid] = record
        imported.append({"component_id": cid, "canonical_name": receipt["canonical_name"], "identity_approval": rel(identity_path), "specifications_approved": bool(receipt["proposals_approved"]), "source_user_statement": source_statement, "source_receipt": identity["source_receipt_snapshot"]})
    family_decision = copy.deepcopy(family) | {"imported_utc": now, "authoritative_user_evidence": family_user[family["user_statement"]], "shared_working_catalogue": rel(family_dest / "approved-working-catalogue.json"), "counting_scope": family_catalogue["counting_rule"], "physical_specs_verified": False, "workbook_contains_import": False}
    user.setdefault("family_decisions", []).append(family_decision)
    user["family_approval_counts"] = {"families": 1, "visual_working_records": 7, "visual_working_specification_groups": 42, "native_named_patterns": 18, "native_option_rows": 144, "media_files": 167, "distinct_physical_sculpture_total_asserted": False}
    user["counts_scope_note"] = "Per-component identity/proposal/dimension counts cover the interactive component register. Wall Circle family-wide working acceptance is counted separately; visual patterns, native options and images are overlapping evidence layers, not extra physical sculptures."
    family_summary = {"component_id": "BC-WALL-CIRCLE", "scope_kind": "SUPPLEMENTAL_FAMILY_WORKING_CATALOGUE", "family_working_entries_approved": True, "family_approval_record": rel(family_dest / "sources/family-approval.json"), "catalogue": rel(family_dest / "approved-working-catalogue.json"), "counts": family_catalogue["counts"], "physical_manufacture_scope": family["physical_manufacture_confirmation_scope"], "exact_native_pattern_aliases_confirmed": False, "physical_specs_verified": False, "workbook_contains_import": False}
    progress.setdefault("family_reviews", {})["BC-WALL-CIRCLE"] = family_summary
    names = len({x["component_id"] for x in user["decisions"]})
    specs = user["specification_decisions"]
    build = user.get("build_variant_decisions", [])
    regular_groups = sum(len(x["approved_proposal_ids"]) for x in specs)
    build_groups = sum(len(x["approved_proposal_ids"]) for x in build)
    user["identity_confirmation_counts"]["component_designs"] = names
    user["specification_approval_counts"] = {"components": len({x["component_id"] for x in specs}), "component_proposal_groups": regular_groups, "build_variant_approvals": len(build), "build_variant_proposal_groups": build_groups, "proposal_groups": regular_groups + build_groups}
    user["updated_utc"] = progress["updated_utc"] = now
    imported_paths = {rel(PEERS / sub / receipt) for _, sub, receipt, _, _ in SOURCES}
    for entry in cp.get("parallel_import_queue", []):
        if entry["receipt"] in imported_paths or entry.get("component_id") == "BC-WALL-CIRCLE":
            entry.update({"status": "IMPORTED INTO SHARED REVIEW OVERLAYS; WORKBOOK EXPORT PENDING", "approval_imported": True, "import_receipt": rel(HERE / "import-receipt.json"), "imported_utc": now})
    cp["parallel_import_queue"].append({"component_id": "BC-WALL-CIRCLE", "receipt": rel(Path(package["family_approval_record"])), "status": "FAMILY PACKAGE IMPORTED INTO SHARED REVIEW OVERLAYS; WORKBOOK EXPORT PENDING", "approval_imported": True, "import_receipt": rel(HERE / "import-receipt.json"), "imported_utc": now})
    for reservation in cp.get("parallel_owner_reviews", []):
        if reservation["component_id"] in {x[0] for x in SOURCES}:
            reservation.update({"status": "OWNER ANSWER IMPORTED; SPECIFICATIONS KEPT ONLY WHERE EXPLICIT", "import_receipt": rel(HERE / "import-receipt.json")})
    cp["last_parallel_import"] = {"recorded_utc": now, "receipt": rel(HERE / "import-receipt.json"), "component_ids": [x[0] for x in SOURCES], "family_ids": ["BC-WALL-CIRCLE"], "active_review_preserved": True}
    cp["updated_utc"] = now
    component["interactive_review_state"].update({"explicit_identity_confirmations": names, "explicit_specification_approvals": user["specification_approval_counts"]["components"], "approved_proposal_groups": regular_groups + build_groups})
    component["parallel_import_queue"] = copy.deepcopy(cp["parallel_import_queue"])
    component["parallel_owner_reviews"] = copy.deepcopy(cp["parallel_owner_reviews"])
    component.setdefault("family_review_supplements", {})["BC-WALL-CIRCLE"] = family_summary
    component["last_parallel_import"] = copy.deepcopy(cp["last_parallel_import"])
    component["updated_utc"] = now
    docs["root"]["current_component_review"] = copy.deepcopy(component)
    assert {k: cp[k] for k in active_keys} == active_before
    assert names == 23 and user["specification_approval_counts"]["components"] == 8 and regular_groups + build_groups == 55
    assert not progress["reviews"]["BC-DP-PALM1"]["specifications_approved"] and not progress["reviews"]["BC-DP-PALM2"]["specifications_approved"]
    assert not progress["reviews"]["BC-DDR-WAVE"]["size_finish_variants"]["DDR-WAVE-VERDIGRIS"]["identity_confirmed"]
    write(HERE / "source-manifest.json", {"recorded_utc": now, "files": copied_sources, "user_evidence": list(peer_user.values()) + list(family_user.values())})
    for key, path in paths.items():
        write(path, docs[key])
    event_id = "parallel-import:CRS1-DP28-DP29-WallCircle:2026-10-17"
    event = {"event_id": event_id, "event": "PARALLEL_OWNER_REVIEWS_IMPORTED", "recorded_utc": now, "import_receipt": rel(HERE / "import-receipt.json"), "component_ids": [x[0] for x in SOURCES], "family_ids": ["BC-WALL-CIRCLE"], "active_component": "BC-DDR-WAVE", "active_variant": "DDR-WAVE-VERDIGRIS", "active_answer_inferred": False, "source_model_workbook_changed": False, "remote_files_changed": False}
    for log in [REVIEWS / "identity_review_journal.jsonl", ROOT / "review_journal.jsonl"]:
        prior = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        if not any(x.get("event_id") == event_id for x in prior):
            with log.open("a") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    assert all(sha(p) == digest for p, digest in protected.items())
    assert {k: read(paths["walkthrough"])[k] for k in active_keys} == active_before
    assert read(paths["root"])["current_component_review"] == read(paths["component"])
    assert component["counts"]["components_in_working_register"] == 123 and component["counts"]["fully_physically_verified"] == 0
    result = {"schema_version": 1, "status": "APPLIED_AND_VERIFIED", "recorded_utc": now, "imported_components": imported, "family_import": family_summary, "identity_component_count": names, "specification_approval_component_count": 8, "approved_regular_and_build_proposal_groups": 55, "family_visual_proposal_groups_counted_separately": 42, "main_working_component_baseline": 123, "distinct_manufactured_total_not_inferred": True, "native_options_preserved": 144, "current_active_component": "BC-DDR-WAVE", "current_active_variant": "DDR-WAVE-VERDIGRIS", "current_question_and_answer_state_unchanged": True, "source_model_and_workbook_unchanged": True, "workbook_export_pending": True, "remote_files_changed": False, "source_manifest": rel(HERE / "source-manifest.json"), "before_import_backup": rel(backup)}
    write(HERE / "import-receipt.json", result)
    print(json.dumps({k: result[k] for k in ["status", "identity_component_count", "specification_approval_component_count", "approved_regular_and_build_proposal_groups", "native_options_preserved", "current_active_variant", "current_question_and_answer_state_unchanged", "source_model_and_workbook_unchanged"]}))


if __name__ == "__main__":
    main()
