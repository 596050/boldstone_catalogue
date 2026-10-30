import collections, datetime, hashlib, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
CAT=HERE.parents[2]
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(value,message):
    if not value:raise AssertionError(message)
pointer_path=CAT/'current-master.json'
pointer_sha=sha(pointer_path);p=load(pointer_path)
regpath=CAT/p['register'];register_sha=sha(regpath);r=load(regpath)
a=load(HERE/'strata-owner-approval.json')
base={o['product_id']:o for o in load(HERE/'baseline-options.json')['options']}
opts={o['product_id']:o for o in r['options']}
target=opts['BSI-7B6291B7C7F9'];ref=a['approved_reference_roles'][0]['reference']
if target.get('context_file_id')!=ref['file_id'] or target['photo_coverage']['in_situ']!='Available':
    print(json.dumps({'status':'AWAITING_CANONICAL_IMPORT','register':str(regpath)}));sys.exit(3)
check(p['register_sha256']==register_sha,'Published register hash mismatch')
workbook=CAT/p['workbook'];workbook_sha=sha(workbook)
check(p['workbook_sha256']==workbook_sha,'Published workbook hash mismatch')
for field in ['context_file_id','context_folder_id','context_image_url','context_folder_url']:
    key={'context_file_id':'file_id','context_folder_id':'folder_id','context_image_url':'image_url','context_folder_url':'folder_url'}[field]
    check(target[field]==ref[key],'Current Strata binding '+field)
check(a['decision_id'] in json.dumps(target),'Exact owner decision absent from option')
for pid,old in base.items():
    cur=opts[pid]
    for field in ['name','master_fields','specifications','selling_details','file_id','folder_id','image_url','folder_url','physical_specifications_verified']:
        check(cur.get(field)==old.get(field),'Unapproved field drift '+pid+'.'+field)
    for role in ['individual','series']:
        check(cur['photo_coverage'][role]==old['photo_coverage'][role],'Other role changed '+pid+'.'+role)
check(opts['BSI-3635E3DC3434']['photo_coverage']['series']=='No verified image','One Leaf Pewter series incorrectly closed')
active=r.get('active_option_ids',[o['product_id'] for o in r['options'] if o.get('counted_as_individual_option')])
check('BSI-C41824131174' not in active,'Sandstone retirement lost')
counts={role:dict(collections.Counter(opts[i]['photo_coverage'][role] for i in active)) for role in ['individual','in_situ','series']}
pc=p.get('current_image_review_links',{}).get('counts',{})
for role,key in [('in_situ','in_situ_gaps'),('series','series_gaps')]:
    if key in pc:check(pc[key]==counts[role].get('No verified image',0),'Pointer count mismatch '+key)
check(sha(pointer_path)==pointer_sha and sha(regpath)==register_sha and sha(workbook)==workbook_sha,'Publication changed during readback')
receipt={'status':'PASS_PUBLISHED_STRATA_OWNER_DESIGNATION','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pointer_sha256':pointer_sha,'register':str(regpath),'register_sha256':register_sha,'workbook':str(workbook),'workbook_sha256':workbook_sha,'decision_id':a['decision_id'],'reference':ref,'active_options':len(active),'historical_options':len(opts),'counts':counts,'three_scoped_option_specifications_and_individual_references_preserved':True,'one_leaf_pewter_series_still_unresolved':True,'canonical_writes':False,'workbook_exported':False,'dropbox_writes':False}
(HERE/'published-readback.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['reference','counts']},ensure_ascii=False))

