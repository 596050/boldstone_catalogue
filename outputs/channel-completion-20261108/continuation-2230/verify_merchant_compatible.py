"""Independently read native exports before/after the bounded same-photo update."""
from pathlib import Path
from datetime import datetime,timezone
import csv,io,json,hashlib,sys,zipfile

OUT=Path(__file__).parent
phase,source=sys.argv[1],Path(sys.argv[2]);assert phase in ['before','after']
with zipfile.ZipFile(source) as archive:
    names=[name for name in archive.namelist() if name.endswith('.tsv')];assert len(names)==1
    payload=archive.read(names[0])
actual_rows=list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig')),delimiter='\t'))
actual={row['id']:row for row in actual_rows};assert len(actual_rows)==len(actual)==325
plan_path=OUT.parent/'google-supplement-refresh-plan.json' if phase=='before' else OUT/'merchant-compatible-supplement-plan.json'
plan=json.loads(plan_path.read_text());assert len(plan['rows'])==176
differences=[]
for expected in plan['rows']:
    observed=actual[expected['id']]
    for field,value in expected.items():
        if observed[field.replace('_',' ')]!=value:
            differences.append({'offer_id':expected['id'],'field':field,'expected':value,'observed':observed[field.replace('_',' ')]})
result={'checked_at':datetime.now(timezone.utc).isoformat(),'phase':phase,'native_offers':325,'publication_products':176,
    'compared_publication_fields':len(plan['headers'])*176,'differences':differences,
    'native_export_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
if phase=='after':
    frozen={row['id']:row for row in csv.DictReader((OUT/'google-rendition-before-native.tsv').open(encoding='utf-8-sig'),delimiter='\t')}
    assert set(actual)==set(frozen)
    scope={row['id'] for row in plan['rows']};protected=['title','price','brand','image link','additional image link','availability','condition','link','shipping weight','max handling time']
    outside=[{'offer_id':key,'field':field} for key in actual.keys()-scope for field in protected if actual[key][field]!=frozen[key][field]]
    price_changes=[key for key in actual if actual[key]['price']!=frozen[key]['price']]
    result.update(unrelated_offers_compared=149,unrelated_protected_field_differences=outside,price_changes=price_changes,new_products=0)
    assert not outside and not price_changes
result['status']='PASS_NATIVE_COMBINED_OFFER_READBACK' if not differences else 'HOLD_NATIVE_OFFER_DIFFERENCES'
(OUT/f'google-rendition-{phase}-native.zip').write_bytes(source.read_bytes())
(OUT/f'google-rendition-{phase}-native.tsv').write_bytes(payload)
(OUT/f'google-rendition-{phase}-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='differences'},indent=2))
if differences:
    print(json.dumps([{'offer_id':row['offer_id'],'field':row['field']} for row in differences[:15]],indent=2))
    raise SystemExit(2)
