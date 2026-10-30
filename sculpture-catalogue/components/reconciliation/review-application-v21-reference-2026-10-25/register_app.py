"""Register a sealed app release; never import reviews or modify native files."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import os
import shutil
import urllib.request

H=Path(__file__).resolve().parent
B=H.parents[2]
APP=B.parent/'catalogue-review'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser()
parser.add_argument('--receipt',type=Path,required=True)
parser.add_argument('--receipt-sha',required=True)
args=parser.parse_args()
def write(path,value):
    path=Path(path)
    tmp=path.with_name(path.name+'.v21-reference-tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,path)
assert not (H/'publication-receipt.json').exists()
pointer=B/'current-master.json'
assert sha(pointer)=='9083266b288bfef81f806c3975a18a8dc1bb5268a984152de64852bbd5bf3c1c'
old=read(pointer)
assert sha(args.receipt)==args.receipt_sha
qa=read(args.receipt)
assert qa['status'].startswith('PASS_')
assert qa['native_delete_calls_performed']==0
assert qa['saved_reviews_never_replaced_from_qa']
assert qa['review_events_preserved_through']>=305
for name,digest in qa['code_hashes'].items():
    f=Path(name)
    f=f if f.is_absolute() else APP/f
    assert sha(f)==digest,str(f)
for name,digest in qa['canonical_source_hashes_preserved'].items():
    assert sha(name)==digest,name
for key in ['register','workbook']:
    assert sha(B/old[key])==old[key+'_sha256']
assert sha(B/old['preferred_review_workbook'])==old['current_comprehensive_workbook']['sha256']
with urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=10) as response:
    health=json.load(response)
    assert response.status==200
assert health['products']==188 and health['version']=='2.1'
controls=[B/x for x in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
for f in controls:
    assert read(f)['current_master_catalogue']==old
protected={str(B/old[k]):sha(B/old[k]) for k in ['register','workbook']}
protected[str(B/old['preferred_review_workbook'])]=sha(B/old['preferred_review_workbook'])
protected[str(B/old['current_asset_reference_map']['path'])]=old['current_asset_reference_map']['sha256']
protected[str(B/old['current_native_reference_map']['path'])]=old['current_native_reference_map']['sha256']
snap=H/'inputs'
snap.mkdir(exist_ok=True)
snapshots={}
for f in [pointer,*controls]:
    target=snap/str(f.relative_to(B)).replace('/','__')
    assert not target.exists()
    shutil.copy2(f,target)
    snapshots[f]=target
now=datetime.now(timezone.utc).isoformat()
ref=copy.deepcopy(old['current_review_application'])
previous={k:ref[k] for k in ['version','last_verified_utc','verification','verification_sha256','contract_sha256','ui_revision'] if k in ref}
ref.update(
    status='LOCAL_REVIEW_APP_V21_HEALTHY_AT_VERIFICATION',version='2.1',
    last_verified_utc=now,ui_revision='independent-purposes-saved-modal-reviewed-file-deletion-20261025',
    contract_sha256=sha(APP/'README.md'),verification=str(args.receipt.resolve()),verification_sha256=args.receipt_sha,
    verification_scope=qa['scope'],preceding_validation_reference=previous,
    card_purposes={'listing_and_advertising_independently_selectable':True,'exclude_clears_all_purposes_for_current_option':True},
    modal_save={'both_image_and_shared_metadata_forms':True,'discard_prompt_only_for_actual_unsaved_values':True},
    reviewed_native_file_deletion={
        'enabled':True,'scope':'Explicitly reviewed individual Dropbox file only',
        'per_file_final_confirmation_required':True,'normal_recoverable_delete_only':True,
        'permanent_recovery_history_purge':False,'automatic_similarity_or_size_deletion':False,
        'stable_file_revision_and_content_hash_guard':True,'keeper_and_sharing_and_other_uses_reviewed':True,
        'same_exact_byte_display_group_keeper_supported':False,
        'same_group_keeper_rejected_before_native_inspection_and_execution':True,
        'durable_jobs_table':'deletion_jobs','durable_review_kind':'deletion',
        'execution_states':['executing','uncertain','deleted','rejected'],
        'uncertain_requests_automatically_retried':False,
        'status_recheck_read_only':True,'deleted_primary_automatically_replaced':False,
        'history_reviews_cached_bytes_and_platform_source_records_retained':True,
        'canonical_inventory_reconciliation_owner':'01a144ab-1a7c-7223-a403-73a4d53d70ff',
        'canonical_inventory_reconciliation_requires_verified_receipt':True,
        'real_delete_calls_during_release_verification':qa['native_delete_calls_performed'],
        'real_delete_call_count_scope':'Sealed release verification only; later user actions are separate.',
    },
    automatic_canonical_or_platform_application=False,
    general_live_source_sync={'status':'PREPARED_ONLY_NOT_ENABLED','source_target_answer_pending':True},
    last_completed_review_is_a_snapshot=True,
    current_user_choices_may_differ_from_last_completed_review=True,
    release_validation={'unit_tests':qa['unit_tests'],'qa_browser_checks':qa['qa_browser_checks'],
        'live_read_only_browser_checks':qa['live_read_only_browser_checks'],
        'review_events_preserved_through':qa['review_events_preserved_through']},
)
p=copy.deepcopy(old)
p.update(recorded_utc=now,current_review_application=ref,
    publication_receipt=str((H/'publication-receipt.json').relative_to(B)))
p['latest_master_metadata_change']={
    'status':'REVIEW_APP_V21_REFERENCE_ONLY','preceding_receipt':old['publication_receipt'],
    'catalogue_register_workbooks_image_maps_and_canonical_photo_choices_unchanged':True,
    'review_database_reads_or_writes_by_registration':0,
}
allowed={'recorded_utc','current_review_application','publication_receipt','latest_master_metadata_change'}
assert all(old[k]==p[k] for k in old if k not in allowed)
updates={}
for f in controls:
    value=read(f)
    value.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for k in ['current_review_application','latest_master_metadata_change']:
        value[k]=copy.deepcopy(p[k])
    updates[f]=value
try:
    for f,snapshot in snapshots.items():
        assert sha(f)==sha(snapshot)
    assert sha(args.receipt)==args.receipt_sha
    for name,digest in qa['code_hashes'].items():
        f=Path(name);f=f if f.is_absolute() else APP/f
        assert sha(f)==digest,str(f)
    for f,value in updates.items():
        write(f,value)
    write(pointer,p)
    assert read(pointer)==p
    for f in controls:
        assert read(f)['current_master_catalogue']==p
    assert all(sha(name)==digest for name,digest in protected.items())
    receipt={'status':'PASS_REVIEW_APP_V21_REFERENCE_REGISTERED','recorded_utc':now,
        'pointer_sha256':sha(pointer),'preceding_pointer_sha256':sha(snapshots[pointer]),
        'source_register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],
        'preferred_workbook_sha256':p['current_comprehensive_workbook']['sha256'],
        'application_verification_path':str(args.receipt.resolve()),'application_verification_sha256':args.receipt_sha,
        'application_code_hashes_checked':len(qa['code_hashes']),
        'controls_sha256':{str(f):sha(f) for f in controls},'protected_data_files_unchanged':protected,
        'review_database_reads_or_writes_by_registration':0,'canonical_review_imports':0,
        'native_or_platform_calls_by_registration':0,
        'unit_tests_in_release_receipt':qa['unit_tests'],'qa_browser_checks_in_release_receipt':qa['qa_browser_checks'],
        'live_read_only_checks_in_release_receipt':qa['live_read_only_browser_checks']}
    write(H/'publication-receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['controls_sha256','protected_data_files_unchanged']},ensure_ascii=False,indent=2))
except BaseException:
    for f,snapshot in snapshots.items():
        shutil.copy2(snapshot,f)
    raise
