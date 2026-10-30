"""Independently inspect the published native files without writing shared state."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

BASE = Path(__file__).resolve().parents[1]
CATALOGUE = BASE.parents[2]
OUT = Path(__file__).resolve().parent
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
checks = []


def check(label, value):
    checks.append({"check": label, "pass": bool(value)})


def workbook(path):
    sheets = {}
    with ZipFile(path) as z:
        check("published workbook ZIP integrity", z.testzip() is None)
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        relationships = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        for s in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS):
            target = relationships[s.attrib[REL]]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            rows = []
            for row in ET.fromstring(z.read(target)).findall("m:sheetData/m:row", NS):
                values = {}
                for cell in row:
                    v = cell.find("m:v", NS)
                    text = (v.text or "") if v is not None else "".join(t.text or "" for t in cell.findall(".//m:t", NS))
                    if cell.attrib.get("t") == "s":
                        text = strings[int(text)]
                    if cell.attrib.get("t") == "e":
                        check(f"no native Excel error {s.attrib['name']}!{cell.attrib['r']}", False)
                    col = "".join(c for c in cell.attrib["r"] if c.isalpha())
                    values[col] = text
                rows.append(values)
            sheets[s.attrib["name"]] = rows
    return sheets


pointer_bytes = (CATALOGUE / "current-master.json").read_bytes()
pointer = json.loads(pointer_bytes)
staged = "--staged" in sys.argv
if staged:
    stage = CATALOGUE / "components/reconciliation/listing-resolution-import-2026-10-21"
    register_path = stage / "canonical-master-register.json"
    workbook_path = stage / "master-workbook.pending"
else:
    register_path = CATALOGUE / pointer["register"]
    workbook_path = CATALOGUE / pointer["workbook"]
register_bytes = register_path.read_bytes()
workbook_bytes = workbook_path.read_bytes()
if not staged:
    check("register exact pointer hash", hashlib.sha256(register_bytes).hexdigest() == pointer["register_sha256"])
    check("workbook exact pointer hash", hashlib.sha256(workbook_bytes).hexdigest() == pointer["workbook_sha256"])
    check("current publication pointer stable during read", pointer_bytes == (CATALOGUE / "current-master.json").read_bytes())
current = json.loads(register_bytes)
prior = json.loads((BASE / "inputs/rebase-cup-frozen/master-register.json").read_text())
expected = json.loads((BASE / "LISTING_RESOLUTION.json").read_text())
prior_by_id = {e["product_id"]: e for e in prior["options"]}
current_by_id = {e["product_id"]: e for e in current["options"]}
overlays = {e["product_id"]: e for e in expected["option_overlays"]}
check("same184 immutable catalogue IDs", set(prior_by_id) == set(current_by_id) == set(overlays) and len(current["options"]) == 184)
for pid, old in prior_by_id.items():
    e = current_by_id[pid]
    check(f"catalogue identity preserved {pid}", (old["product_id"], old["canonical_key"], old["name"]) == (e["product_id"], e["canonical_key"], e["name"]))
    check(f"all six accepted field groups preserved {pid}", e["master_fields"] == old["master_fields"])
    check(f"current resolution imported exactly {pid}", e.get("current_listing_resolution") == overlays[pid])
for key in ["current_listing_source_links", "current_listing_match_evidence", "current_listing_issues"]:
    check(f"dated source history preserved {key}", current[key] == prior[key])
check("all144 Wall Circle native rows retained", current["wall_circle_native_options"] == prior["wall_circle_native_options"] and len(current["wall_circle_native_options"]) == 144)
check("47 source-supported catalogue option records", sum(e.get("current_listing_resolution", {}).get("source_supported_individual_record_present", False) for e in current["options"]) == 47)
check("four conditional working Wall Circle native lookups", sum(bool(e.get("current_listing_resolution", {}).get("conditional_native_tuple")) for e in current["options"]) == 4)
for imported_key, source_file in [
    ("current_listing_resolution", "LISTING_RESOLUTION.json"),
    ("current_listing_resolution_details", "OPTION_RESOLUTIONS_106.json"),
    ("listing_resolution_source_edges", "NEW_SOURCE_LINKS.json"),
    ("listing_resolution_native_action_drafts", "NATIVE_ACTION_DRAFTS.json"),
]:
    check(f"full source packet preserved {source_file}", current.get(imported_key) == json.loads((BASE / source_file).read_text()))
metadata = current.get("latest_listing_resolution", {})
check("published listing metadata binds sealed payload", metadata.get("payload_sha256") == hashlib.sha256((BASE / "LISTING_RESOLUTION.json").read_bytes()).hexdigest())
check("published listing metadata retains no-execution scope", metadata.get("counts", {}).get("platform_writes") == 0 and metadata.get("counts", {}).get("proven_live_absences") == 0)

# Reopen the workbook bytes just hashed, so a later coordinator publication cannot race this audit.
snapshot = OUT / ("staged-master.xlsx" if staged else "published-master.xlsx")
snapshot.write_bytes(workbook_bytes)
sheets = workbook(snapshot)
old_sheets = workbook(BASE / "inputs/rebase-cup-frozen/current-master.xlsx")
check("all16 earlier source/catalogue sheets retained", set(old_sheets).issubset(sheets) and len(old_sheets) == 16)
catalogue_rows = [r for r in sheets["Master Catalogue"] if r.get("A") in current_by_id]
check("184 saved native Master Catalogue rows", len(catalogue_rows) == len({r["A"] for r in catalogue_rows}) == 184)
spec_rows = [r for r in sheets["Specifications"] if r.get("A") in current_by_id]
check("1104 saved specification groups", len(spec_rows) == 1104 and len({r.get("P") for r in spec_rows}) == 1104)
field_order = ["Dimensions / depth", "Weight", "Material / finish", "Fixing", "Individual price", "Availability"]
for r in catalogue_rows:
    e = current_by_id[r["A"]]
    check(f"saved row name exact {r['A']}", r.get("B") == e["name"])
    for col, field in zip("EFGHIJ", field_order):
        check(f"saved catalogue field exact {r['A']} {field}", r.get(col, "") == e["master_fields"][field]["display"])
for r in spec_rows:
    e = current_by_id[r["A"]]
    field = r["C"]
    check(f"saved specification value/state exact {r['P']}", r.get("D", "") == e["master_fields"][field]["display"] and r.get("E", "") == e["master_fields"][field]["state"])
new_sheets = sorted(set(sheets) - set(old_sheets))
new_sheet_option_counts = {s: sum(any(v in current_by_id for v in row.values()) for row in sheets[s]) for s in new_sheets}
check("new native current-resolution views exist", bool(new_sheets) and any(n == 184 for n in new_sheet_option_counts.values()))
resolution_rows = {r.get("A"): r for r in sheets.get("Listing Resolution", []) if r.get("A") in current_by_id}
for pid, e in overlays.items():
    candidates = ([e["conditional_native_tuple"]] if e["conditional_native_tuple"] else []) + [m for m in e["new_supported_source_matches"] if m["platform"] == "Squarespace"]
    for match in candidates:
        row = resolution_rows.get(pid, {})
        values = list(row.values())
        native_values = [match["native_product_id"], match["native_variant_id"], match.get("sku", match.get("sku_raw"))]
        if e["conditional_native_tuple"]:
            check(f"saved conditional native product/variant/SKU assignment {pid}", all(v in values for v in native_values))
            check(f"saved conditional WC axes {pid}", match["diameter_option"] in values and match["lighting_option"] in values and row.get("D") == "0" and row.get("E") == "1")
        else:
            check(f"positive native tuple in preserved source view {pid}", any(all(v in source_row.values() for v in native_values) for source_row in sheets["Listing Offer Links"]))
            check(f"positive source binding in current resolution view {pid}", row.get("D") == "1" and row.get("E") == "0" and row.get("F") == "1")
expected_drafts = json.loads((BASE / "OPTION_RESOLUTIONS_106.json").read_text())["entries"]
draft_skus = {e["draft_listing"]["proposed_sku"] for e in expected_drafts if e["draft_listing"]}
saved_draft_skus = [r.get("D") for r in sheets.get("Draft Listings", []) if r.get("D", "").startswith("DRAFT-BSI-")]
check("97 native saved draft-only SKU suggestions exact", len(saved_draft_skus) == 97 and set(saved_draft_skus) == draft_skus)
action_ids = {e["action_id"] for e in json.loads((BASE / "NATIVE_ACTION_DRAFTS.json").read_text())["actions"]}
check("all7 action drafts saved in native view", {r.get("A") for r in sheets.get("Listing Actions", []) if r.get("A") in action_ids} == action_ids)
four = json.loads((BASE / "FOUR_LISTING_CORRECTIONS.json").read_text())["records"]
correction_expected = {(e["product_id"], field): value for e in four for field, value in e["accepted_working_specifications"].items()}
saved_corrections = {(r.get("B"), r.get("D")): r for r in sheets.get("Listing Corrections", []) if (r.get("B"), r.get("D")) in correction_expected}
check("24 native correction field rows exact population", set(saved_corrections) == set(correction_expected) and len(saved_corrections) == 24)
for key, value in correction_expected.items():
    check(f"correction accepted value preserved {key}", saved_corrections.get(key, {}).get("E") == value)
failures = [r for r in checks if not r["pass"]]
result = {
    "schema": "boldstone.A-independent-published-master-readback.v1",
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "status": ("PASS_STAGED_NATIVE_WORKBOOK" if staged else "PASS_PUBLISHED_MASTER_AND_NATIVE_WORKBOOK") if not failures else "FAIL",
    "publication_receipt": None if staged else pointer.get("publication_receipt"),
    "register": {"path": str(register_path), "sha256": hashlib.sha256(register_bytes).hexdigest()},
    "workbook": {"path": str(workbook_path), "sha256": hashlib.sha256(workbook_bytes).hexdigest()},
    "checks_passed": len(checks) - len(failures), "checks_total": len(checks),
    "new_sheets_option_rows": new_sheet_option_counts, "failures": failures, "checks": checks,
    "remote_execution_verified_or_claimed": False,
    "shared_master_writes_by_A": 0,
}
(OUT / ("STAGED_IMPORT_READBACK.json" if staged else "MASTER_IMPORT_READBACK.json")).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "checks"}, indent=2))
raise SystemExit(bool(failures))
