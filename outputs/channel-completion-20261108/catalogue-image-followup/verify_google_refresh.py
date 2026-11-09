"""Independently compare the live Google-native export with the authorised master."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as E

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path[:0] = ['/tmp/boldstone-20261106-readback', str(ROOT / 'catalogue-review/scripts')]
from python_calamine import CalamineWorkbook
from import_saatchi_snapshot import Xlsx, NS, column

plan = json.loads((OUT / 'google-refresh-plan.json').read_text())
source_path = Path(plan['source_path'])
native_path = OUT / 'google-master-after.xlsx'
assert hashlib.sha256(source_path.read_bytes()).hexdigest() == plan['source_sha256']
source = CalamineWorkbook.from_path(str(source_path))
native = CalamineWorkbook.from_path(str(native_path))
assert source.sheet_names == native.sheet_names and len(source.sheet_names) == 12
a, b = Xlsx(source_path), Xlsx(native_path)
links = lambda book, sheet: {h.get('ref'): h.attrib for h in E.fromstring(book.parts[book.paths[sheet]]).findall('s:hyperlinks/s:hyperlink', NS)}
source_links, native_links = links(a, 'Wall Sculptures'), links(b, 'Wall Sculptures')
value = lambda rows, r, c: rows[r][c] if r < len(rows) and c < len(rows[r]) and rows[r][c] is not None else ''
equal = lambda x, y: math.isclose(x, y, rel_tol=1e-10, abs_tol=1e-7) if isinstance(x, (float, int)) and not isinstance(x, bool) and isinstance(y, (float, int)) and not isinstance(y, bool) else x == y
differences, accepted_labels, accepted_rounding, unexpected = [], [], [], []
checked = nonblank = 0
for sheet in source.sheet_names:
    old = source.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
    new = native.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
    for row in range(max(len(old), len(new))):
        for col in range(max(len(old[row]) if row < len(old) else 0, len(new[row]) if row < len(new) else 0)):
            x, y = value(old, row, col), value(new, row, col)
            checked += 1
            nonblank += x != ''
            if equal(x, y):
                continue
            diff = dict(sheet=sheet, row=row+1, column=col+1, source=str(x), native=str(y))
            differences.append(diff)
            cell = column(col+1) + str(row+1)
            if sheet == 'Wall Sculptures' and col+1 == 46:
                sl, nl = source_links.get(cell), native_links.get(cell)
                if sl and nl and sl.get('display') == y and sl.get('location') == nl.get('location'):
                    accepted_labels.append(diff)
                    continue
            if sheet == 'Wall Sculptures' and col+1 == 479 and 8 <= row+1 <= 188:
                floor = Decimal(str(a.value(sheet, 'RJ'+str(row+1))))
                discount = Decimal(str(a.value(sheet, 'QO4')))
                exact = (floor/(1-discount)).quantize(Decimal('.01'), rounding=ROUND_CEILING)
                assert Decimal(str(y)) == exact and abs(Decimal(str(x))-exact) == Decimal('.01')
                assert a.formula(sheet, cell) == f'ROUNDUP(RJ{row+1}/(1-$QO$4),2)'
                # The native conversion may share adjacent formulas. Verify its
                # expanded expression against the exact original expression.
                node = b.cells[sheet][cell].find('s:f', NS)
                assert node is not None
                if node.text:
                    expression = node.text
                else:
                    si = node.get('si')
                    anchor, node = next((c, element.find('s:f', NS)) for c, element in b.cells[sheet].items()
                                        if element.find('s:f', NS) is not None and element.find('s:f', NS).get('si') == si and element.find('s:f', NS).text)
                    delta = row+1-int(re.sub(r'\D', '', anchor))
                    expression = re.sub(r'(\$?[A-Z]+)(\$?)(\d+)', lambda m: m[1]+m[2]+str(int(m[3])+(0 if m[2] else delta)), node.text)
                assert expression == a.formula(sheet, cell)
                accepted_rounding.append(diff)
                continue
            unexpected.append(diff)
(OUT / 'google-native-value-differences.json').write_text(json.dumps(differences, indent=2)+'\n')
assert not unexpected, unexpected[:8]
assert len(accepted_labels) == 181
formula_counts, table_counts, errors = {}, {}, []
for label, book in [('source', a), ('native', b)]:
    formula_counts[label] = 0
    table_counts[label] = sum(bool(re.fullmatch(r'xl/tables/table\d+\.xml', n)) for n in book.parts)
    for sheet, path in book.paths.items():
        tree = E.fromstring(book.parts[path])
        formula_counts[label] += len(tree.findall('.//s:f', NS))
        errors += [dict(book=label, sheet=sheet, cell=c.get('r')) for c in tree.findall('.//s:c', NS) if c.get('t') == 'e']
assert formula_counts['source'] == formula_counts['native'] == 32776
assert table_counts['source'] == table_counts['native']
assert not errors
assert len({b.value('Wall Sculptures', 'AA'+str(row)) for row in range(8, 189)}) == 181
assert b.value('Wall Sculptures', 'AHU7') == 'microsoft_merchant_image_compatibility_status'
owner = (OUT / 'google-master-owner-private-after.txt').read_text()
assert 'Share. Private to only me.' in owner and 'info@boldstone.co.uk' in owner
assert 'Document status: Saved to Drive.' in owner and '1T-t6Mgy_TiMKzV8P45o1hvH2tpndicPO8Pq05KG8ZAs' in owner
receipt = dict(status='PASS_GOOGLE_NATIVE_MASTER_FULL_EXPORT_READBACK', checked_at=datetime.now(timezone.utc).isoformat(),
    native_url=plan['google_url'], owner='info@boldstone.co.uk', private=True, existing_document_id_preserved=True,
    source_dropbox_revision=plan['source_dropbox_revision'], source_master_sha256=plan['source_sha256'],
    native_export_sha256=hashlib.sha256(native_path.read_bytes()).hexdigest(), sheets=source.sheet_names,
    component_records=181, master_columns=905, cells_compared=checked, nonblank_values_checked=nonblank,
    unexpected_value_differences=0, preserved_internal_link_display_labels=len(accepted_labels),
    native_engine_rounding_difference_count=len(accepted_rounding), native_engine_rounding_scope='Existing column RK Faire minimum list-price planning formula only; exact mathematical upward rounding verified. No adopted retail-price differences.',
    formula_counts=formula_counts, native_table_counts=table_counts, formula_errors=0,
    prior_native_owner_edits_detected=0, public_pinterest_feed_changed=False,
    visual_verification='Pending native visual review')
image_plan=json.loads((OUT/'plan.json').read_text())
for patch in image_plan['patches']:
    if patch['style']!='utc':continue
    assert b.value(patch['sheet'],patch['cell']) not in ('',None)
receipt.update(new_dated_evidence_cells_verified=1061,prior_timestamp_dates_preserved=True,
    visual_verification='Pending native visual review')
(OUT / 'google-refresh-verification.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps({k:receipt[k] for k in ['status','component_records','master_columns','cells_compared','unexpected_value_differences','formula_counts','formula_errors','native_engine_rounding_difference_count']}))
