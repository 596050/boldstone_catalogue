"""Independently read all saved changes and check every qualified margin."""
from pathlib import Path
import hashlib
import json
import math
import sys

sys.path.insert(0, '/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook

OUT = Path(__file__).parent
plan = json.loads((OUT / 'plan.json').read_text())
book = CalamineWorkbook.from_path(str(OUT / 'catalogue_wall_sculptures.xlsx'))
tables = {name: book.get_sheet_by_name(name).to_python(skip_empty_area=False) for name in {p['sheet'] for p in plan['patches']}}


def index(cell):
    col = 0
    for c in ''.join(c for c in cell if c.isalpha()):
        col = col * 26 + ord(c) - 64
    return int(''.join(c for c in cell if c.isdigit())) - 1, col - 1


def read(sheet, cell):
    r, c = index(cell)
    return tables[sheet][r][c]


for p in plan['patches']:
    actual = read(p['sheet'], p['cell'])
    expected = p['value']
    same = math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-6) if isinstance(expected, (int, float)) and not isinstance(expected, bool) else actual == expected
    assert same, (p['sheet'], p['cell'], actual, expected)

margins = []
held = []
headers = plan['headers']
for record in plan['records']:
    row = str(record['row'])
    value = lambda name: read('Wall Sculptures', headers[name] + row)
    assert value('Product ID') == record['catalogue_id']
    assert value('SKU') == record['sku']
    assert value('Labour cost') == 0
    if record['status'] != 'PLANNING_ESTIMATE':
        assert value('saatchi_packaging_allowance_gbp') == 'n.a.'
        assert value('saatchi_asking_price_usd') == 'n.a.'
        held.append(record['catalogue_id'])
        continue
    target = value('Price (GBP)') - value('Manufacturing cost, excluding labour') - value('Labour cost')
    result = value('saatchi_profit_after_discount_gbp')
    assert result + 0.005 >= target, (record['catalogue_id'], result, target)
    margins.append(dict(catalogue_id=record['catalogue_id'], direct_profit_gbp=round(target, 2), modelled_saatchi_profit_gbp=result, packing_gbp=value('saatchi_packaging_allowance_gbp'), asking_usd=value('saatchi_asking_price_usd')))

assert len(margins) == 180 and len(held) == 1
receipt = json.loads((OUT / 'verification.json').read_text())
assert receipt['sha256'] == hashlib.sha256((OUT / 'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()
receipt.update(independent_reader='python-calamine 0.9.1', independently_verified_patches=len(plan['patches']), independently_verified_margin_cases=len(margins), held_missing_dimensions=held, readers_agree=True)
(OUT / 'independent-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
(OUT / 'independent-margin-readback.json').write_text(json.dumps(margins, indent=2) + '\n')
print(json.dumps(dict(status='PASS_INDEPENDENT_READER', cells=len(plan['patches']), qualified_margins=len(margins), missing_dimensions_held=held)))
