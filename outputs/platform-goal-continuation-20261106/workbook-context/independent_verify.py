"""Read every affected saved cell through a separate XLSX implementation."""
from pathlib import Path
import json,sys,hashlib
sys.path.insert(0,'/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook
OUT=Path(__file__).parent
plan=json.loads((OUT/'plan.json').read_text())
book=CalamineWorkbook.from_path(str(OUT/'catalogue_wall_sculptures.xlsx'))
tables={name:book.get_sheet_by_name(name).to_python(skip_empty_area=False) for name in {p['sheet'] for p in plan['patches']}}
for p in plan['patches']:
    col=0
    for c in ''.join(c for c in p['cell'] if c.isalpha()):col=col*26+ord(c)-64
    row=int(''.join(c for c in p['cell'] if c.isdigit()))
    value=tables[p['sheet']][row-1][col-1]
    assert value==p['value'],(p['sheet'],p['cell'],value,p['value'])
report=json.loads((OUT/'verification.json').read_text())
assert report['sha256']==hashlib.sha256((OUT/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()
report.update(independent_reader='python-calamine 0.9.1',independently_verified_patches=len(plan['patches']),readers_agree=True,saatchi_held_variant_photo_review=plan['saatchi_held_variant_photo_review'])
(OUT/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status='PASS_INDEPENDENT_READER',cells=len(plan['patches']),sheets=list(tables))))
