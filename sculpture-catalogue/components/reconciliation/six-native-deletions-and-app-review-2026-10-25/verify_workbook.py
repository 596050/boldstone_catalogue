"""Independently compare v4 native XML with all 22 retained source sheets."""
from pathlib import Path
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import xml.etree.ElementTree as ET

H = Path(__file__).resolve().parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
module_path = H.parent / 'acanthus-native-availability-2026-10-25/verify_workbook.py'
spec = importlib.util.spec_from_file_location('native_xlsx_reader', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Book = module.Book
arg = argparse.ArgumentParser()
arg.add_argument('--output', required=True, type=Path)
arg.add_argument('--metadata-allowlist', required=True, type=Path)
a = arg.parse_args()
packet = read(H / 'workbook-cutoff-packet.json')
overlay = read(packet['overlay_path'])
source = Path(packet['baseline_workbook'])
assert sha(source) == packet['baseline_workbook_sha256']
assert a.output.resolve() == Path(packet['output_workbook']).resolve()
before, after = Book(source), Book(a.output)
old_names, new_names = list(before.sheets), list(after.sheets)
errors, changes, link_changes = [], [], []
new_cells = new_links = checked = 0
if old_names != new_names or len(new_names) != 23:
    errors.append('Expected same 23 sheets in same order')
source_sheets = [n for n in old_names if n != 'Native Availability']
assert len(source_sheets) == 22
for name in source_sheets:
    bc, bl = before.sheet(name)
    ac, al = after.sheet(name)
    for ref, value in bc.items():
        checked += 1
        if ac.get(ref) != value:
            changes.append({'sheet': name, 'cell': ref, 'before': list(value), 'after': list(ac[ref]) if ref in ac else None})
    for ref, value in bl.items():
        checked += 1
        if al.get(ref) != value:
            link_changes.append({'sheet': name, 'cell': ref, 'before': value, 'after': al.get(ref)})
    new_cells += len(set(ac) - set(bc))
    new_links += len(set(al) - set(bl))
allowlist = read(a.metadata_allowlist)
assert isinstance(allowlist, list)
allowed_coordinates = {('Wall Sculptures', 'A6'), ('Wall Sculptures', 'AC9'), ('Products', 'AA100'), ('Overview', 'C12'), ('Guide and sources', 'B18')}
for row in allowlist:
    if (row['sheet'], row['cell']) not in allowed_coordinates or row['before'][0] != 'text' or row['after'][0] != 'text':
        errors.append('Metadata allowlist exceeds availability-only text scope')
unexpected = [r for r in changes if r not in allowlist]
unused = [r for r in allowlist if r not in changes]
if unexpected or unused:
    errors.append('Saved metadata differences do not exactly match reviewed delta')
if link_changes or new_links:
    errors.append('Existing source hyperlinks changed or new source links added')
if new_cells:
    errors.append('New cells in retained source sheets')
native, links = after.sheet('Native Availability')
native_text = {v[1] for v in native.values() if v[0] == 'text'}
for record in overlay['rows']:
    for key in ['file_id', 'revision_at_deletion', 'folder_id']:
        if record[key] not in native_text:
            errors.append('Missing native deletion evidence: ' + record['file_id'] + ' / ' + key)
for record in overlay['remaining_verified_files']:
    meta = record['metadata']
    for key in ['id', 'rev']:
        if meta[key] not in native_text:
            errors.append('Missing surviving native reference: ' + meta['id'] + ' / ' + key)
ns = module.M
native_xml = ET.fromstring(after.zip.read(after.sheets['Native Availability']))
raw_cells = {c.attrib['r']: c for c in native_xml.iter(ns + 'c')}
summary = {}
for ref, expected in {'B6': 6360, 'B7': 6, 'B8': 6354}.items():
    cached = raw_cells[ref].find(ns + 'v')
    value = Decimal(cached.text) if cached is not None else None
    summary[ref] = str(value)
    if value != Decimal(expected):
        errors.append('Native summary cached value incorrect: ' + ref)
if native['B7'] != ('formula', 'COUNTA(F13:F18)') or native['B8'] != ('formula', 'B6-B7'):
    errors.append('Native summary formulas do not bind the six deletion rows')
out = {'status': 'PASS_V4_SIX_FILE_NATIVE_AVAILABILITY_WORKBOOK' if not errors else 'NEEDS_REVIEW_V4_WORKBOOK',
       'source_workbook': str(source), 'source_workbook_sha256': sha(source),
       'output_workbook': str(a.output.resolve()), 'output_workbook_sha256': sha(a.output),
       'overlay_sha256': sha(packet['overlay_path']), 'review_event_cutoff': overlay['review_event_cutoff'],
       'last_confirmed_native_event': overlay['last_confirmed_native_event'],
       'source_sheet_count': len(old_names), 'output_sheet_count': len(new_names),
       'retained_source_sheets_checked': 22, 'source_cells_and_links_checked': checked,
       'existing_cell_value_changes': changes, 'approved_metadata_text_changes': len(allowlist),
       'source_or_specification_cell_changes': len(unexpected), 'metadata_allowlist_sha256': sha(a.metadata_allowlist),
       'existing_hyperlink_changes': link_changes, 'new_cells_in_retained_sheets': new_cells,
       'new_hyperlinks_in_retained_sheets': new_links,
       'output_hyperlinks': sum(len(after.sheet(n)[1]) for n in new_names),
       'native_deletion_ids_and_revisions_present': not any('Missing native deletion' in e for e in errors),
       'surviving_references_present': not any('Missing surviving' in e for e in errors),
       'native_summary_cached_values': summary,
       'errors': errors, 'canonical_or_review_state_writes': 0, 'native_calls': 0}
before.close()
after.close()
(H / 'workbook-independent-validation.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in out.items() if k not in ['existing_cell_value_changes', 'existing_hyperlink_changes']}, ensure_ascii=False, indent=2))
raise SystemExit(0 if not errors else 1)
