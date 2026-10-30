"""Read a published immutable workbook without modifying shared records."""
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
import argparse
import datetime
import hashlib
import json
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

B = Path(__file__).resolve().parent
C = B.parents[2]
R = C / "components/reviews"
B96 = B.parent / "remaining-lane-b-working-specs-2026-10-20"
parser = argparse.ArgumentParser()
parser.add_argument("--workbook-sha256", required=True)
parser.add_argument("--minimum-batch", type=int, default=97)
parser.add_argument("--candidate", action="store_true", help="Check the exported bytes while publication/visual QA is pending.")
args = parser.parse_args()
digest = args.workbook_sha256
assert re.fullmatch("[0-9a-f]{64}", digest)
H = R / "workbook-refresh-2026-10-19/history" / digest
S = R / "workbook-refresh-2026-10-19/published-snapshots" / (digest + ".xlsx.snapshot")


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


def norm(s):
    return " ".join(str(s).replace("**", "").split())


def linked_path(url):
    p = urlparse(url)
    path = unquote(p.path)
    if path.startswith("/home"):
        path = path[5:]
        if parse_qs(p.query).get("preview"):
            path += "/" + parse_qs(p.query)["preview"][0]
    elif path.startswith("/preview"):
        path = path[8:]
    return p.netloc, path


def working_label(text, require_physical_boundary=False):
    value = str(text).lower()
    accepted = "working" in value and "accepted" in value and "need confirmation" not in value
    bounded = "not physically verified" in value or ("physical" in value and "unverified" in value)
    return accepted and (bounded or not require_physical_boundary)


checks = []


def check(name, result, detail=None):
    checks.append({"name": name, "status": "PASS" if result else "FAIL", "detail": detail})


publication = None
candidate_export_ref = None
if args.candidate:
    stage = R / "workbook-refresh-2026-10-19"
    independent_bytes = (stage / "independent-file-verification.json").read_bytes()
    export_bytes = (stage / "export-receipt.json").read_bytes()
    independent, exported = json.loads(independent_bytes), json.loads(export_bytes)
    assert independent["output_sha256"] == exported["output_sha256"] == digest
    blob = Path(exported["output"]).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == digest
    H = B / "candidate-snapshots" / digest
    H.mkdir(parents=True, exist_ok=True)
    S = H / "workbook.xlsx.snapshot"
    for path, data in [(S, blob), (H / "export-receipt.json", export_bytes),
                       (H / "independent-file-verification.json", independent_bytes)]:
        if path.exists():
            assert path.read_bytes() == data
        else:
            path.write_bytes(data)
    candidate_export_ref = ref(H / "export-receipt.json")
    expected_native_links = exported["native_hyperlink_count"]
    current_import = read(R / "specification_review_progress.json")["latest_parallel_import"]["batch"]
    check("Immutable candidate workbook hash", sha(S) == digest)
    check("Model imports ready for final publication", current_import >= args.minimum_batch)
    check("Coordinator saved-file QA; visual/publication not yet certified", independent["status"] == "PASS")
else:
    publication = read(H / "checkpoint-publication-receipt.json")
    independent = read(H / "independent-file-verification.json")
    expected_native_links = publication["summary"]["native_hyperlinks"]
    check("Immutable workbook hash", sha(S) == digest == publication["summary"]["workbook_sha256"])
    check("Remaining batches included", publication["summary"]["included_owner_review_imports_through_batch"] >= args.minimum_batch)
    check("Coordinator saved-file QA", publication["status"] == independent["status"] == "PASS")
check("B96 source seal unchanged", all(sha(r["path"]) == r["sha256"] for r in read(B96 / "SEALED_MANIFEST.json")["files"]))

ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
sheets = {}
native_count = 0
with zipfile.ZipFile(S) as archive:
    strings = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("x:si", ns)] if "xl/sharedStrings.xml" in archive.namelist() else []
    bookrels = {x.attrib["Id"]: x.attrib["Target"] for x in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    for sheet in book.findall("x:sheets/x:sheet", ns):
        target = bookrels[sheet.attrib[rid]]
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        xml = ET.fromstring(archive.read(path))
        elements = xml.findall("x:hyperlinks/x:hyperlink", ns)
        native_count += len(elements)
        if sheet.attrib["name"] not in ["Current Reviews", "Reviewed Specifications", "Photograph Gaps"]:
            continue
        relpath = posixpath.join(posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels")
        relations = {x.attrib["Id"]: x.attrib["Target"] for x in ET.fromstring(archive.read(relpath))} if relpath in archive.namelist() else {}
        links = {x.attrib["ref"]: relations[x.attrib[rid]] for x in elements if rid in x.attrib}
        rows = []
        for row in xml.findall("x:sheetData/x:row", ns):
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
            rows.append({"row": int(row.attrib["r"]), "cells": cells,
                         "hyperlinks": {col: links[col + row.attrib["r"]] for col in cells if col + row.attrib["r"] in links}})
        sheets[sheet.attrib["name"]] = rows
check("Native hyperlink total agrees with saved-file receipt", native_count == expected_native_links)
labels = {"dimensions": "Dimensions / depth", "weight": "Weight", "material_finish": "Material / finish",
          "fixing": "Fixing", "individual_price": "Individual price", "availability": "Availability"}
selected, failures = [], []
for item in read(B96 / "IMPORT_PACKAGE.json")["existing_scopes"]:
    key = item["scope_key"]
    decision = read(item["decision"]["path"])
    cid, scope = item["component_id"], item["variant"]
    current = [r for r in sheets["Current Reviews"] if r["cells"].get("A") == cid and r["cells"].get("C") == scope]
    fields = [r for r in sheets["Reviewed Specifications"] if r["cells"].get("A") == cid and r["cells"].get("C") == scope]
    check(key + ": one row and six groups", len(current) == 1 and len(fields) == 6 and {r["cells"].get("D") for r in fields} == set(labels.values()))
    if len(current) != 1 or len(fields) != 6:
        continue
    row = current[0]
    c = row["cells"]
    check(key + ": name and working acceptance", c["B"] == decision["canonical_name"] and c["E"] == "Owner kept this name" and working_label(c["F"]), c.get("F"))
    check(key + ": primary IDs and native links", c["J"] == decision["primary_file_id"] and c["K"] == decision["folder_id"] and
          linked_path(row["hyperlinks"].get("H", "")) == linked_path(decision["image_link"]) and
          linked_path(row["hyperlinks"].get("I", "")) == linked_path(decision["folder_link"]))
    for field, label in labels.items():
        r = next((r for r in fields if r["cells"].get("D") == label), None)
        if not r:
            continue
        v = decision["specifications"][field]
        cell = r["cells"]
        check(key + ": " + field + " displayed with working boundary",
              norm(cell["E"]).startswith(norm(v["display"])) and
              working_label(cell["F"], require_physical_boundary=True) and
              norm(v["basis"]) in norm(cell.get("G", "")) and cell["J"] == decision["primary_file_id"] and cell["K"] == decision["folder_id"] and
              linked_path(r["hyperlinks"].get("H", "")) == linked_path(decision["image_link"]) and
              linked_path(r["hyperlinks"].get("I", "")) == linked_path(decision["folder_link"]),
              {"display": cell["E"], "status": cell["F"]})
    context = decision["context_images"]
    if context["selected_context_available"]:
        check(key + ": context flag visible", c.get("N", "").lower().startswith("available"), c.get("N"))
        chosen = context["selected_context_images"]
        if chosen:
            check(key + ": selected context native links", linked_path(row["hyperlinks"].get("P", "")) == linked_path(chosen[0]["image_url"]) and
                  linked_path(row["hyperlinks"].get("Q", "")) == linked_path(chosen[0]["folder_url"]))
    check(key + ": contextual observation retained", norm(context["visual_observation"]) in norm(c.get("O", "")), c.get("O"))
    if key == "UGR-G310|SOUNDWAVE-WHITE-G310003":
        check(key + ": resolved approval question removed", "unapproved" not in c.get("L", "").lower())
    if key == "BC-BONE-WATER|BASE":
        check(key + ": owner working size not reasked", "size/version confirmation" not in c.get("L", "").lower())
    selected.append({"scope_key": key, "current": current, "specifications": fields})
reference_rows = []
for cid in ["BC-PORTMAN-1", "BC-MCP-4"]:
    rows = [r for r in sheets["Current Reviews"] if r["cells"].get("A") == cid and r["cells"].get("C") == "BASE"]
    check(cid + "|BASE: terminal reference row present", len(rows) == 1)
    if len(rows) == 1:
        state = rows[0]["cells"].get("F", "").lower()
        check(cid + "|BASE: no pending six-field review", any(word in state for word in ["reference", "heading", "header"]) and
              "need confirmation" not in state and "pending" not in state, state)
        reference_rows.append(rows[0])
output = B / (("CANDIDATE_WORKBOOK_READBACK_" if args.candidate else "WORKBOOK_READBACK_") + digest[:16] + ".json")
assert not output.exists()
failed = [c for c in checks if c["status"] != "PASS"]
result = {
    "schema": "boldstone.remaining-batch-independent-publication-readback.v1",
    "status": "PASS" if not failed else "FAIL",
    "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "workbook_sha256": digest, "immutable_snapshot": str(S),
    "publication": ref(H / "checkpoint-publication-receipt.json") if publication else None,
    "candidate_only": args.candidate, "publication_verified": not args.candidate,
    "candidate_export": candidate_export_ref,
    "coordinator_saved_file_verification": ref(H / "independent-file-verification.json"),
    "minimum_import_batch": args.minimum_batch, "scope_count": 40, "working_field_groups": 240,
    "checks_passed": len(checks) - len(failed), "checks_failed": len(failed),
    "checks": checks, "selected_rows": selected, "terminal_reference_rows": reference_rows,
    "shared_master_writes_by_lane": 0, "remote_mutations": 0,
}
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "checks_passed": result["checks_passed"],
                  "checks_failed": len(failed), "failed_names": [x["name"] for x in failed],
                  "receipt": ref(output)}))
