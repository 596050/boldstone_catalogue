"""Record the verified local review tool without reading or applying reviews."""
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request

H=Path(__file__).resolve().parent;B=H.parents[2];APP=B.parent/'catalogue-review'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.review-app-tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
pointer=B/'current-master.json';assert sha(pointer)=='ab7f8a6e3d196ad7e5c5923bde10f60f904126b5c1c3ec315f8448851260b223'
old=read(pointer);verified=read(APP/'verification.json');assert verified['status']=='PASS_V2_IMAGE_REVIEW_READY'
assert sha(APP/'verification.json')=='6273894e79faf6502868304ddf5dbef4a56641304ec2dfa68bbb32b88add2f20'
for name,digest in verified['file_hashes'].items():assert sha(APP/name)==digest,name
for key in ['register','workbook']:assert sha(B/old[key])==old[key+'_sha256']
assert verified['source_coverage']['source']['register_sha256']==old['register_sha256']
with urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=10)as response:health=json.load(response);assert response.status==200
assert health['status']=='ok'and health['products']==188 and health['version']=='2.0'
controls=[B/'components/reviews/specification_review_progress.json',B/'components/checkpoint.json',B/'checkpoint.json']
for path in controls:assert read(path)['current_master_catalogue']==old
(H/'inputs').mkdir(exist_ok=True);snapshots={}
for path in [pointer,*controls]:
    dest=H/'inputs'/str(path.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(path,dest);snapshots[path]=dest
now=datetime.now(timezone.utc).isoformat()
ref={'status':'LOCAL_REVIEW_APP_V2_HEALTHY_AT_LAST_VERIFICATION','last_verified_utc':now,'url':'http://127.0.0.1:8767',
    'launcher':str(APP/'Open Boldstone Review.command'),'contract':str(APP/'README.md'),'contract_sha256':sha(APP/'README.md'),
    'verification':str(APP/'verification.json'),'verification_sha256':sha(APP/'verification.json'),
    'source_register_sha256':old['register_sha256'],'source_gallery_sha256':verified['source_coverage']['source']['gallery_sha256'],
    'source_coverage':verified['source_coverage'],'review_state_database':str(Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3')),
    'export_directory':str(Path('/Users/tprice/Library/Application Support/BoldstoneReview/exports')),'export_schema':'boldstone-review/v2',
    'review_state_separate_from_canonical_catalogue':True,'automatic_canonical_or_platform_application':False,
    'import_instruction_required':'Do not import review decisions into canonical records or platforms unless explicitly instructed.',
    'image_edit_requests_are_pending_instructions':True,'review_database_reads_or_writes_by_metadata_registration':0,'version':'2.0','v1_reviews_preserved':True,'previous_version_reference':copy.deepcopy(old['current_review_application']),'assignment_changes_are_reversible_review_overlays':True,'exact_byte_dedupe_keeps_source_and_review_aliases':True}
p=copy.deepcopy(old);p.update(recorded_utc=now,current_review_application=ref,publication_receipt=rel(H/'publication-receipt.json'))
p['current_image_review_links']['local_review_application']=ref['url']
p['latest_master_metadata_change']={'status':'LOCAL_REVIEW_APPLICATION_V2_REFERENCE_ONLY','preceding_receipt':old['publication_receipt'],
    'catalogue_register_workbook_images_and_review_decisions_unchanged':True}
allowed={'recorded_utc','current_review_application','publication_receipt','current_image_review_links','latest_master_metadata_change'}
assert all(p[k]==old[k]for k in old if k not in allowed)
updates={}
for path in controls:
    value=read(path);value.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for key in ['current_review_application','current_image_review_links','latest_master_metadata_change']:value[key]=copy.deepcopy(p[key])
    updates[path]=value
try:
    for path,snapshot in snapshots.items():assert sha(path)==sha(snapshot)
    for path,value in updates.items():write(path,value)
    write(pointer,p)
    assert read(pointer)==p
    for path in controls:assert read(path)['current_master_catalogue']==p
    for key in ['register','workbook']:assert sha(B/p[key])==p[key+'_sha256']
    receipt={'status':'PASS_LOCAL_REVIEW_APP_V2_REFERENCE_REGISTERED','recorded_utc':now,'pointer_sha256':sha(pointer),
        'preceding_pointer_sha256':sha(snapshots[pointer]),'register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],
        'url':ref['url'],'health':health,'verification_sha256':ref['verification_sha256'],'controls_sha256':{str(x):sha(x)for x in controls},
        'new_catalogue_or_review_decision_or_platform_changes':0,'metadata_pointer_keys_changed':sorted(allowed)}
    write(H/'publication-receipt.json',receipt);print(json.dumps({k:v for k,v in receipt.items()if k!='controls_sha256'},indent=2))
except BaseException:
    for path,snapshot in snapshots.items():shutil.copy2(snapshot,path)
    raise
