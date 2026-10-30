"""Register the verified selected-file deletion UI, with no review import."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import os
import shutil
import urllib.request

H=Path(__file__).resolve().parent;B=H.parents[2];APP=B.parent/'catalogue-review'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser()
parser.add_argument('--receipt',required=True,type=Path)
parser.add_argument('--receipt-sha',required=True)
args=parser.parse_args()
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.bulk-app-reference-tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
pointer=B/'current-master.json'
assert sha(pointer)=='7200c781f888508e967fdc55ff62360f8a2d858b628a5fee9bbd27ef8116cbd1'
old=read(pointer)
assert sha(args.receipt)==args.receipt_sha
qa=read(args.receipt)
assert qa['status'].startswith('PASS_')
assert qa['native_delete_calls_performed']==0
assert qa['native_inspections_performed']==0 and not qa['qa_database_promoted']
assert qa['saved_reviews_preserved']==288 and qa['saved_review_events_preserved_through']>=305
for name,digest in qa['code_hashes'].items():
    f=Path(name);f=f if f.is_absolute() else APP/f
    assert sha(f)==digest,str(f)
for name,digest in qa['canonical_sources_read_back'].items():
    assert sha(name)==digest,name
for name,digest in qa['evidence'].items():assert sha(name)==digest,name
controls=[B/x for x in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
for f in controls:assert read(f)['current_master_catalogue']==old
protected={}
for key in ['register','workbook']:
    f=B/old[key];assert sha(f)==old[key+'_sha256'];protected[str(f)]=sha(f)
for key in ['current_asset_reference_map','current_native_reference_map']:
    f=B/old[key]['path'];assert sha(f)==old[key]['sha256'];protected[str(f)]=sha(f)
f=B/old['preferred_review_workbook']
assert sha(f)==old['current_comprehensive_workbook']['sha256'];protected[str(f)]=sha(f)
with urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=10)as response:
    health=json.load(response);assert response.status==200
assert health['products']==188
snap=H/'inputs';snap.mkdir(exist_ok=True);snapshots={}
for f in [pointer,*controls]:
    dest=snap/str(f.relative_to(B)).replace('/','__');assert not dest.exists()
    shutil.copy2(f,dest);snapshots[f]=dest
now=datetime.now(timezone.utc).isoformat()
ref=copy.deepcopy(old['current_review_application'])
preceding={k:ref[k] for k in ['version','last_verified_utc','verification','verification_sha256','contract_sha256','ui_revision'] if k in ref}
ref.update(status='LOCAL_REVIEW_APP_SELECTED_FILE_DELETION_VERIFIED',
    version=health['version'],last_verified_utc=now,
    ui_revision='selected-file-batch-review-and-confirmation-20261025',
    verification=str(args.receipt.resolve()),verification_sha256=args.receipt_sha,
    contract_sha256=sha(APP/'README.md'),preceding_validation_reference=preceding,
    verification_scope=qa.get('scope',qa.get('validation_scope')))
ref['reviewed_native_file_deletion']['selected_file_batches']={
    'enabled':True,'entry_point':'Selected-images bar Delete button',
    'one_confirmation_for_complete_reviewed_manifest':True,
    'manifest_binds_exact_native_file_ids_and_revisions':True,
    'automatic_expansion_to_similar_files_or_aliases':False,
    'non_dropbox_selections_explicitly_skipped':True,
    'keepers_in_target_list_rejected':True,
    'duplicate_native_ids_or_display_groups_rejected':True,
    'per_file_revision_content_hash_sharing_and_use_rechecks':True,
    'durable_batch_table':'deletion_batches','per_file_jobs_table':'deletion_jobs',
    'execution_order':'Sequential','stop_on_unconfirmed_or_rejected_result':True,
    'automatic_destructive_retry':False,
    'per_file_outcomes_and_unattempted_files_shown':True,
    'native_delete_calls_during_release_verification':qa['native_delete_calls_performed'],
    'count_scope':'Sealed verification only; later user actions are separate.',
}
ref['general_live_source_sync']={'status':'PREPARED_ONLY_NOT_ENABLED','source_target_answer_pending':True}
ref['automatic_canonical_or_platform_application']=False
ref['release_validation']={k:qa[k] for k in ['unit_tests','qa_browser_checks','live_read_only_browser_checks'] if k in qa}
p=copy.deepcopy(old)
p.update(recorded_utc=now,current_review_application=ref,
    publication_receipt=str((H/'publication-receipt.json').relative_to(B)))
p['latest_master_metadata_change']={
    'status':'REVIEW_APP_SELECTED_FILE_DELETE_REFERENCE_ONLY',
    'preceding_receipt':old['publication_receipt'],
    'catalogue_register_workbooks_maps_and_canonical_photo_choices_unchanged':True,
    'review_database_reads_or_writes_by_registration':0,
}
allowed={'recorded_utc','current_review_application','publication_receipt','latest_master_metadata_change'}
assert all(p[k]==old[k] for k in old if k not in allowed)
updates={}
for f in controls:
    value=read(f);value.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for k in ['current_review_application','latest_master_metadata_change']:value[k]=copy.deepcopy(p[k])
    updates[f]=value
try:
    for f,snapshot in snapshots.items():assert sha(f)==sha(snapshot)
    assert sha(args.receipt)==args.receipt_sha
    for name,digest in qa['code_hashes'].items():
        f=Path(name);f=f if f.is_absolute() else APP/f
        assert sha(f)==digest,str(f)
    for f,value in updates.items():write(f,value)
    write(pointer,p)
    assert read(pointer)==p
    for f in controls:assert read(f)['current_master_catalogue']==p
    assert all(sha(f)==digest for f,digest in protected.items())
    receipt={'status':'PASS_SELECTED_FILE_DELETE_APP_REFERENCE_REGISTERED',
        'recorded_utc':now,'pointer_sha256':sha(pointer),
        'preceding_pointer_sha256':sha(snapshots[pointer]),
        'register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],
        'preferred_workbook_sha256':p['current_comprehensive_workbook']['sha256'],
        'application_verification_path':str(args.receipt.resolve()),'application_verification_sha256':args.receipt_sha,
        'application_code_hashes_checked':len(qa['code_hashes']),
        'controls_sha256':{str(f):sha(f) for f in controls},
        'protected_data_files_unchanged':protected,
        'review_database_reads_or_writes_by_registration':0,'canonical_review_imports':0,
        'native_or_platform_calls_by_registration':0,
        'release_checks':ref['release_validation']}
    write(H/'publication-receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['controls_sha256','protected_data_files_unchanged']},ensure_ascii=False,indent=2))
except BaseException:
    for f,snapshot in snapshots.items():shutil.copy2(snapshot,f)
    raise
