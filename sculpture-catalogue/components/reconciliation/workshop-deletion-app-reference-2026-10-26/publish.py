"""Register independently checked v2.7 review scope and later live receipts."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,os,shutil
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
dump=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');a=parser.parse_args()
qa=read(H/'independent-verification.json');pointer=B/'current-master.json'
assert qa['status']=='PASS_INDEPENDENT_V2_7_GUARDS_AND_REVIEW_PRESERVATION' and sha(pointer)==qa['baseline_pointer_sha256']
assert not (H/'publication-receipt.json').exists()
for group in ['application_files','protected_source_hashes']:
    for path,digest in qa[group].items():assert sha(path)==digest,path
assert sha(qa['handoff'])==qa['handoff_sha256'] and sha(qa['predeployment_backup'])==qa['predeployment_backup_sha256']
old=read(pointer);p=copy.deepcopy(old);now=datetime.now(timezone.utc).isoformat()
controls=[B/x for x in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
assert all(read(path)['current_master_catalogue']==old for path in controls)
before={str(path):sha(path) for path in [pointer,*controls]}
app=p['current_review_application']
app['preceding_validation_reference']={k:old['current_review_application'][k] for k in ['version','verification','verification_sha256','last_verified_utc','ui_revision'] if k in old['current_review_application']}
app.update(status='LOCAL_REVIEW_APP_V2_7_WORKSHOP_DELETION_REVIEW_AND_MISSING_CLEANUP_VERIFIED',
    version='2.7.0',last_verified_utc=now,verification=str(H/'independent-verification.json'),
    verification_sha256=sha(H/'independent-verification.json'),owning_thread_handoff=qa['handoff'],
    owning_thread_handoff_sha256=qa['handoff_sha256'],contract_sha256=sha(ROOT/'catalogue-review/README.md'),
    ui_revision='known-master-catalogue-image-deletion-review-and-separate-already-absent-cleanup',
    verification_scope='Independent122 tests and124 code/source/prepared-review/durable-state checks.2144 old reviews/4376 events preserved with18 later live events. Eight exact Barbados reviewed file IDs later have deleted/verified-absence receipts. Root used read-only inspection.')
app['release_validation'].update(unit_tests=122,owner_tests_not_rerun_by_root=False)
app['saved_review_snapshot']={'event_cutoff':qa['live_event_cutoff'],'review_rows':qa['live_review_rows'],
    'predeployment_review_rows_preserved':2144,'predeployment_event_cutoff':4376,'later_live_events':qa['later_live_events'],
    'review_values_originals_versions_and_audit_events_preserved':True,'app_review_writes_by_catalogue_publisher':0,
    'owner_may_continue_reviewing':True}
deletion=app['reviewed_native_file_deletion']
deletion.update(status='VERIFIED_EXACT_FILE_REVIEW_WITHIN_KNOWN_MASTER_CATALOGUE',
    supported_root='/BOLDSTONE MASTER',known_catalogue_image_ids_only=True,
    existing_account_namespace_anchor_verification_retained=True,missing_local_preview_does_not_block_native_inspection=True,
    present_files_pinned_to_native_identity_path_hash_size_revision_and_sharing=True,
    explicit_exact_file_or_complete_batch_confirmation_retained=True,
    native_absence_cleanup_state='already_absent',already_absent_cleanup_sends_no_native_delete=True,
    file_returning_after_absence_requires_new_present_file_review=True,
    transport_failure_does_not_establish_absence=True,folders_and_unknown_or_outside_master_files_rejected=True,
    original_source_history_and_cached_bytes_retained=True)
app['workshop_eight_file_receipt_observation']={'checked_utc':qa['checked_utc'],
    'file_ids':qa['reviewed_barbados_file_ids'],'job_states':qa['current_reviewed_job_states'],
    'results_are_later_live_activity_not_software_test_execution':True,
    'verified_absence_is_from_native_app_receipts_not_a_new_root_remote_rescan':True,
    'verification':str(H/'independent-verification.json'),'sha256':sha(H/'independent-verification.json'),
    'root_native_deletion_calls':0}
app['retained_workshop_preview_recovery']['recovered_count_is_historical_snapshot']=True
app['retained_workshop_preview_recovery']['later_known_file_deletion_receipts']=app['workshop_eight_file_receipt_observation']
app['retained_workshop_preview_recovery']['current_availability_is_resolved_by_live_app_tombstones']=True
p.update(recorded_utc=now,publication_receipt=rel(H/'publication-receipt.json'))
p['current_saved_specification_review'].update(last_independently_preserved_through_event=qa['live_event_cutoff'],
    latest_review_preservation_verification=rel(H/'independent-verification.json'),
    latest_review_preservation_verification_sha256=sha(H/'independent-verification.json'))
p['latest_master_metadata_change']={'status':'REGISTERED_VERIFIED_APP_V2_7_DELETION_REVIEW_SCOPE',
    'preceding_receipt':old['publication_receipt'],'source_register_core_preferred_workbook_and_gallery_bytes_unchanged':True,
    'review_history_and_later_live_activity_preserved':True,'root_code_review_db_native_platform_mutations':0,
    'software_tests_do_not_establish_the_later_native_deletion_outcome':True}
changed=[k for k in p if p[k]!=old[k]]
assert set(changed)=={'recorded_utc','publication_receipt','current_review_application','current_saved_specification_review','latest_master_metadata_change'}
updates={}
for path in controls:
    d=read(path);d.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for k in changed:
        if k in d and k not in {'recorded_utc','publication_receipt'}:d[k]=copy.deepcopy(p[k])
    updates[path]=d
if not a.apply:
    print(json.dumps({'status':'READY_VERIFIED_V2_7_METADATA_PUBLICATION','active_options':187,'unit_tests':122,
        'predeployment_reviews_preserved':2144,'later_live_events':18,'reviewed_job_states':qa['current_reviewed_job_states'],
        'register_and_workbook_bytes_unchanged':True},indent=2));raise SystemExit(0)
snap=H/'publication-inputs';snap.mkdir(exist_ok=True)
for path in [pointer,*controls]:
    dest=snap/str(path.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(path,dest)
def atomic(path,doc):
    temp=path.with_name(path.name+'.workshop-app-publication-tmp')
    with temp.open('w') as f:json.dump(doc,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
written=[]
try:
    assert all(sha(path)==before[str(path)] for path in [pointer,*controls])
    for path,doc in updates.items():atomic(path,doc);written.append(path)
    assert all(read(path)['current_master_catalogue']==p for path in controls)
    atomic(pointer,p);written.append(pointer)
    assert read(pointer)==p and all(read(path)['current_master_catalogue']==p for path in controls)
    assert all(sha(path)==digest for path,digest in qa['protected_source_hashes'].items())
    receipt={'status':'PUBLISHED_VERIFIED_V2_7_WORKSHOP_DELETION_REVIEW_REFERENCE','published_utc':now,
        'before_pointer_sha256':before[str(pointer)],'pointer_sha256':sha(pointer),'application_version':'2.7.0','active_options':187,
        'predeployment_review_rows_preserved':2144,'predeployment_events_preserved':4376,'later_live_events':18,
        'current_eight_reviewed_job_states':qa['current_reviewed_job_states'],'root_native_mutations':0,
        'all_controls_equal_pointer':True,'register_and_workbook_bytes_unchanged':True,
        'verification':str(H/'independent-verification.json'),'verification_sha256':sha(H/'independent-verification.json'),
        'changed_pointer_keys':changed,'root_app_code_review_db_native_platform_writes':0}
    dump(H/'publication-receipt.json',receipt)
except BaseException:
    for path in reversed(written):
        source=snap/str(path.relative_to(B)).replace('/','__');temp=path.with_name(path.name+'.workshop-app-rollback-tmp')
        shutil.copy2(source,temp);os.replace(temp,path)
    raise
print(json.dumps(receipt,indent=2))
