"""Register independently checked app capabilities without catalogue/data edits."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,os,shutil
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
dump=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');a=parser.parse_args()
qa=read(H/'independent-verification.json')
assert qa['status']=='PASS_INDEPENDENT_V2_5_RELEASE_AND_REVIEW_PRESERVATION'
pointer=B/'current-master.json';assert sha(pointer)==qa['baseline_pointer_sha256']
assert not (H/'publication-receipt.json').exists()
for group in ['application_files','protected_source_hashes']:
    for path,digest in qa[group].items():assert sha(path)==digest,path
assert sha(qa['handoff'])==qa['handoff_sha256']
assert sha(qa['predeployment_backup'])==qa['predeployment_backup_sha256']
old=read(pointer);p=copy.deepcopy(old);now=datetime.now(timezone.utc).isoformat()
controls=[B/x for x in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
assert all(read(f)['current_master_catalogue']==old for f in controls)
before={str(f):sha(f) for f in [pointer,*controls]}
p.update(recorded_utc=now,publication_receipt=rel(H/'publication-receipt.json'))
app=p['current_review_application']
app['preceding_validation_reference']={k:old['current_review_application'][k] for k in ['version','verification','verification_sha256','last_verified_utc','ui_revision'] if k in old['current_review_application']}
app.update(status='LOCAL_REVIEW_APP_V2_5_0_SIMILARITY_AND_MULTISORT_VERIFIED',version='2.5.0',last_verified_utc=now,
    verification=str(H/'independent-verification.json'),verification_sha256=sha(H/'independent-verification.json'),
    owning_thread_handoff=qa['handoff'],owning_thread_handoff_sha256=qa['handoff_sha256'],
    contract_sha256=sha(ROOT/'catalogue-review/README.md'),
    ui_revision='local-vision-similarity-ordered-multi-sort-and-unwanted-deletion-default',
    verification_scope='Independent94 Python tests,9 Node sort checks,15 deployed/QA file hashes and served static bytes;7091-image permutation with328 missing previews retained;1918 saved reviews and3952 audit events unchanged.')
app['release_validation'].update(unit_tests=94,node_sort_checks=9,owner_tests_not_rerun_by_root=False)
app['saved_review_snapshot']={'event_cutoff':3952,'review_rows':1918,'predeployment_review_rows_preserved':1918,
    'review_values_versions_originals_and_audit_events_preserved':True,'app_review_writes_by_catalogue_publisher':0,
    'owner_may_continue_reviewing':True}
app['visual_similarity']={'status':'VERIFIED_LOCAL_VIEW_ORDER_ONLY','algorithm':'Apple Vision feature prints revision2, nearest-neighbour order',
    'analysed_on_this_mac':True,'full_library_images':7091,'usable_local_previews':6763,'missing_preview_images_retained':328,
    'missing_previews_sort_last_within_group':True,'resized_and_brightness_fixture_copies_checked':True,
    'features_and_results_cached_with_input_identity':True,'similarity_is_not_duplicate_or_sculpture_identity_proof':True,
    'source_identities_image_selections_and_listing_order_not_changed':True}
app['image_multi_sort']={'maximum_ordered_rules':5,'directions_supported':True,'earlier_rules_define_similarity_groups':True,
    'later_rules_break_ties':True,'browser_preferences_and_shareable_url':True,'view_order_not_listing_order':True}
app['reviewed_native_file_deletion']['default_reason']='unwanted'
app['reviewed_native_file_deletion']['duplicate_keeper_required_only_for_duplicate_reason']=True
app['reviewed_native_file_deletion']['existing_metadata_review_and_explicit_delete_confirmation_retained']=True
p['current_saved_specification_review'].update(last_independently_preserved_through_event=3952,
    latest_review_preservation_verification=rel(H/'independent-verification.json'),
    latest_review_preservation_verification_sha256=sha(H/'independent-verification.json'))
p['latest_master_metadata_change']={'status':'REGISTERED_INDEPENDENTLY_VERIFIED_APP_V2_5_0',
    'preceding_receipt':old['publication_receipt'],'source_register_core_preferred_workbook_and_gallery_bytes_unchanged':True,
    'saved_review_values_originals_versions_and_audit_history_preserved':True,
    'catalogue_image_identity_or_physical_specification_imports':0,'root_runtime_db_native_platform_mutations':0}
changed=[k for k in p if p[k]!=old[k]]
assert set(changed)=={'recorded_utc','publication_receipt','current_review_application','current_saved_specification_review','latest_master_metadata_change'}
updates={}
for path in controls:
    d=read(path);d.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for key in changed:
        if key in d and key not in {'recorded_utc','publication_receipt'}:d[key]=copy.deepcopy(p[key])
    updates[path]=d
if not a.apply:
    print(json.dumps({'status':'READY_APP_V2_5_METADATA_ONLY_PUBLICATION','active_options':187,'code_files':len(qa['application_files']),
        'review_rows_preserved':1918,'audit_events_preserved':3952,'source_register_and_workbook_bytes_unchanged':True},indent=2));raise SystemExit(0)
snap=H/'publication-inputs';snap.mkdir(exist_ok=True)
for path in [pointer,*controls]:
    dest=snap/str(path.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(path,dest)
def atomic(path,doc):
    temp=path.with_name(path.name+'.similarity-app-publication-tmp')
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
    receipt={'status':'PUBLISHED_VERIFIED_APP_V2_5_METADATA_REFERENCE','published_utc':now,'before_pointer_sha256':before[str(pointer)],
        'pointer_sha256':sha(pointer),'application_version':'2.5.0','active_options':187,'review_rows_preserved':1918,
        'audit_events_preserved':3952,'all_controls_equal_pointer':True,'register_and_workbook_bytes_unchanged':True,
        'verification':str(H/'independent-verification.json'),'verification_sha256':sha(H/'independent-verification.json'),
        'changed_pointer_keys':changed,'root_runtime_db_native_platform_code_writes':0}
    dump(H/'publication-receipt.json',receipt)
except BaseException:
    for path in reversed(written):
        source=snap/str(path.relative_to(B)).replace('/','__');temp=path.with_name(path.name+'.similarity-app-rollback-tmp')
        shutil.copy2(source,temp);os.replace(temp,path)
    raise
print(json.dumps(receipt,indent=2))
