"""Attach native links (a missing authoring feature), then independently read XLSX XML."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import posixpath
import zipfile
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
read = lambda name: json.loads((HERE / name).read_text())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
receipt = read("export-receipt.json")
book = Path(receipt["output"])
assert digest(book) == receipt["output_sha256"]
graph = read("canonical-products.json")
assert digest(HERE / "canonical-products.json") == receipt["canonical_source_sha256"]
expected, plan = read("expected-workbook.json"), read("native-hyperlinks.json")
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
qn = lambda ns, tag: "{" + ns + "}" + tag
with zipfile.ZipFile(book) as z:
    files = {i.filename: (i, z.read(i.filename)) for i in z.infolist()}
workbook = ET.fromstring(files["xl/workbook.xml"][1])
relations = {e.get("Id"): e.get("Target") for e in ET.fromstring(files["xl/_rels/workbook.xml.rels"][1])}
sheet_files = {}
for sheet in workbook.find(qn(S, "sheets")):
    target = relations[sheet.get(qn(R, "id"))]
    sheet_files[sheet.get("name")] = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
by_sheet = defaultdict(list)
for item in plan:
    assert item["target"].startswith(("https://", "#"))
    by_sheet[item["sheet"]].append(item)
assert len({(p["sheet"], p["cell"]) for p in plan}) == len(plan)
replacements = {}
late = {"printOptions", "pageMargins", "pageSetup", "headerFooter", "rowBreaks", "colBreaks", "customProperties", "cellWatches", "ignoredErrors", "smartTags", "drawing", "legacyDrawing", "legacyDrawingHF", "picture", "oleObjects", "controls", "webPublishItems", "tableParts", "extLst"}
for name, items in by_sheet.items():
    path = sheet_files[name]
    root = ET.fromstring(files[path][1])
    assert root.find(qn(S, "hyperlinks")) is None
    links = ET.Element(qn(S, "hyperlinks"))
    index = next((i for i, child in enumerate(root) if child.tag.split("}")[-1] in late), len(root))
    root.insert(index, links)
    rel_path = posixpath.join(posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels")
    rel_root = ET.fromstring(files[rel_path][1]) if rel_path in files else ET.Element(qn(P, "Relationships"))
    existing_ids = {e.get("Id") for e in rel_root}
    for i, item in enumerate(items, 1):
        link = ET.SubElement(links, qn(S, "hyperlink"), ref=item["cell"], display=item["label"])
        if item["target"].startswith("#"):
            link.set("location", item["target"][1:])
        else:
            rid = "rIdIndividualProductLink" + str(i)
            assert rid not in existing_ids
            link.set(qn(R, "id"), rid)
            ET.SubElement(rel_root, qn(P, "Relationship"), Id=rid, Type=R + "/hyperlink", Target=item["target"], TargetMode="External")
    replacements[path] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if len(rel_root):
        replacements[rel_path] = ET.tostring(rel_root, encoding="utf-8", xml_declaration=True)
temp = book.with_suffix(".links.tmp")
with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for name, (info, content) in files.items():
        z.writestr(info, replacements.pop(name, content))
    for name, content in replacements.items():
        z.writestr(name, content)
temp.replace(book)

# Read the saved bytes independently of artifact-tool and of its in-memory model.
checks = 0
failures = []
def check(test, label):
    global checks
    checks += 1
    if not test:
        failures.append(label)

def col(n):
    value = ""
    while n:
        n, rem = divmod(n - 1, 26)
        value = chr(65 + rem) + value
    return value

with zipfile.ZipFile(book) as z:
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        strings = ["".join(e.itertext()) for e in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    cell_maps = {}
    formula_maps = {}
    for name, path in sheet_files.items():
        tree = ET.fromstring(z.read(path))
        cells, formulas = {}, {}
        for c in tree.iter(qn(S, "c")):
            typ, address = c.get("t"), c.get("r")
            value_node = c.find(qn(S, "v"))
            v = value_node.text if value_node is not None else None
            if typ == "s":
                value = strings[int(v)] if v is not None else ""
            elif typ == "inlineStr":
                value = "".join(c.find(qn(S, "is")).itertext())
            elif typ == "str":
                value = v or ""
            elif typ == "b":
                value = v == "1"
            elif typ == "e":
                value = v
                failures.append("Formula/cell error: " + name + "!" + address + "=" + str(v))
            else:
                value = float(v) if v is not None and v != "" else ""
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
            cells[address] = value
            f = c.find(qn(S, "f"))
            if f is not None:
                formulas[address] = f.text
        cell_maps[name], formula_maps[name] = cells, formulas
        view = expected[name]
        for j, header in enumerate(view["headers"], 1):
            check(cells.get(col(j) + "6", "") == header, name + " header " + str(j))
        for i, row in enumerate(view["rows"], 7):
            for j, value in enumerate(row, 1):
                check(cells.get(col(j) + str(i), "") == value, name + "!" + col(j) + str(i))
        pane = tree.find(".//" + qn(S, "pane"))
        check(pane is not None and pane.get("ySplit") == "6" and pane.get("xSplit") == "2", name + " frozen headings and IDs")
        rel_path = posixpath.join(posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels")
        relations = {e.get("Id"): e for e in ET.fromstring(z.read(rel_path))} if rel_path in z.namelist() else {}
        actual_links = {}
        for h in tree.findall(".//" + qn(S, "hyperlink")):
            actual_links[h.get("ref")] = "#" + h.get("location") if h.get("location") else relations[h.get(qn(R, "id"))].get("Target")
        check(len(actual_links) == len(by_sheet[name]), name + " hyperlink population")
        for item in by_sheet[name]:
            check(actual_links.get(item["cell"]) == item["target"], name + " link " + item["cell"])
        table_parts = tree.find(qn(S, "tableParts"))
        check(table_parts is not None and len(table_parts) == 1, name + " filter table")
    for address, value in {"B4": 173, "D4": 174, "F4": 173, "H4": len(graph["source_candidates"]) + len(graph.get("additional_source_candidates", []))}.items():
        check(cell_maps["Products"].get(address) == value, "Summary recalculation " + address)
        check(address in formula_maps["Products"], "Summary is a formula " + address)
    check(len(formula_maps["Products"]) == 177, "173 six-field formulas plus four summary formulas")

base_manifest = read("input-manifest.json")
for item in base_manifest["sources"]:
    check(digest(Path(item["source"])) == item["sha256"], "Original source unchanged " + item["source"])
    check(digest(Path(item["snapshot"])) == item["sha256"], "Input snapshot unchanged " + item["snapshot"])
check(digest(Path(base_manifest["baseline_workbook"])) == base_manifest["baseline_workbook_sha256"], "Original workbook unchanged")
check(len(graph["source_offer_coverage"]) == 81, "All81 source offers present")
check(len(graph["source_configuration_coverage"]) == 199, "All199 source configurations present")
check(len({o["offer_ref"] for o in graph["source_offer_coverage"]}) == 81, "Unique offer IDs")
check(len({c["configuration_id"] for c in graph["source_configuration_coverage"]}) == 199, "Unique configuration IDs")
valid = {p["product_id"] for p in graph["products"]} | {r["reference_id"] for r in graph["references"]} | {c["candidate_id"] for c in graph["source_candidates"]}
for alias, entry in graph.get("reference_aliases", {}).items():
    check(entry["target_reference_id"] in valid, "Reference alias resolves " + alias)
valid |= set(graph.get("reference_aliases", {}))
for source in [*graph["scope_reconciliation"], *graph["historical_alias_reconciliation"]]:
    check(bool(source["targets"]) and set(source["targets"]) <= valid, "No dangling source target " + source["source_scope"])
for source in [*graph["source_offer_coverage"], *graph["source_configuration_coverage"]]:
    for field in ["exact_supported_target_ids", "covered_family_product_ids", "source_candidate_target_ids", "reference_target_ids"]:
        check(set(source.get(field, [])) <= valid, "No dangling coverage target " + field + " " + source.get("offer_ref", source.get("configuration_id", "")))

result = {"status": "PASS" if not failures else "FAIL", "checked_utc": datetime.now(timezone.utc).isoformat(),
          "workbook": str(book), "workbook_sha256": digest(book), "canonical_products_sha256": digest(HERE / "canonical-products.json"),
          "independent_checks": checks, "native_hyperlinks": len(plan), "sheet_rows": {k:len(v["rows"]) for k,v in expected.items()},
          "all_original_inputs_and_workbook_unchanged": not any("unchanged" in f for f in failures),
          "source_offer_coverage": dict(Counter(o["canonical_graph_coverage_state"] for o in graph["source_offer_coverage"])),
          "source_configuration_coverage": dict(Counter(c["canonical_graph_coverage_state"] for c in graph["source_configuration_coverage"])),
          "remote_reads": 0, "remote_writes": 0, "failures": failures}
(HERE / "independent-file-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
receipt.update(status="PASS_SAVED_FILE_READBACK" if not failures else "FAIL_SAVED_FILE_READBACK", output_sha256=digest(book), native_hyperlinks_written=len(plan), independent_checks=checks)
(HERE / "export-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
assert not failures, failures[:10]
