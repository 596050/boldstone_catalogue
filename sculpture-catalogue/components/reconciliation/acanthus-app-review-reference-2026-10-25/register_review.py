"""Record completed app-only photo review without importing any decisions."""
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
    path=Path(path);temp=path.with_name(path.name+'.acanthus-app-tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
pointer=B/'current-master.json';assert sha(pointer)=='c8e3eea61b7da6555afe536bc422b556552bf17b5147f638c50899570980494c'
old=read(pointer);qpath=APP/'verification.json';assert sha(qpath)=='53170c540d0bdfd0129faba6f0557afe24d8c9f343e72efc0cce856ede620c48';q=read(qpath)
assert q['status']=='PASS_COMPACT_CARDS_AND_ACANTHUS_REVIEW'and q['existing_review_rows_preserved']
for name,digest in {**q['file_hashes'],**q['artifact_hashes']}.items():assert sha(APP/name)==digest,name
prior=Path(q['previous_validation_receipt']);assert sha(prior)=='6273894e79faf6502868304ddf5dbef4a56641304ec2dfa68bbb32b88add2f20'
summary_path=Path(q['review_summary']);summary=read(summary_path)
assert summary['status']=='SAVED_AND_READ_BACK'and summary['counts']['active_options']==10 and summary['counts']['listing_selections']==21 and summary['counts']['primary_images']==10
for key in ['register','workbook']:assert sha(B/old[key])==old[key+'_sha256']
with urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=10)as response:health=json.load(response);assert response.status==200
assert health['products']==188 and health['version']=='2.0'
controls=[B/'components/reviews/specification_review_progress.json',B/'components/checkpoint.json',B/'checkpoint.json']
for path in controls:assert read(path)['current_master_catalogue']==old
(H/'inputs').mkdir(exist_ok=True);snapshots={}
for path in [pointer,*controls]:
    dest=H/'inputs'/str(path.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(path,dest);snapshots[path]=dest
now=datetime.now(timezone.utc).isoformat();ref=copy.deepcopy(old['current_review_application'])
ref.update(last_verified_utc=now,ui_revision='compact-cards-acanthus-20261025',verification=str(qpath),verification_sha256=sha(qpath),
    contract_sha256=sha(APP/'README.md'),verification_scope=q['validation_scope'],
    preceding_full_validation_receipt={'path':str(prior),'sha256':sha(prior)},
    latest_completed_review={'status':'LOCAL_REVIEW_CHOICES_SAVED_NOT_IMPORTED','family':'Acanthus','counts':summary['counts'],
        'report':q['review_report'],'report_sha256':sha(q['review_report']),'summary':str(summary_path),'summary_sha256':sha(summary_path),
        'browser_checks':28,'readback_checks':308,'qualifications':summary['qualifications'],
        'canonical_identity_specification_or_coverage_changes':0,'canonical_import_instruction_required':True},
    review_shortcuts={'in_situ':'http://127.0.0.1:8767/#BSI-A9FE7D79863A?type=in_situ','group':'http://127.0.0.1:8767/#BSI-A9FE7D79863A?type=group'})
p=copy.deepcopy(old);p.update(recorded_utc=now,current_review_application=ref,publication_receipt=rel(H/'publication-receipt.json'))
p['current_image_review_links']['acanthus_app_review_report']=q['review_report']
p['latest_master_metadata_change']={'status':'ACANTHUS_APP_REVIEW_REFERENCE_ONLY','preceding_receipt':old['publication_receipt'],
    'catalogue_register_workbook_and_canonical_photo_choices_unchanged':True}
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
    for path in controls:assert read(path)['current_master_catalogue']==p
    assert read(pointer)==p
    for key in ['register','workbook']:assert sha(B/p[key])==p[key+'_sha256']
    receipt={'status':'PASS_ACANTHUS_LOCAL_APP_REVIEW_REFERENCE_REGISTERED','recorded_utc':now,'pointer_sha256':sha(pointer),
        'preceding_pointer_sha256':sha(snapshots[pointer]),'register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],
        'verification_sha256':sha(qpath),'summary_sha256':sha(summary_path),'active_options_reviewed':10,'listing_photo_selections':21,'primary_images':10,
        'app_only_wrong_finish_exclusions':47,'app_browser_checks':28,'saved_review_readback_checks':308,
        'controls_sha256':{str(x):sha(x)for x in controls},'review_database_reads_or_writes_by_registration':0,'canonical_or_platform_imports':0}
    write(H/'publication-receipt.json',receipt);print(json.dumps({k:v for k,v in receipt.items()if k!='controls_sha256'},indent=2))
except BaseException:
    for path,snapshot in snapshots.items():shutil.copy2(snapshot,path)
    raise
