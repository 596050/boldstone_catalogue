"""Register checked v2.6 app behavior, preserving canonical and review data."""
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
assert qa['status']=='PASS_INDEPENDENT_V2_6_COMPONENTS_AND_REVIEW_PRESERVATION'
assert sha(pointer)==qa['baseline_pointer_sha256']
assert not (H/'publication-receipt.json').exists()
for group in ['application_files','protected_source_hashes']:
    for path,digest in qa[group].items():assert sha(path)==digest,path
assert sha(qa['handoff'])==qa['handoff_sha256'] and sha(qa['before_backup'])==qa['before_backup_sha256']
old=read(pointer);p=copy.deepcopy(old);now=datetime.now(timezone.utc).isoformat()
controls=[B/x for x in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
assert all(read(f)['current_master_catalogue']==old for f in controls)
before={str(f):sha(f) for f in [pointer,*controls]}
p.update(recorded_utc=now,publication_receipt=rel(H/'publication-receipt.json'))
app=p['current_review_application']
app['preceding_validation_reference']={k:old['current_review_application'][k] for k in ['version','verification','verification_sha256','last_verified_utc','ui_revision'] if k in old['current_review_application']}
app.update(status='LOCAL_REVIEW_APP_V2_6_COMPONENT_VISIBILITY_AND_IMAGE_USES_VERIFIED',version='2.6.0',last_verified_utc=now,
    verification=str(H/'independent-verification.json'),verification_sha256=sha(H/'independent-verification.json'),
    owning_thread_handoff=qa['handoff'],owning_thread_handoff_sha256=qa['handoff_sha256'],
    contract_sha256=sha(ROOT/'catalogue-review/README.md'),
    ui_revision='exact-group-folder-component-visibility-and-per-component-listing-advertising',
    verification_scope='Independent106 Python tests,9 Node sort checks,481 read-only native-ID/component/API/state checks;2012 predeployment review rows and4131 events preserved, plus9 later owner events through4140.')
app['release_validation'].update(unit_tests=106,node_sort_checks=9,owner_tests_not_rerun_by_root=False)
app['saved_review_snapshot']={'event_cutoff':qa['live_event_cutoff'],'review_rows':qa['live_review_rows'],
    'predeployment_review_rows_preserved':2012,'predeployment_event_cutoff':4131,'later_owner_events':qa['later_owner_events'],
    'review_values_versions_originals_and_audit_events_preserved':True,'app_review_writes_by_catalogue_publisher':0,
    'owner_may_continue_reviewing':True}
app['component_image_controls']={'status':'VERIFIED_EXPLICIT_PER_COMPONENT_CHOICES',
    'viewing_defaults':'Only complete unambiguous matches to the components named in the current group folder',
    'size_finish_and_number_distinctions_preserved':True,'manual_removals_and_image_use_exclusions_preserved':True,
    'per_component_choices':['Show','Listing','Ads'],'shared_image_type_toggle':'In situ',
    'atomic_version_and_content_identity_checks':True,'unchanged_chooser_can_close_without_discard_warning':True,
    'group_default_visibility_is_not_listing_approval_or_manufactured_identity':True,
    'current_ammonite_images_at_check':89,'large_pair_images':29,'large_pair_in_situ_images':19,
    'large_group_default_option_ids':['BSI-DA27DD604F0B','BSI-C3858B1FE67E'],
    'small_option_ids_not_in_large_defaults':['BSI-624D16148726','BSI-EFBAEB31C2B1'],
    'source_physical_specifications_or_platform_matches_inferred':False}
app['family_library']['per_component_visibility_listing_and_ads']=True
app['family_library']['shared_in_situ_toggle_preserves_component_purposes']=True
p['current_saved_specification_review'].update(last_independently_preserved_through_event=qa['live_event_cutoff'],
    latest_review_preservation_verification=rel(H/'independent-verification.json'),
    latest_review_preservation_verification_sha256=sha(H/'independent-verification.json'))
p['latest_master_metadata_change']={'status':'REGISTERED_INDEPENDENTLY_VERIFIED_APP_V2_6_0',
    'preceding_receipt':old['publication_receipt'],'source_register_core_preferred_workbook_and_gallery_bytes_unchanged':True,
    'saved_reviews_originals_versions_and_audit_history_preserved':True,
    'default_group_visibility_is_not_identity_or_listing_approval':True,
    'catalogue_identity_or_physical_specification_imports':0,'root_runtime_db_native_platform_mutations':0}
changed=[k for k in p if p[k]!=old[k]]
assert set(changed)=={'recorded_utc','publication_receipt','current_review_application','current_saved_specification_review','latest_master_metadata_change'}
updates={}
for path in controls:
    d=read(path);d.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for key in changed:
        if key in d and key not in {'recorded_utc','publication_receipt'}:d[key]=copy.deepcopy(p[key])
    updates[path]=d
if not a.apply:
    print(json.dumps({'status':'READY_APP_V2_6_METADATA_ONLY_PUBLICATION','active_options':187,'python_tests':106,
        'read_only_checks':qa['checks'],'review_rows_preserved':2012,'later_owner_events_preserved':9,
        'register_and_workbook_bytes_unchanged':True},indent=2));raise SystemExit(0)
snap=H/'publication-inputs';snap.mkdir(exist_ok=True)
for path in [pointer,*controls]:
    dest=snap/str(path.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(path,dest)
def atomic(path,doc):
    temp=path.with_name(path.name+'.component-app-publication-tmp')
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
    receipt={'status':'PUBLISHED_VERIFIED_APP_V2_6_COMPONENT_CONTROLS_REFERENCE','published_utc':now,
        'before_pointer_sha256':before[str(pointer)],'pointer_sha256':sha(pointer),'application_version':'2.6.0',
        'active_options':187,'predeployment_reviews_preserved':2012,'predeployment_events_preserved':4131,
        'later_owner_events_preserved':9,'all_controls_equal_pointer':True,'register_and_workbook_bytes_unchanged':True,
        'verification':str(H/'independent-verification.json'),'verification_sha256':sha(H/'independent-verification.json'),
        'changed_pointer_keys':changed,'root_runtime_db_native_platform_code_writes':0}
    dump(H/'publication-receipt.json',receipt)
except BaseException:
    for path in reversed(written):
        source=snap/str(path.relative_to(B)).replace('/','__');temp=path.with_name(path.name+'.component-app-rollback-tmp')
        shutil.copy2(source,temp);os.replace(temp,path)
    raise
print(json.dumps(receipt,indent=2))
