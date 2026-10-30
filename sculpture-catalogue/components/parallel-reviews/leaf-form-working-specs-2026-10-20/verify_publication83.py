"""Read the immutable batch83 workbook and write separate lane receipts."""
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
import datetime
import hashlib
import json
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

LANE = Path(__file__).resolve().parent
CAT = LANE.parents[2]
BASE = CAT / "components/reviews/workbook-refresh-2026-10-19"
DIGEST = "080536aa2867b5c3b330176eebf3f2c522ea827d6c05acd78a2750c4d07c2c79"
HISTORY = BASE / "history" / DIGEST
SNAPSHOT = BASE / "published-snapshots" / (DIGEST + ".xlsx.snapshot")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return {"path": str(path), "sha256": sha(path)}


def norm(value):
    return " ".join(value.split())


def linked_path(url):
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if path.startswith("/home"):
        path = path[5:]
        preview = parse_qs(parsed.query).get("preview")
        if preview:
            path += "/" + preview[0]
    elif path.startswith("/preview"):
        path = path[8:]
    return parsed.netloc, path


publication = read(HISTORY / "checkpoint-publication-receipt.json")
independent = read(HISTORY / "independent-file-verification.json")
final = read(HISTORY / "final-readback-batch83.json")
assert sha(SNAPSHOT) == DIGEST
assert publication["summary"]["workbook_sha256"] == DIGEST
assert publication["summary"]["included_owner_review_imports_through_batch"] == 83
assert independent["status"] == "PASS" and independent["check_count"] == 201
assert all(v == "PASS" for v in independent["checks"].values())
assert final["workbook_sha256"] == DIGEST
assert final["canonical_standing_working_policy_count"] == 1

ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
sheets = {}
native_count = 0
with zipfile.ZipFile(SNAPSHOT) as archive:
    strings = [
        "".join(e.itertext())
        for e in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("x:si", ns)
    ] if "xl/sharedStrings.xml" in archive.namelist() else []
    workbook_relations = {
        e.attrib["Id"]: e.attrib["Target"]
        for e in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    for sheet in workbook.findall("x:sheets/x:sheet", ns):
        target = workbook_relations[sheet.attrib[rid]]
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        tree = ET.fromstring(archive.read(path))
        native_elements = tree.findall("x:hyperlinks/x:hyperlink", ns)
        native_count += len(native_elements)
        if sheet.attrib["name"] not in ["Current Reviews", "Reviewed Specifications"]:
            continue
        relations_path = posixpath.join(posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels")
        relations = {
            e.attrib["Id"]: e.attrib["Target"]
            for e in ET.fromstring(archive.read(relations_path))
        } if relations_path in archive.namelist() else {}
        links = {e.attrib["ref"]: relations[e.attrib[rid]] for e in native_elements if rid in e.attrib}
        rows = []
        for row in tree.findall("x:sheetData/x:row", ns):
            cells = {}
            for cell in row.findall("x:c", ns):
                column = re.sub("[0-9]", "", cell.attrib["r"])
                value = cell.find("x:v", ns)
                if cell.attrib.get("t") == "s" and value is not None:
                    text = strings[int(value.text)]
                elif cell.attrib.get("t") == "inlineStr":
                    text = "".join(cell.find("x:is", ns).itertext())
                else:
                    text = value.text if value is not None else ""
                cells[column] = text
            rows.append({
                "row": int(row.attrib["r"]), "cells": cells,
                "hyperlinks": {col: links[col + row.attrib["r"]] for col in cells if col + row.attrib["r"] in links},
            })
        sheets[sheet.attrib["name"]] = rows
assert native_count == 4175

addendum = read(LANE / "CONTROL_MANIFEST_ADDENDUM.json")
assert all(sha(Path(x["path"])) == x["current_sha256"] for x in addendum["control_file_changes"])
scopes = [
    (
        CAT / "components/parallel-reviews/fountain-palm-mediterranean-white-working-specs-2026-10-20",
        "FOUNTAIN-MED-WHITE", 81, "owner-working-specs-keep/SPECIFICATION_APPROVAL.json",
    )
] + [
    (LANE / sub, vid, 83, "SPECIFICATION_APPROVAL.json")
    for sub, vid in [
        ("lf1-white", "LEAF-FORM-LF1-WHITE"),
        ("lf2-white", "LEAF-FORM-LF2-WHITE"),
        ("gold", "LEAF-FORM-GOLD"),
    ]
]
labels = {
    "dimensions": "Dimensions / depth", "weight": "Weight",
    "material_finish": "Material / finish", "fixing": "Fixing",
    "individual_price": "Individual price", "availability": "Availability",
}
prepared = []
for target, variant, batch, filename in scopes:
    source = read(target / filename)
    rows = [x for x in sheets["Current Reviews"] if x["cells"].get("C") == variant]
    specifications = [x for x in sheets["Reviewed Specifications"] if x["cells"].get("C") == variant]
    checks = {}

    def check(key, result):
        checks[key] = "PASS" if result else "FAIL"

    check("publication83_saved_hash_and_inclusion", publication["summary"]["included_owner_review_imports_through_batch"] >= batch)
    check("root_independent201_visual35_bound", independent["check_count"] == 201 and final["affected_previews_inspected"] == 35)
    check("one_current_row_six_unique_fields", len(rows) == 1 and len(specifications) == 6 and {x["cells"]["D"] for x in specifications} == set(labels.values()))
    current = rows[0]
    cells = current["cells"]
    check("name_and_six_acceptance_visible", cells["A"] == source["component_id"] and cells["B"] == source["canonical_name"] and cells["E"] == "Owner kept this name" and cells["F"].startswith("Six working specifications accepted"))
    check("primary_ids_native_links", cells["J"] == source["primary_file_id"] and cells["K"] == source["folder_id"] and linked_path(current["hyperlinks"]["H"]) == linked_path(source["image_link"]) and linked_path(current["hyperlinks"]["I"]) == linked_path(source["folder_link"]))
    for key, label in labels.items():
        row = next(x for x in specifications if x["cells"]["D"] == label)
        value = source["specifications"][key]
        saved = row["cells"]
        check(key + "_display_status_basis_ids_links",
              saved["E"].startswith(value["display"])
              and "Owner accepted working proposal; not physically verified" in saved["F"]
              and value["status"] in saved["F"]
              and norm(value["basis"]) in norm(saved["G"])
              and saved["J"] == source["primary_file_id"]
              and saved["K"] == source["folder_id"]
              and linked_path(row["hyperlinks"]["H"]) == linked_path(source["image_link"])
              and linked_path(row["hyperlinks"]["I"]) == linked_path(source["folder_link"]))
    context = source["context_images"]
    check("context_native_links_and_ids",
          linked_path(current["hyperlinks"]["P"]) == linked_path(context["image_url"])
          and linked_path(current["hyperlinks"]["Q"]) == linked_path(context["folder_url"])
          and context["representative_file_id"] in cells["O"]
          and context["representative_folder_id"] in cells["O"])
    check("context_availability_and_limits_visible", cells["N"].startswith("Available:") and norm(context["limitations"]) in norm(cells["O"]))
    check("one_canonical_policy_without_per_entry_replies", final["canonical_standing_working_policy_count"] == 1 and (batch == 81 or all("no individual reply recorded" in x["cells"]["F"] for x in specifications)))
    check("Leaf_six_sealed_controls_unchanged", all(sha(Path(x["path"])) == x["current_sha256"] for x in addendum["control_file_changes"]))
    failures = [key for key, value in checks.items() if value != "PASS"]
    print(variant, "FAILURES", failures)
    assert not failures
    prepared.append((target, {
        "schema": "boldstone.parallel-finish-workbook-readback.v1",
        "status": "PASS", "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "check_count": len(checks), "checks": checks,
        "component_id": source["component_id"], "size_finish_variant_id": variant,
        "workbook": str(CAT / publication["summary"]["workbook"]),
        "verified_immutable_workbook_snapshot": str(SNAPSHOT), "workbook_sha256": DIGEST,
        "published_through": 83, "approval_import_batch": batch,
        "publication_snapshot": ref(HISTORY / "checkpoint-publication-receipt.json"),
        "root_final_readback": ref(HISTORY / "final-readback-batch83.json"),
        "root_independent_validation": ref(HISTORY / "independent-file-verification.json"),
        "root_independent_check_count": 201, "native_hyperlink_count": native_count,
        "source_approval": ref(target / filename),
        "selected_saved_rows": {"Current Reviews": rows, "Reviewed Specifications": specifications},
        "sealed_controls_and_manifests_unchanged": True,
        "shared_master_writes_by_lane": 0, "remote_mutations": 0,
    }))
for target, result in prepared:
    output = target / "SPECIFICATION_WORKBOOK_READBACK.json"
    assert not output.exists()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"variant": result["size_finish_variant_id"], "checks": result["check_count"], "receipt": ref(output)}))
