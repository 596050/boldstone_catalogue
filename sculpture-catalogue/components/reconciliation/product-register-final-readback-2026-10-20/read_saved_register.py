"""Check saved workbook cells, cached count formulas and native link targets."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
import hashlib
import json
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--workbook", required=True)
parser.add_argument("--workbook-sha256", required=True)
parser.add_argument("--graph", required=True)
parser.add_argument("--graph-sha256", required=True)
parser.add_argument("--expected", required=True)
parser.add_argument("--forbidden-prefixes-json")
args = parser.parse_args()
workbook = Path(args.workbook).resolve()
graph_path = Path(args.graph).resolve()
assert sha(workbook) == args.workbook_sha256
assert sha(graph_path) == args.graph_sha256
g = read(graph_path)
expected = read(args.expected)
checks = {}


def check(name, value):
    checks[name] = bool(value)


def col(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def resolve(base, target):
    return target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(base), target))


with zipfile.ZipFile(workbook) as archive:
    strings = []
    if "xl/sharedStrings.xml" in archive.namelist():
        for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS):
            strings.append("".join(t.text or "" for t in si.findall(".//s:t", NS)))
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    book_rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
    sheets = {}
    all_links = {}
    error_cells = []
    formula_cells = {}
    for sheet in book.findall("s:sheets/s:sheet", NS):
        name = sheet.attrib["name"]
        part = resolve("xl/workbook.xml", book_rels[sheet.attrib[REL]])
        tree = ET.fromstring(archive.read(part))
        cells = {}
        for c in tree.findall(".//s:sheetData/s:row/s:c", NS):
            ref = c.attrib["r"]
            v = c.find("s:v", NS)
            raw = v.text if v is not None else None
            kind = c.attrib.get("t", "")
            if kind == "s":
                value = strings[int(raw)] if raw is not None else ""
            elif kind == "inlineStr":
                value = "".join(t.text or "" for t in c.findall(".//s:t", NS))
            elif kind in ["str", "e"]:
                value = raw or ""
            elif raw is None:
                value = ""
            else:
                try:
                    value = float(raw)
                    if value.is_integer():
                        value = int(value)
                except ValueError:
                    value = raw
            cells[ref] = value
            if kind == "e":
                error_cells.append({"sheet": name, "cell": ref, "value": value})
            f = c.find("s:f", NS)
            if f is not None:
                formula_cells[(name, ref)] = f.text or ""
        rel_path = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
        rels = {}
        if rel_path in archive.namelist():
            rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(archive.read(rel_path))}
        for h in tree.findall("s:hyperlinks/s:hyperlink", NS):
            ref = h.attrib["ref"]
            target = rels.get(h.attrib.get(REL), h.attrib.get("location", ""))
            all_links[(name, ref)] = target
        sheets[name] = cells

check("Six requested worksheets present", set(sheets) == {"Components", "Listing Options", "Sets and Context", "Aliases", "References and Gaps", "Source Mapping"})
check("No cached Excel error cells", not error_cells)
check("No unsupported HYPERLINK formulas remain", all("HYPERLINK(" not in f.upper() for f in formula_cells.values()))

for name, sheet in expected["sheets"].items():
    cells = sheets[name]
    first = sheet["first"]
    for j, header in enumerate(sheet["headers"], 1):
        check("Header " + name + ":" + col(j), cells.get(col(j) + str(first - 1), "") == header)
    # Export fidelity, in addition to direct graph checks below.
    for i, row in enumerate(sheet["rows"], first):
        for j, target in enumerate(row, 1):
            ref = col(j) + str(i)
            if (name, ref) in formula_cells:
                continue
            check("Saved value " + name + ":" + ref, cells.get(ref, "") == ("" if target is None else target))

for item in expected["formulas"]:
    key = (item["sheet"], item["cell"])
    actual_formula = formula_cells.get(key, "")
    check("Saved count formula " + ":".join(key), actual_formula.lstrip("=") == item["formula"].lstrip("="))
    check("Cached count value " + ":".join(key), sheets[key[0]].get(key[1]) == item["expected"])
check("Only the intended count formulas remain", len(formula_cells) == len(expected["formulas"]))

expected_links = {(x["sheet"], x["cell"]): x["target"] for x in expected["hyperlinks"]}
check("All native hyperlink cells match the export link manifest", set(all_links) == set(expected_links))
for key, target in expected_links.items():
    check("Native link " + ":".join(key), all_links.get(key) == target)
    check("Native link label is not an error " + ":".join(key), bool(sheets[key[0]].get(key[1])) and not str(sheets[key[0]].get(key[1])).startswith("#"))

component_cells = sheets["Components"]
for i, item in enumerate(g["components"], 10):
    check("Component identity and family " + item["component_id"], component_cells.get("A" + str(i)) == item["component_id"] and component_cells.get("B" + str(i)) == item["name"] and component_cells.get("C" + str(i)) == item["family"])
    check("Component option count from current graph " + item["component_id"], component_cells.get("D" + str(i)) == item["option_count"])
    check("Component current media references " + item["component_id"], component_cells.get("H" + str(i)) == item["file_id"] and component_cells.get("I" + str(i)) == item["folder_id"] and all_links.get(("Components", "F" + str(i))) == item["image_url"] and all_links.get(("Components", "G" + str(i))) == item["folder_url"])

option_cells = sheets["Listing Options"]
for i, item in enumerate(g["options"], 10):
    pid = item["product_id"]
    check("Option identity retained " + pid, option_cells.get("B" + str(i)) == pid and option_cells.get("C" + str(i)) == item["name"])
    check("Option current dimensions and offered fixings " + pid, option_cells.get("G" + str(i)) == item["specifications"]["Dimensions / depth"]["display"] and option_cells.get("I" + str(i)) == " or ".join(item["offered_fixing_choices"]))
    if item["file_id"]:
        check("Option current file and folder links " + pid, option_cells.get("L" + str(i)) == item["file_id"] and option_cells.get("M" + str(i)) == item["folder_id"] and all_links.get(("Listing Options", "J" + str(i))) == item["image_url"] and all_links.get(("Listing Options", "K" + str(i))) == item["folder_url"])
    else:
        check("Unbound source option visibly has no invented image " + pid, item.get("unbound_size_option") and option_cells.get("L" + str(i)) == "Unbound" and option_cells.get("M" + str(i)) == "Unbound" and ("Listing Options", "J" + str(i)) not in all_links)
    check("Option source scopes retained " + pid, option_cells.get("N" + str(i)) == "\n".join(item["source_scopes"]))

component_ids = [component_cells.get("A" + str(i)) for i in range(10, 10 + len(g["components"]))]
option_ids = [option_cells.get("B" + str(i)) for i in range(10, 10 + len(g["options"]))]
check("Saved component and option IDs are unique", len(set(component_ids)) == len(g["components"]) and len(set(option_ids)) == len(g["options"]))
check("Headline component count is data-derived", component_cells.get("B4") == len(component_ids))
check("Headline option count is data-derived", component_cells.get("F4") == len(option_ids))
check("Headline component-option subtotal matches reciprocity", component_cells.get("D4") == sum(c["option_count"] for c in g["components"]))
check("Headline unbound source option count stays separate", component_cells.get("H4") == sum(bool(o.get("unbound_size_option")) for o in g["options"]))

source_cells = sheets["Source Mapping"]
increments = [source_cells.get("L" + str(i), 0) for i in range(10, 10 + len(g["source_review_reconciliation"]) + len(g["source_component_dispositions"]))]
check("Source review increments plus supplemental Wall Circle equal option records", sum(increments) + g["summary"]["wall_circle_kept_visual_options"] == len(option_ids))
check("Overlapping source component rows add zero options", all(x == 0 for x in increments[len(g["source_review_reconciliation"]):]))

forbidden = ["/Moon Crater Phase/Moon Crater Phase 4/"]
if args.forbidden_prefixes_json:
    forbidden.extend(read(args.forbidden_prefixes_json))
stale = [{"sheet": key[0], "cell": key[1], "target": target} for key, target in all_links.items() if any(re.search(re.escape(prefix.rstrip("/")) + r"(/|[?#]|$)", unquote(target)) for prefix in forbidden)]
check("No visible native links use superseded folder prefixes", not stale)
check("Graph and workbook stayed unchanged throughout readback", sha(workbook) == args.workbook_sha256 and sha(graph_path) == args.graph_sha256)

result = {
    "schema": "boldstone.saved-product-register-independent-readback.v1",
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if all(checks.values()) else "FAIL",
    "workbook": str(workbook), "workbook_sha256": args.workbook_sha256,
    "graph": str(graph_path), "graph_sha256": args.graph_sha256,
    "expected_manifest": str(Path(args.expected).resolve()), "expected_manifest_sha256": sha(args.expected),
    "checks_passed": sum(checks.values()), "checks_failed": sum(not x for x in checks.values()),
    "failed_checks": [k for k, v in checks.items() if not v],
    "native_hyperlinks": len(all_links), "count_formulas": len(formula_cells),
    "error_cells": error_cells, "superseded_path_links": stale,
    "sheet_data_rows": {k: len(v["rows"]) for k, v in expected["sheets"].items()},
    "headline_counts": {k: component_cells.get(k) for k in ["B4", "D4", "F4", "H4"]},
    "shared_master_writes": 0, "remote_reads": 0, "remote_writes": 0,
    "checks": {k: "PASS" if v else "FAIL" for k, v in checks.items()},
}
out = HERE / ("SAVED_REGISTER_READBACK_" + args.workbook_sha256[:16] + ".json")
assert not out.exists(), out
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"path": str(out), "sha256": sha(out), "status": result["status"], "checks_passed": result["checks_passed"], "failed": result["failed_checks"][:20], "native_links": len(all_links), "formula_count": len(formula_cells), "stale_path_count": len(stale)}))
