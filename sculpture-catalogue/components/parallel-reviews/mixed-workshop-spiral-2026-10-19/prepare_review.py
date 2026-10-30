"""Prepare an isolated identity review; never modify shared catalogue files."""
import datetime
import hashlib
import json
import pathlib
import re
from urllib.parse import quote

BASE = pathlib.Path(__file__).resolve().parent
if (BASE / "collection-only-decision/OWNER_DECISION.json").exists():
    raise SystemExit("Owner has deferred this collection. Preserve the closed review and its decision.")
ROOT = BASE.parents[2]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
OWNER = "01a13fe6-495b-7253-b923-31823b4cbca8"
MAIN = "01a144ab-1a7c-7223-a403-73a4d53d70ff"
TARGET = "BC-MIX-SPIRALS"


def read(p):
    return json.loads(pathlib.Path(p).read_text())


def digest(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def write(name, obj):
    p = BASE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    return {"path": str(p), "sha256": digest(p)}


ack = read(BASE / "COORDINATOR_ACKNOWLEDGEMENT.json")
assert ack["owner_session"] == OWNER and ack["component_ids"] == [TARGET]
assert ack["shared_master_writes_allowed"] is False
source = ROOT / "components/evidence/component_register.json"
ledger = ROOT / "components/reviews/user_classifications.json"
packets = ROOT / "components/parallel-preparation/20261017T164751Z/Prepared_Catalogue_Packets.json"
r, decisions, prepared = read(source), read(ledger), read(packets)
component = next(x for x in r["components"] if x["component_id"] == TARGET)
packet = next(x for x in prepared["entries"] if x["component_id"] == TARGET)
downloads = read(BASE / "family-media/fresh-download-receipt.json")
assert downloads["all_pass"] and len(downloads["entries"]) == 3
primary = next(x for x in downloads["entries"] if x["id"] == "id:cnqzTNngPVsAAAAAAAuTGg")
assert digest(primary["local_path"]) == primary["sha256"]

source_snapshot = write("source-snapshot.json", {
    "recorded_utc": NOW,
    "sources": [{"path": str(p), "sha256": digest(p)} for p in [source, ledger, packets]],
    "component": component,
    "prepared_packet": packet,
    "configurations": [x for x in r["configurations"] if TARGET in json.dumps(x)],
    "mixed_bindings": [x for x in r["mixed_bindings"] if TARGET in json.dumps(x)],
    "register_aliases": r["aliases"],
    "alias_and_identity_decisions": {
        k: v for k, v in decisions.items()
        if "alias" in k or k in ["component_identity_relationship_decisions", "catalogue_naming_corrections"]
    },
    "candidate_components": [x for x in r["components"] if re.search(r"spiral|strip", x.get("name", "") + " " + x.get("family", ""), re.I)],
    "scope": "Read-only source snapshot. No new identity, mould, stock, offer or specification approval."
})

documents_root = pathlib.Path("/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z")
texts = sorted((documents_root / "documents").glob("*.txt")) + sorted((documents_root / "late-source-check/documents").glob("*.txt"))
texts = [p for p in texts if not p.name.endswith(".docx.extracted.txt")]
search_terms = r"stacked|five.?spiral|spiral.?strip|strip|spiral"
exact_terms = r"stacked\s+spiral|five[ -]?spiral|spiral[ -]?strip"
doc_scan = []
for p in texts:
    lines = p.read_text(errors="replace").splitlines()
    matches = [{"line": i, "text": " ".join(s.split())} for i, s in enumerate(lines, 1) if re.search(search_terms, s, re.I)]
    doc_scan.append({"path": str(p), "sha256": digest(p), "matches": matches,
                     "exact_strip_phrase_matches": [m for m in matches if re.search(exact_terms, m["text"], re.I)]})

platform = read(BASE / "platform-photo-candidates.json")
for p in platform:
    p["reviewed_image"] = p["image"]["thumb"]
    p["reviewed_image_sha256"] = digest(p["reviewed_image"])
    p["review_scope"] = "Cached first gallery image visually inspected in full; not a fresh live listing read or whole-gallery census."
    p["result"] = "Does not establish the complete five-spiral vertical strip."
    if p["ref"] == "O046":
        p["result"] = "Cropped single Deco spiral detail; cannot establish the strip or a complete object's identity."

comparison = write("identity-comparison.json", {
    "recorded_utc": NOW,
    "target_id": primary["id"],
    "target_position": "Second from the right: narrow upright strip bearing five spiral motifs, between the large square spiral panel and the rightmost ribbed strip.",
    "observed_role": "Complete front silhouette visible within a mixed workshop photograph. Production role, joints, material and independent sale unit unknown.",
    "motifs_are_not_sale_units": True,
    "selected_full_frames": [
        {"id": primary["id"], "sha256": primary["sha256"], "role": "PRIMARY", "target_present": True},
        {"id": "id:cnqzTNngPVsAAAAAAA51YQ", "role": "EXCLUDED", "target_present": False, "reason": "Shows other curved and rippled panels; no five-spiral strip."},
        {"id": "id:cnqzTNngPVsAAAAAAArqRg", "role": "EXCLUDED", "target_present": False, "reason": "Two separate broad spiral panels; no five-spiral strip."}
    ],
    "related_designs_visually_compared": [
        {"component_id": "BC-SM-SPIRAL", "observation": "One broad spiral on a square backing; resembles the larger neighbouring panel. Does not establish a five-motif strip or shared mould."},
        {"component_id": "BC-CR-SPIRAL", "observation": "A rough textured continuous spiral on one square panel; different composition from the five-motif strip."},
        {"component_id": "BC-DR-SPIRAL", "observation": "Flowing parallel ridges ending in two curls; different composition from the five-motif strip."},
        {"component_id": "BC-DP-SPIRAL", "observation": "Single smooth angular spiral shown alone or with palms; shared motif language does not establish identity."}
    ],
    "cached_platform_first_photos": platform,
    "document_text_search": {"pattern": search_terms, "exact_strip_pattern": exact_terms, "sources": doc_scan,
        "limits": "Text search of cached source extracts; not a full visual examination of all source PDF pages. No material, measurement, weight or current offer inferred from analogous designs."},
    "alias_scope": "All ten register aliases and current shared alias/identity relationship decision collections read in source snapshot; no exact strip alias established.",
    "folder_scope": "Fresh complete listing contains 150 entries; three selected complete image frames inspected. No claim to have freshly inspected all 150 images. No whole-folder component binding.",
    "conclusion": "IDENTITY_UNRESOLVED_OWNER_QUESTION_REQUIRED",
    "platform_mapping": "No exact platform offer established by this bounded comparison."
})

folder_path = primary["path_display"].rsplit("/", 1)[0]
folder_url = "https://www.dropbox.com/home" + quote(folder_path, safe="/")
image_url = folder_url + "?preview=" + quote(primary["name"], safe="")
card = f"""Recorded: **Luciano Moonshell Lava and Lava Moon are the same design.** Lava Moon remains the catalogue name, with Luciano Moonshell Lava recorded as its historical name.

Next: **Five-Spiral Strip — workshop reference** (identity unconfirmed).

[Image]({image_url}) · [Containing folder]({folder_url})

The target is the **narrow strip with five spirals, second from the right**, beside the large square spiral. These links open in your Dropbox account.

| Specification | Detail or proposal |
|---|---|
| Dimensions | Approximately 90 × 15 cm, depth 5–7 cm — very tentative guess; no scale or measurement available |
| Weight | Unknown; 4–8 kg is only a planning guess for a new lightweight cast at that proposed size |
| Material / finish | Pale stone-like appearance; cast composite is a guess. Actual material and production role unknown |
| Fixings | Rear unseen; concealed rear fixings are a proposal requiring design and load confirmation |
| Individual price | Unknown; £250–450 is an uncosted proposal only if confirmed as a saleable strip |
| Availability | Unconfirmed; the photograph does not establish current stock or manufacture |

An isolated photograph, rear view and measurements are still missing.

**How should this five-spiral strip be identified: an existing named design, a separate finished sculpture, or a master/sample?**

<oai-mem-citation>
<citation_entries>
MEMORY.md:110-112|note=[Preserved owner identity decisions and unconfirmed specifications]
MEMORY.md:119-119|note=[Separated mixed photograph evidence from individual product identity]
</citation_entries>
<rollout_ids>
01a13fbf-1cbc-7511-8416-cf339051083e
</rollout_ids>
</oai-mem-citation>
"""
card_path = BASE / "review-123/PRE_ANSWER_CARD.md"
card_path.parent.mkdir(exist_ok=True)
card_path.write_text(card)
review = write("review-123/REVIEW.json", {
    "schema": "boldstone.identity-review.v1", "created_utc": NOW,
    "review_number": 123, "review_id": "R123-MIX-SPIRALS", "component_id": TARGET,
    "status": "AWAITING_OWNER_IDENTITY", "identity_approved": False,
    "owner_turn": None, "keep_recorded": False,
    "all_six_fields_pending": True, "physical_specs_verified": False,
    "specification_proposals": packet["specifications"],
    "card": {"path": str(card_path), "sha256": digest(card_path)},
    "primary_image": primary, "image_url": image_url, "folder_url": folder_url,
    "link_status": "ACCOUNT_PATH_LINKS_CURRENT_METADATA_BOUND_NOT_BROWSER_TESTED",
    "source_snapshot": source_snapshot, "identity_comparison": comparison,
    "forbidden_inferences": ["whole-folder identity", "five independent sale units", "new mould or stock count", "known material or mass", "exact platform offer"],
    "remote_mutations": 0, "shared_catalogue_writes": 0
})
write("OWNERSHIP.json", {
    "schema": "boldstone.parallel-review-ownership.v1", "created_utc": NOW,
    "owner_session": OWNER, "main_shared_master_writer": MAIN,
    "component_ids": [TARGET], "review_numbers": [123], "group_refs": ["G050"],
    "exclusive_output": str(BASE), "status": "ACTIVE_AWAITING_OWNER_IDENTITY",
    "coordinator_acknowledgement_sha256": digest(BASE / "COORDINATOR_ACKNOWLEDGEMENT.json"),
    "shared_master_writes": False, "remote_mutations_allowed": False,
    "active_review_id": "R123-MIX-SPIRALS", "kept_working_review_ids": []
})
write("CHECKPOINT.json", {
    "updated_utc": NOW, "owner_session": OWNER,
    "state": "AWAITING_OWNER_IDENTITY", "component_id": TARGET,
    "review_number": 123, "review": review,
    "next_action": "Capture exact owner reply and bind it to this frozen pre-answer card; reconcile identity before any proposed Keep or import.",
    "main_pending_concave_mcp4_untouched": True,
    "all_six_fields_pending": True, "remote_mutations": 0, "shared_catalogue_writes": 0
})
checks = {
    "allocation_exact_component": ack["component_ids"] == [TARGET],
    "three_downloads_verified": downloads["all_pass"],
    "target_exact_id": primary["id"] == "id:cnqzTNngPVsAAAAAAAuTGg",
    "target_hash_readback": digest(primary["local_path"]) == primary["sha256"],
    "six_fields": len(packet["specifications"]) == 6,
    "card_bytes_readback": card_path.read_text() == card,
    "no_shared_source_changes": all(digest(x["path"]) == x["sha256"] for x in read(BASE / "source-snapshot.json")["sources"]),
    "all_platform_comparisons_exist": all(pathlib.Path(p["reviewed_image"]).exists() for p in platform),
    "no_owner_approval_invented": read(BASE / "review-123/REVIEW.json")["owner_turn"] is None,
}
receipt = write("PREPARATION_READBACK.json", {"checked_utc": NOW, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"})
print(json.dumps({"review": review, "readback": receipt, "checks": checks,
                  "document_extracts_searched": len(doc_scan),
                  "exact_strip_phrase_matches": sum(len(x["exact_strip_phrase_matches"]) for x in doc_scan)}, indent=2))
assert all(checks.values())
