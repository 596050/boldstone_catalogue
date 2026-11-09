"""Read all saved native observations through an independent XLSX reader."""
import hashlib
import json
import math
import sys
from datetime import datetime, date
from pathlib import Path
sys.path.insert(0, '/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook

OUT = Path(__file__).parent
plan = json.loads((OUT / 'plan.json').read_text())
book = CalamineWorkbook.from_path(str(OUT / 'catalogue_wall_sculptures.xlsx'))
sheet = book.get_sheet_by_name('Wall Sculptures').to_python(skip_empty_area=False)
for patch in plan['patches']:
    column = 0
    for char in ''.join(c for c in patch['cell'] if c.isalpha()):
        column = column * 26 + ord(char) - 64
    row = int(''.join(c for c in patch['cell'] if c.isdigit()))
    actual, expected = sheet[row - 1][column - 1], patch['value']
    if patch.get('style')=='utc':
        assert isinstance(actual,datetime),patch['cell']
        actual=(actual-datetime(1899,12,30)).total_seconds()/86400
    assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-6) if isinstance(expected, (int, float)) and not isinstance(expected, bool) else actual == expected, patch['cell']
receipt = json.loads((OUT / 'verification.json').read_text())
assert receipt['sha256'] == hashlib.sha256((OUT / 'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()
receipt.update(independent_reader='python-calamine 0.9.1', independently_verified_cells=len(plan['patches']), readers_agree=True)
(OUT / 'independent-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(dict(status='PASS_INDEPENDENT_READER', cells=len(plan['patches']), columns=plan['last_added_column'], component_records=receipt['component_records'])))
