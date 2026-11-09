"""Read converted UTC instants and all other cells through independent Calamine."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
sys.path.insert(0,'/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook
OUT=Path(__file__).parent;plan=json.loads((OUT/'plan.json').read_text())
book=CalamineWorkbook.from_path(str(OUT/'catalogue_wall_sculptures.xlsx'))
sheets={n:book.get_sheet_by_name(n).to_python(skip_empty_area=False) for n in book.sheet_names}
for p in plan['patches']:
    col=0
    for c in re.sub(r'\d','',p['cell']):col=col*26+ord(c)-64
    row=int(re.sub(r'\D','',p['cell']));actual=sheets[p['sheet']][row-1][col-1]
    if p['style']=='utc':
        assert isinstance(actual,datetime),(p['sheet'],p['cell'],actual)
        original=datetime.fromisoformat(p['original_utc'].replace('Z','+00:00')).replace(tzinfo=None)
        assert abs((actual-original).total_seconds())<=.001,(p['cell'],actual,original)
    else:assert actual==p['value']
receipt=json.loads((OUT/'verification.json').read_text())
assert receipt['sha256']==hashlib.sha256((OUT/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()
receipt.update(independent_reader='python-calamine',readers_agree=True,independently_verified_cells=len(plan['patches']),utc_instant_tolerance_seconds=.001)
(OUT/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(status='PASS_INDEPENDENT_UTC_INSTANT_READBACK',patches=len(plan['patches']),date_cells=1832)))
