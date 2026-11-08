"""Independent saved-file check of every changed cell and all retail feed rows."""
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
sys.path.insert(0,'/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook
OUT=Path(__file__).parent
plan=json.loads((OUT/'plan.json').read_text())
book=CalamineWorkbook.from_path(str(OUT/'catalogue_wall_sculptures.xlsx'))
sheet=book.get_sheet_by_name('Wall Sculptures').to_python(skip_empty_area=False)
for p in plan['patches']:
    col=0
    for c in re.sub(r'\d','',p['cell']):col=col*26+ord(c)-64
    row=int(re.sub(r'\D','',p['cell']))
    actual,expected=sheet[row-1][col-1],p['value']
    assert (math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-6) if isinstance(expected,(int,float)) and not isinstance(expected,bool) else actual==expected),p['cell']
feed=CalamineWorkbook.from_path(str(OUT/'pinterest_wall_sculptures.xlsx')).get_sheet_by_name('Products').to_python(skip_empty_area=False)
assert feed[0]==plan['pinterest_feed_fields'] and len(feed)==177
for n,record in enumerate(plan['public_feed_rows'],1):
    for c,key in enumerate(plan['pinterest_feed_fields']):assert str(feed[n][c] or '')==str(record[key] or ''),(n,key)
assert len({r[0] for r in feed[1:]})==176
assert not any('cost' in str(h).lower() or 'labour' in str(h).lower() or str(h).lower().startswith(('ebay_','faire_','saatchi_')) for h in feed[0])
receipt=json.loads((OUT/'verification.json').read_text())
assert receipt['sha256']==hashlib.sha256((OUT/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()
receipt.update(independent_reader='python-calamine 0.9.1',independently_verified_cells=len(plan['patches']),public_feed_rows=176,public_feed_columns=46,no_private_cost_fields_in_public_feed=True)
(OUT/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(status='PASS',cells=len(plan['patches']),public_feed_rows=176)))
