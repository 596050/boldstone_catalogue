"""Register the verified preview repair without editing catalogue or review data."""
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
assert qa['status']=='PASS_INDEPENDENT_BARBADOS_V2_6_1_RECOVERY' and sha(pointer)==qa['baseline_pointer_sha256']
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
app.update(status='LOCAL_REVIEW_APP_V2_6_1_BARBADOS_WORKSHOP_PREVIEWS_VERIFIED',version='2.6.1',last_verified_utc=now,
    verification=str(H/'independent-verification.json'),verification_sha256=sha(H/'independent-verification.json'),
    owning_thread_handoff=qa['handoff'],owning_thread_handoff_sha256=qa['handoff_sha256'],
    contract_sha256=sha(ROOT/'catalogue-review/README.md'),
    ui_revision='retained-workshop-preview-fallback-preserving-current-cache-precedence',
    verification_scope='Independent111 tests and191 source/cache/HTTP/state checks. All23 Barbados previews decoded,12 workshop references recovered,9 full caches match retained Dropbox hashes,3 thumbnails retain unverified original dimensions.2050 old reviews/4197 events preserved plus9 later owner events.')
app['release_validation'].update(unit_tests=111,owner_tests_not_rerun_by_root=False)
app['saved_review_snapshot']={'event_cutoff':qa['live_event_cutoff'],'review_rows':qa['live_review_rows'],
    'predeployment_review_rows_preserved':2050,'predeployment_event_cutoff':4197,'later_owner_events':qa['later_owner_events'],
    'review_values_originals_versions_and_audit_events_preserved':True,'app_review_writes_by_catalogue_publisher':0,
    'owner_may_continue_reviewing':True}
app['retained_workshop_preview_recovery']={'family':'Barbados Wave','restored_preview_references':12,
    'family_image_endpoints_checked':23,'locally_hash_verified_retained_originals':9,'thumbnail_only_references':3,
    'current_cache_and_links_take_precedence':True,'outside_wall_reference_qualification_preserved':True,
    'live_wall_inventory_scope_expanded':False,'native_metadata_evidence_from_owning_session':qa['native_metadata_evidence'],
    'native_metadata_evidence_sha256':qa['native_metadata_evidence_sha256'],
    'original_dimensions_are_not_inferred_from_thumbnails':True,'identity_specifications_or_listing_approval_inferred':False}
p.update(recorded_utc=now,publication_receipt=rel(H/'publication-receipt.json'))
p['current_saved_specification_review'].update(last_independently_preserved_through_event=qa['live_event_cutoff'],
    latest_review_preservation_verification=rel(H/'independent-verification.json'),
    latest_review_preservation_verification_sha256=sha(H/'independent-verification.json'))
p['latest_master_metadata_change']={'status':'REGISTERED_VERIFIED_APP_V2_6_1_PREVIEW_REPAIR',
    'preceding_receipt':old['publication_receipt'],'source_register_core_preferred_workbook_and_gallery_bytes_unchanged':True,
    'review_values_originals_versions_and_audit_history_preserved':True,'outside_wall_reference_scope_preserved':True,
    'root_code_review_db_native_platform_mutations':0}
changed=[k for k in p if p[k]!=old[k]]
assert set(changed)=={'recorded_utc','publication_receipt','current_review_application','current_saved_specification_review','latest_master_metadata_change'}
updates={}
for path in controls:
    d=read(path);d.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for k in changed:
        if k in d and k not in {'recorded_utc','publication_receipt'}:d[k]=copy.deepcopy(p[k])
    updates[path]=d
if not a.apply:
    print(json.dumps({'status':'READY_VERIFIED_V2_6_1_METADATA_PUBLICATION','active_options':187,'restored_workshop_previews':12,
        'family_preview_responses':23,'saved_reviews_preserved':2050,'source_register_and_workbooks_unchanged':True},indent=2));raise SystemExit(0)
snap=H/'publication-inputs';snap.mkdir(exist_ok=True)
for path in [pointer,*controls]:
    dest=snap/str(path.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(path,dest)
def atomic(path,doc):
    temp=path.with_name(path.name+'.barbados-app-publication-tmp')
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
    receipt={'status':'PUBLISHED_VERIFIED_V2_6_1_BARBADOS_PREVIEW_REFERENCE','published_utc':now,
        'before_pointer_sha256':before[str(pointer)],'pointer_sha256':sha(pointer),'application_version':'2.6.1','active_options':187,
        'restored_workshop_previews':12,'family_preview_endpoints':23,'predeployment_review_rows_preserved':2050,
        'predeployment_events_preserved':4197,'later_owner_events_preserved':qa['later_owner_events'],
        'all_controls_equal_pointer':True,'register_and_workbook_bytes_unchanged':True,
        'verification':str(H/'independent-verification.json'),'verification_sha256':sha(H/'independent-verification.json'),
        'changed_pointer_keys':changed,'root_app_code_review_db_native_platform_writes':0}
    dump(H/'publication-receipt.json',receipt)
except BaseException:
    for path in reversed(written):
        source=snap/str(path.relative_to(B)).replace('/','__');temp=path.with_name(path.name+'.barbados-app-rollback-tmp')
        shutil.copy2(source,temp);os.replace(temp,path)
    raise
print(json.dumps(receipt,indent=2))
