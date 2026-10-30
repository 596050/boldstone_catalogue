"""Publish an availability overlay and annotated workbook; preserve review sources."""
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
rel=lambda p:str(Path(p).relative_to(B))
parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=Path,required=True);args=parser.parse_args()
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.availability-publication-tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
inputs=read(args.inputs)
pointer=B/'current-master.json'
assert sha(pointer)=='7d736342277e040da4423ce6113553e230f582f2e238bb5916d1df44fa37057f'
old=read(pointer);overlay=read(H/'availability-overlay.json')
assert sha(H/'availability-overlay.json')=='bd0635e88a9bbb28b7db2f78f484d6fce2f214fe3d9eb8f59ad755debfe13c02'
assert old['register_sha256']==overlay['baseline_register_sha256']
validation=read(inputs['workbook_validation']['path'])
assert sha(inputs['workbook_validation']['path'])==inputs['workbook_validation']['sha256']
assert validation['status'].startswith('PASS_')
assert validation['source_workbook_sha256']==old['current_comprehensive_workbook']['sha256']
assert validation['overlay_sha256']==sha(H/'availability-overlay.json')
workbook=Path(inputs['workbook']['path'])
assert sha(workbook)==inputs['workbook']['sha256']==validation['output_workbook_sha256']
assert workbook.name=='Boldstone_Wall_Sculptures_Unified_2026-10-25_v3.xlsx'
handoff=Path(inputs['workbook_handoff']['path']);assert sha(handoff)==inputs['workbook_handoff']['sha256']
qa_path=Path(inputs['app_verification']['path']);assert sha(qa_path)==inputs['app_verification']['sha256'];qa=read(qa_path)
assert qa['status'].startswith('PASS_')
for name,digest in qa['code_hashes'].items():
    f=Path(name);f=f if f.is_absolute() else APP/f
    assert sha(f)==digest,str(f)
for name,digest in qa.get('evidence',{}).items():assert sha(name)==digest,name
assert qa['native_calls_performed']==0 and not qa['qa_database_promoted']
assert qa['saved_review_event_cutoff_preserved']==345 and qa['saved_review_records_preserved']==307
assert qa['decowaves']=={'component_count':4,'design_group_count':2,'option_count':6,'white_entries_missing':0}
for name,digest in qa['canonical_sources_unchanged'].items():assert sha(name)==digest,name
with urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=10)as response:
    health=json.load(response);assert response.status==200
assert health['products']==188
readers=read(H/'reader-verification.json')
assert readers['status']=='PASS_NATIVE_AVAILABILITY_READERS'
for name,digest in readers['outputs'].items():assert sha(name)==digest,name
protected={}
for k in ['register','workbook']:
    f=B/old[k];assert sha(f)==old[k+'_sha256'];protected[str(f)]=sha(f)
for k in ['current_asset_reference_map','current_native_reference_map']:
    f=B/old[k]['path'];assert sha(f)==old[k]['sha256'];protected[str(f)]=sha(f)
f=B/old['preferred_review_workbook'];assert sha(f)==old['current_comprehensive_workbook']['sha256'];protected[str(f)]=sha(f)
protected[overlay['gallery_database']]=overlay['gallery_database_sha256']
controls=[B/x for x in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
for f in controls:assert read(f)['current_master_catalogue']==old
snap=H/'publication-inputs';snap.mkdir(exist_ok=True);snapshots={}
for f in [pointer,*controls]:
    dest=snap/str(f.relative_to(B)).replace('/','__');assert not dest.exists();shutil.copy2(f,dest);snapshots[f]=dest
now=datetime.now(timezone.utc).isoformat();OUT=B/'outputs/acanthus-native-availability-2026-10-25'
availability={'status':'FIVE_OWNER_CONFIRMED_NATIVE_DELETIONS_RECONCILED',
    'path':rel(H/'availability-overlay.json'),'sha256':sha(H/'availability-overlay.json'),
    'review':rel(OUT/'index.html'),'all_options_review':rel(OUT/'all-options.html'),
    'current_native_files':rel(OUT/'Current_Native_Files_6355.csv'),
    'deleted_native_history':rel(OUT/'Confirmed_Native_Deletions_5.csv'),
    'review_event_cutoff':overlay['review_event_cutoff'],'counts':overlay['counts'],
    'baseline_register_sha256':old['register_sha256'],
    'historical_ids_records_and_source_photo_proof_retained':True,
    'replacement_primary_selections':0,'physical_verifications':0,
    'scope':overlay['scope']}
p=copy.deepcopy(old)
p.update(recorded_utc=now,status='CURRENT_MASTER188_WITH_SCOPED_NATIVE_IMAGE_AVAILABILITY',
    current_native_availability=availability,
    current_effective_native_inventory={**overlay['counts'],'scope':overlay['scope']},
    publication_receipt=rel(H/'publication-receipt.json'))
for k in ['current_asset_reference_map','current_native_reference_map']:
    p[k]['native_availability_overlay']={'path':availability['path'],'sha256':availability['sha256']}
    p[k]['underlying_map_is_a_retained_snapshot']=True
p['current_published_gallery_projection'].update(
    status='RETAINED_SOURCE_GALLERY_WITH_VERIFIED_NATIVE_AVAILABILITY_OVERLAY',
    native_availability_overlay={'path':availability['path'],'sha256':availability['sha256']},
    native_file_count_scope='Gallery source counts retain the original snapshot; the availability overlay subtracts the five confirmed deletions. General review decisions are not imported.')
p['current_complete_gallery_mapping']['native_availability_overlay']=copy.deepcopy(availability)
oldbook=copy.deepcopy(old['current_comprehensive_workbook'])
book=copy.deepcopy(oldbook)
book.update(status='CONSOLIDATED_SOURCE_WORKBOOK_WITH_CONFIRMED_NATIVE_AVAILABILITY',
    path=rel(workbook),sha256=sha(workbook),sheets=validation['output_sheet_count'],
    native_hyperlinks=validation['output_hyperlinks'],
    source_seal=rel(handoff),source_seal_sha256=sha(handoff),
    native_availability_overlay={'path':availability['path'],'sha256':availability['sha256']},
    native_availability_review_event_cutoff=overlay['review_event_cutoff'],
    preceding_workbook=oldbook,
    current_native_availability_source_scope=overlay['scope'],
    original_source_snapshot_counts=copy.deepcopy(oldbook['counts']))
book['counts']['current_wall_files']=6355
book['counts']['confirmed_deleted_files_retained_as_history']=5
book['counts']['source_snapshot_wall_files']=6360
p['current_comprehensive_workbook']=book;p['preferred_review_workbook']=rel(workbook)
links=p['current_image_review_links']
links['captured_source_review_before_native_deletions']=old['current_image_review_links']['all_links']
links.update(all_links=availability['all_options_review'],
    current_native_availability=availability['review'],
    all_individual_option_galleries=availability['all_options_review'],
    complete_current_wall_images=availability['current_native_files'],
    all_catalogue_and_source_inventories_workbook=str(workbook),
    single_wall_sculptures_sheet_workbook=str(workbook))
p['current_guided_image_review']['terminal_review_command']=rel(H/'walkthrough.py')
p['current_guided_image_review']['native_availability_overlay']=copy.deepcopy(availability)
app=copy.deepcopy(old['current_review_application'])
app['preceding_validation_reference']={k:app[k]for k in ['version','last_verified_utc','verification','verification_sha256','ui_revision']if k in app}
app.update(status='LOCAL_REVIEW_APP_FAMILY_OVERVIEW_VERIFIED',last_verified_utc=now,
    version=health['version'],ui_revision='family-navigation-design-aware-white-checklist-20261025',
    verification=str(qa_path.resolve()),verification_sha256=sha(qa_path),
    contract_sha256=sha(APP/'README.md'),verification_scope=qa.get('scope',qa.get('validation_scope')),
    family_review={'family_grouped_selector':True,'family_overview':True,
        'retained_component_records_separate_from_working_design_groups':True,
        'white_coverage_uses_explicit_published_design_equivalence':True,
        'grouping_transfers_images_specifications_or_platform_records':False,
        'fewer_than_two_tagged_in_situ_images_flagged':True,
        'in_situ_tag_counts_do_not_certify_real_installations':True,
        'image_totals_distinguish_assigned_and_related_sources':True},
    release_validation={'unit_tests':qa['unit_tests'],'qa_browser_checks':qa['qa_browser_checks'],
        'live_read_only_browser_checks':qa['live_readonly_browser_checks'],
        'design_group_live_browser_checks':qa['design_group_live_browser_checks']})
app['reviewed_native_file_deletion']['known_reconciled_receipt_scope']={
    'native_files':5,'review_event_cutoff':overlay['review_event_cutoff'],
    'availability_overlay':availability['path'],'scope':'Owner-confirmed app deletion receipts only; no additional native write by the catalogue publisher.'}
p['current_review_application']=app
p['latest_master_metadata_change']={'status':'NATIVE_AVAILABILITY_V3_WORKBOOK_AND_FAMILY_APP_REFERENCE',
    'preceding_receipt':old['publication_receipt'],
    'source_register_core_workbook_maps_and_gallery_bytes_unchanged':True,
    'general_review_choice_imports':0,'publisher_native_mutations':0}
allowed={'recorded_utc','status','current_native_availability','current_effective_native_inventory','publication_receipt',
    'current_asset_reference_map','current_native_reference_map','current_published_gallery_projection',
    'current_complete_gallery_mapping','current_comprehensive_workbook','preferred_review_workbook',
    'current_image_review_links','current_guided_image_review','current_review_application','latest_master_metadata_change'}
assert all(p[k]==old[k]for k in old if k not in allowed)
updates={}
for f in controls:
    value=read(f);value.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for k in allowed-{'recorded_utc','status','publication_receipt'}:
        if k in p:value[k]=copy.deepcopy(p[k])
    updates[f]=value
try:
    for f,snapshot in snapshots.items():assert sha(f)==sha(snapshot)
    for f,digest in protected.items():assert sha(f)==digest,f
    assert sha(qa_path)==inputs['app_verification']['sha256']
    for name,digest in qa['code_hashes'].items():
        f=Path(name);f=f if f.is_absolute()else APP/f;assert sha(f)==digest,str(f)
    for f,value in updates.items():write(f,value)
    write(pointer,p)
    assert read(pointer)==p
    for f in controls:assert read(f)['current_master_catalogue']==p
    assert all(sha(f)==digest for f,digest in protected.items())
    receipt={'status':'PASS_SCOPED_NATIVE_AVAILABILITY_AND_V3_WORKBOOK_PUBLISHED',
        'recorded_utc':now,'pointer_sha256':sha(pointer),'preceding_pointer_sha256':sha(snapshots[pointer]),
        'overlay_sha256':availability['sha256'],'review_event_cutoff':overlay['review_event_cutoff'],
        'source_register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],
        'preferred_workbook_path':str(workbook),'preferred_workbook_sha256':sha(workbook),
        'deleted_native_files':5,'affected_master_examples':1,'active_options':188,
        'replacement_primaries_selected_by_publication':0,'general_review_choices_imported':0,
        'publisher_native_mutations':0,'publisher_active_review_db_writes':0,
        'protected_source_files_unchanged':protected,
        'controls_sha256':{str(f):sha(f)for f in controls},
        'app_verification_sha256':sha(qa_path),'workbook_validation_sha256':sha(inputs['workbook_validation']['path'])}
    write(H/'publication-receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items()if k not in ['protected_source_files_unchanged','controls_sha256']},ensure_ascii=False,indent=2))
except BaseException:
    for f,snapshot in snapshots.items():shutil.copy2(snapshot,f)
    raise
