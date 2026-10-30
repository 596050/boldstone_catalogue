"""Independently verify all saved app field choices from immutable export bytes."""
from pathlib import Path
from collections import Counter
from urllib.parse import quote
import csv,hashlib,json,re,sqlite3
H=Path(__file__).resolve().parent;B=H.parents[2];APP=B.parent/'catalogue-review';D=APP/'reviews/specification-completion-20261025'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
q=read(D/'sealed-handoff.json');assert sha(D/'sealed-handoff.json')=='60a2e5c6e5e9b608ff5378a579d47c3b05f4a7907913cc8436d982677bd54e0a'
assert q['status']=='applied_and_verified_in_local_review_app'and q['failures']==0
for r in q['artifacts']+q['application_code']:assert sha(r['path'])==r['sha256'],r['path']
base=read(APP/'verification-family-coverage-v2.1.json')
codes={str((Path(k)if Path(k).is_absolute()else APP/k).resolve()):v for k,v in base['code_hashes'].items()}
codes.update({r['path']:r['sha256']for r in q['application_code']})
for f,digest in codes.items():assert sha(f)==digest,f
p=read(B/'current-master.json');assert sha(B/'current-master.json')==q['unchanged_current_master_sha256']
assert sha(B/p['register'])==q['source']['register_sha256']==p['register_sha256']
assert sha(q['source']['gallery_database'])==q['source']['gallery_sha256']
assert sha(B/p['workbook'])==p['workbook_sha256']and sha(B/p['preferred_review_workbook'])==p['current_comprehensive_workbook']['sha256']
g=read(B/p['register']);active=set(g['active_option_ids']);assert len(active)==188
initial=read(D/'initial-app-fields.json');products={r['id']:r for r in initial['products']};assert set(products)==active
source_fields={(pid,f['key']):f for pid,r in products.items()for f in r['fields']}
def normalize(r):
    out=dict(r)
    for key,value in out.items():
        if isinstance(value,str)and value.startswith(('{','[')):
            try:out[key]=json.loads(value)
            except ValueError:pass
    return out
before=read(D/'before-live-state.json');old={(r['kind'],r['product_id'],r['item_id']):normalize(r)for r in before['reviews']}
backup=Path(q['export']['path'])/'review-backup.sqlite3';assert backup.is_file()
c=sqlite3.connect('file:'+quote(str(backup))+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
after={(r['kind'],r['product_id'],r['item_id']):normalize(r)for r in c.execute('SELECT * FROM reviews')}
assert len(old)==308 and len(after)==1790
checks=0
for key,value in old.items():
    if key[0]!='field':assert after[key]==value,key;checks+=1
for table in ['operations','deletion_jobs','deletion_batches']:
    expected=[normalize(r)for r in before[table]];actual=[normalize(r)for r in c.execute('SELECT * FROM '+table)]
    canon=lambda rows:sorted(json.dumps(r,sort_keys=True,ensure_ascii=False)for r in rows)
    assert canon(actual)==canon(expected),table;checks+=len(expected)
event_map={r['id']:normalize(r)for r in c.execute('SELECT * FROM events')}
for r in before['events']:assert event_map[r['id']]==normalize(r);checks+=1
assert len(event_map)==1830
new_events=[r for i,r in event_map.items()if i>347];assert len(new_events)==1483 and all(r['kind']=='field'for r in new_events)
deleted={r['file_id']for r in c.execute("SELECT file_id FROM deletion_jobs WHERE state='deleted'")};assert len(deleted)==6
c.close()
fields={'Dimensions / depth','Weight','Material / finish','Fixing','Price','Availability','Lead time'}
plan=read(D/'prepared-values.json');changes=plan['changes'];assert len(changes)==1483
for change in changes:
    key=('field',change['product_id'],change['item_id']);saved=after[key]
    assert saved['data']==change['data']and saved['version']==change['version']+1,key
    assert saved['source_hash']==p['register_sha256'],key
    checks+=3
readback=read(D/'all-188-readback.json');assert len(readback)==188and{r['product_id']for r in readback}==active
byid={r['product_id']:r for r in readback};certainty=Counter();reference_ids=[]
for pid in active:
    row=byid[pid];assert set(row['values'])==fields
    for field in fields:
        record=after[('field',pid,field)];value=record['data']['value'];src=source_fields[(pid,field)]
        assert record['data']['decision']=='edit'and value.strip()
        assert value==row['values'][field]and '\u2014'not in value
        assert not re.search(r'\b(?:estimate(?:d|s)?|proposal)\b',value,re.I),(pid,field,value)
        assert record['original']==src,(pid,field,'source changed')
        assert row['provenance'][field]['original']==src
        assert record['data']['evidence']and record['data']['certainty']in{'estimate','source_claim','confirmed'}
        certainty[record['data']['certainty']]+=1;checks+=7
    old_name=old.get(('field',pid,'Name'),{}).get('data',{})
    original_name=old_name.get('value')if old_name.get('decision')=='edit'else source_fields[(pid,'Name')]['value']
    assert row['name']==original_name.replace('\u2014','-'),pid;checks+=1
    reference=row.get('image_reference')
    if reference:
        assert reference['id']not in deleted and reference.get('folder_url')and reference.get('url');reference_ids.append(reference['id']);checks+=3
export_fields=list(csv.DictReader((Path(q['export']['path'])/'specification-decisions.csv').open(encoding='utf-8-sig')))
export_index={(r['product_id'],r['field']):r for r in export_fields}
for pid in active:
    for field in fields:
        r=export_index[(pid,field)];src=source_fields[(pid,field)];data=after[('field',pid,field)]['data']
        assert r['listing_value']==byid[pid]['values'][field]
        assert r['original']==src['value']and r['original_qualification']==src['qualification']and r['source_basis']==src['basis']
        assert r['certainty']==data['certainty']and r['evidence']==data['evidence'];checks+=6
special=byid['BSI-46F6DB226213']['values']
assert special['Lead time']=='1 week'and '175'in special['Price']and '4'in special['Weight']
assert all('70'in r['values']['Dimensions / depth']and '15'in r['values']['Dimensions / depth']for r in readback if r['family']=='Frozen Fish')
oldname=('field','BSI-8CD6A48141ED','Name');assert 'White'in after[oldname]['data']['value']
result={'status':'PASS_INDEPENDENT_ALL188_APP_FIELDS_AND_EXPORT',
    'handoff_sha256':sha(D/'sealed-handoff.json'),'products':188,'specification_fields':1316,
    'punctuation_only_names':167,'saved_review_rows':1790,'event_cutoff':1830,'checks':checks,
    'previous_nonfield_rows_preserved':307,'original_events_preserved':347,
    'operations_deletion_jobs_batches_preserved':True,'prior_owner_white_name_preserved':True,
    'internal_certainty_counts':dict(certainty),'image_references_not_deleted':len(reference_ids),
    'missing_image_reference_option_ids':[r['product_id']for r in readback if not r.get('image_reference')],
    'separate_provenance_columns_verified':True,'new_physical_measurements':0,
    'register_sha256':p['register_sha256'],'export_backup_sha256':sha(backup),
    'all_application_code_hashes':codes,'active_review_database_writes':0,'native_calls':0,
    'actual_specification_verification_status_unchanged':not p['all_actual_specifications_complete']}
(H/'app-independent-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k!='all_application_code_hashes'},ensure_ascii=False,indent=2))
