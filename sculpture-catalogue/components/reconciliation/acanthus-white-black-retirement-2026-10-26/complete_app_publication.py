"""Clear the pending app transition only after independent live/read-only checks."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,csv,hashlib,json,os,shutil,urllib.request

H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent
A=ROOT/'catalogue-review/reviews/family-gallery-types-20261026'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
dump=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
pointer=B/'current-master.json';expected='b45f6ae844f1d9a764777f65e33dfd34659c2673fe9c1a2b43dbe8f3f7b61550'
assert sha(pointer)==expected
assert not (H/'app-completion-publication-receipt.json').exists()
handoff=read(A/'HANDOFF.json');qa=read(H/'app-rebase-independent-verification.json')
assert handoff['status']=='COMPLETE_VERIFIED_LIVE_V2_4_0_AND_EXACT_PRODUCT_RETIREMENT'
assert qa['status']=='PASS_INDEPENDENT_LIVE187_AND_SOURCE_REBASE' and qa['live_active_options']==187
for group in ['application_files','evidence']:
    for path,digest in handoff[group].items():assert sha(path)==digest,path
assert sha(handoff['canonical_publication']['path'])==handoff['canonical_publication']['sha256']
assert qa['app_owner_rebase_receipt_sha256']==sha(A/'retirement-rebase.json')
export=Path(handoff['export_verification']['export_path'])
for name in ['all-product-decisions.csv','listing-drafts.csv','listing-ready.csv','specification-decisions.csv']:
    with (export/name).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==handoff['export_verification']['counts'][name]
    assert all('BSI-B0D0CCA7E318' not in str(r) for r in rows)
with urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap',timeout=15) as r:boot=json.load(r)
with urllib.request.urlopen('http://127.0.0.1:8767/api/library?family=Ammonite',timeout=20) as r:library=json.load(r)
snapshot=read(boot['source']['live_dropbox']['path'])
native={k:v for k,v in snapshot['records'].items() if v['kind']=='file' and v['path'].startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/Ammonite/')}
app={r['id']:r for r in library['images'] if r['source']=='Dropbox'}
assert set(native)==set(app) and len(native)==236
assert len({r['folder_id'] for r in native.values()})==8
assert all(app[k]['folder_id']==v['folder_id'] for k,v in native.items())
old=read(pointer);p=copy.deepcopy(old)
assert boot['source']['register_sha256']==p['register_sha256']==qa['register_sha256']
assert len(boot['products'])==187
controls=[B/path for path in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
assert all(read(f)['current_master_catalogue']==old for f in controls)
before_hashes={str(f):sha(f) for f in [pointer,*controls]}
now=datetime.now(timezone.utc).isoformat()
browser={'checked_utc':now,'method':'Read-only Chrome accessibility observation through cua_repl',
    'url':'http://127.0.0.1:8767/#BSI-B0D0CCA7E318','tab_id':'961978032','visible_active_option_count':187,
    'visible_message':"This sculpture has been removed from the active catalogue. Choose another sculpture from the left panel.",
    'other_product_opened_instead':False,'ui_or_review_mutations':0}
browser_path=H/'browser-retired-link-readback.json'
if not browser_path.exists():dump(browser_path,browser)
release={'status':'PASS_OWNER_HANDOFF_AND_INDEPENDENT_LIVE_REBASE_READBACK','checked_utc':now,
    'owner_handoff_path':str(A/'HANDOFF.json'),'owner_handoff_sha256':sha(A/'HANDOFF.json'),
    'application_files':handoff['application_files'],'app_version':'2.4.0','active_options':187,
    'owner_reported_unit_tests_passed':89,'independent_root_rebase_checks':qa['checks'],
    'root_review_values_versions_and_originals_unchanged':True,'root_preserved_historical_review_rows':18,
    'independent_ammonite_native_images':236,'independent_ammonite_app_images':236,'independent_ammonite_folders':8,
    'current_ammonite_missing_or_extra_ids':0,'ammonite_snapshot':boot['source']['live_dropbox'],
    'saved_active_export_populations_verified':handoff['export_verification']['counts'],
    'independent_retired_browser_observation':{'path':str(browser_path),'sha256':sha(browser_path)},
    'root_app_code_review_native_platform_mutations':0}
release_path=H/'app-release-independent-verification.json'
dump(release_path,release)
p.update(recorded_utc=now,status='CURRENT_MASTER187_AND_LIVE_APP_VERIFIED',
    publication_receipt=rel(H/'app-completion-publication-receipt.json'))
p['current_saved_specification_review'].update(status='CURRENT187_SAVED_REVIEWS_REBOUND_WITH_HISTORICAL188_SNAPSHOT_RETAINED',
    current_register_sha256=p['register_sha256'],latest_rebase_verification=rel(H/'app-rebase-independent-verification.json'),
    latest_rebase_verification_sha256=sha(H/'app-rebase-independent-verification.json'),
    last_independently_preserved_through_event=qa['event_cutoff_at_readback'],current_active_options=187)
appref=p['current_review_application']
appref['preceding_validation_reference']={k:old['current_review_application'][k] for k in ['version','verification','verification_sha256','last_verified_utc','ui_revision'] if k in old['current_review_application']}
appref.update(status='LOCAL_REVIEW_APP_V2_4_0_CURRENT187_SOURCE_REBASE_VERIFIED',version='2.4.0',last_verified_utc=now,
    verification=str(release_path),verification_sha256=sha(release_path),contract_sha256=sha(ROOT/'catalogue-review/README.md'),
    source_register_sha256=p['register_sha256'],source_gallery_sha256=qa['gallery_sha256'],
    ui_revision='family-native-folder-gallery-multiple-image-types-and-retired-link-notice',
    verification_scope='Nine application file hashes and owner handoff verified; live187 IDs/source binding, source-only1839-event rebase,1857 durable reviews,18 retired-history rows,236 native/app Ammonite images and eight actual folders independently checked.',
    owning_thread_handoff=str(A/'HANDOFF.json'),owning_thread_handoff_sha256=sha(A/'HANDOFF.json'))
appref['source_coverage']['historical_source_coverage_scope_options']=appref['source_coverage'].get('products',188)
appref['source_coverage']['current_active_option_source_binding']={'products':187,'register_sha256':p['register_sha256'],
    'verification':str(H/'app-rebase-independent-verification.json'),'sha256':sha(H/'app-rebase-independent-verification.json')}
appref['canonical_source_transition'].update(status='COMPLETE_SOURCE_ONLY_REBASE_WITH_REVIEW_DATA_PRESERVED',
    rebase_receipt=str(A/'retirement-rebase.json'),rebase_receipt_sha256=sha(A/'retirement-rebase.json'),
    verification=rel(H/'app-rebase-independent-verification.json'),verification_sha256=sha(H/'app-rebase-independent-verification.json'),
    active_options=187,rebound_source_bindings=1839,historical_review_rows_preserved=18,
    all_values_originals_and_versions_preserved=True)
appref['release_validation'].update(unit_tests=89,owner_tests_not_rerun_by_root=True)
appref['saved_review_snapshot']={'event_cutoff':qa['event_cutoff_at_readback'],'review_rows':qa['review_rows_at_readback'],
    'review_values_versions_originals_preserved':True,'source_binding_events_only':1839,'historical_rows_unchanged':18,
    'app_review_writes_by_catalogue_publisher':0,'owner_may_continue_reviewing':True}
appref['family_library']={'url':'http://127.0.0.1:8767/#library?family=Ammonite','current_native_folder_filters':True,
    'image_types_support_multiple_values':True,'card_type_dropdown_autosaves':True,'uncategorised_review_queue':True,
    'owner_image_purpose_and_source_qualification_remain_separate':True}
p['next_catalogue_actions']=old['next_catalogue_actions'][1:]
p['latest_master_metadata_change']={'status':'CURRENT187_APP_SOURCE_REBASE_COMPLETED_AND_VERIFIED',
    'preceding_receipt':old['publication_receipt'],'register_and_workbook_bytes_unchanged':True,
    'app_review_data_originals_and_versions_preserved':True,'root_runtime_review_native_platform_mutations':0,
    'verification':rel(release_path),'verification_sha256':sha(release_path)}
changed=[k for k in p if p[k]!=old[k]]
updates={}
for path in controls:
    d=read(path);d.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for key in changed:
        if key in d and key not in {'recorded_utc','status','publication_receipt'}:d[key]=copy.deepcopy(p[key])
    updates[path]=d
if not args.apply:
    print(json.dumps({'status':'READY_VERIFIED_APP_COMPLETION_PUBLICATION','version':'2.4.0','active_options':187,
        'source_binding_only_events':1839,'root_checks':qa['checks'],'pending_rebase_cleared':True},indent=2));raise SystemExit(0)
snap=H/'app-completion-inputs';snap.mkdir(exist_ok=True)
for path in [pointer,*controls]:
    dest=snap/str(path.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(path,dest)
def atomic(path,doc):
    temp=path.with_name(path.name+'.app-retirement-complete-tmp')
    with temp.open('w') as f:json.dump(doc,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
written=[]
try:
    assert all(sha(f)==before_hashes[str(f)] for f in [pointer,*controls])
    for path,doc in updates.items():atomic(path,doc);written.append(path)
    assert all(read(path)['current_master_catalogue']==p for path in controls)
    atomic(pointer,p);written.append(pointer)
    assert read(pointer)==p and all(read(path)['current_master_catalogue']==p for path in controls)
    assert sha(B/p['register'])==p['register_sha256'] and sha(B/p['workbook'])==p['workbook_sha256']
    assert sha(B/p['preferred_review_workbook'])==p['current_comprehensive_workbook']['sha256']
    receipt={'status':'PUBLISHED_VERIFIED_CURRENT187_AND_APP_COMPLETION','published_utc':now,
        'before_pointer_sha256':expected,'pointer_sha256':sha(pointer),'register_sha256':p['register_sha256'],
        'app_version':'2.4.0','active_options':187,'retained_history_options':189,'retired_history_options':2,
        'all_controls_equal_pointer':True,'source_register_and_workbook_bytes_unchanged':True,
        'release_verification':str(release_path),'release_verification_sha256':sha(release_path),
        'root_rebase_verification_sha256':sha(H/'app-rebase-independent-verification.json'),
        'app_transition_complete':True,'root_review_db_code_native_platform_mutations':0,
        'control_hashes':{str(path):sha(path) for path in controls},'changed_pointer_keys':changed}
    dump(H/'app-completion-publication-receipt.json',receipt)
except BaseException:
    for path in reversed(written):
        source=snap/str(path.relative_to(B)).replace('/','__');temp=path.with_name(path.name+'.app-retirement-rollback-tmp')
        shutil.copy2(source,temp);os.replace(temp,path)
    raise
print(json.dumps(receipt,indent=2))
