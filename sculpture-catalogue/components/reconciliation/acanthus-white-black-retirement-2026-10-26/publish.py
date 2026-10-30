"""Guarded publication: controls first, canonical pointer last, with rollback."""
from pathlib import Path
from datetime import datetime, timezone
import argparse,copy,hashlib,json,os,shutil

H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
dump=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');a=parser.parse_args()
manifest=read(H/'input-manifest.json');outputs=read(H/'output-manifest.json');qa=read(H/'saved-output-verification.json')
delta=read(H/'SOURCE_READY_FOR_APP_REBASE.json');wqa=read(H/'saved-workbook-verification.json')
assert qa['status']=='PASS_CURRENT187_SAVED_OUTPUTS' and wqa['status']=='PASS'
assert qa['output_manifest_sha256']==sha(H/'output-manifest.json')
assert qa['workbook_verification_sha256']==sha(H/'saved-workbook-verification.json')
assert delta['new_register_sha256']==sha(H/'canonical-master-register.json')=='1774c391792a5ccb7c65c4d4c6ba48b32f5956278de02e5ca5354b9e7c611c58'
assert sha(delta['unchanged_gallery_database'])==delta['unchanged_gallery_sha256']
assert not (H/'publication-receipt.json').exists(),'Already published; use independent readback'
for r in manifest.values():assert sha(r['path'])==sha(r['snapshot'])==r['sha256'],r['path']
for f,digest in outputs['outputs'].items():assert sha(f)==digest,f
old=read(manifest['pointer']['snapshot']);g=read(H/'canonical-master-register.json');summary=outputs['summary'];out=Path(outputs['output_directory'])
workbooks={r['key']:r for r in wqa['workbooks']}
for w in workbooks.values():assert sha(w['output'])==w['sha256']
controls=[Path(manifest[k]['path']) for k in ['specification_control','component_checkpoint','root_checkpoint']]
assert all(read(f)['current_master_catalogue']==old for f in controls)
now=datetime.now(timezone.utc).isoformat()
def file_ref(path):return {'path':str(path),'sha256':sha(path)}
package={'schema':'boldstone.current187-publication-package/v1','status':'VERIFIED_CURRENT187_LOCAL_CATALOGUE',
    'created_utc':now,'active_options':187,'retained_history_options':189,'retired_history_options':2,
    'source_register':file_ref(H/'canonical-master-register.json'),'workbook':file_ref(workbooks['comprehensive_workbook']['output']),
    'core_workbook':file_ref(workbooks['core_workbook']['output']),'catalogue_csv':file_ref(out/'Current_Individual_Options_187.csv'),
    'listing_treatments_csv':file_ref(out/'Active_Listing_Treatments_187.csv'),'review':str(out/'index.html'),
    'output_verification':file_ref(H/'saved-output-verification.json'),'workbook_verification':file_ref(H/'saved-workbook-verification.json'),
    'source_assertions_preserved':1668,'native_platform_and_review_writes_by_publisher':0,
    'historical_188_package':old['current_listing_treatment_plan']['package']}
package_path=H/'CATALOGUE_PACKAGE.json'
if package_path.exists():
    prior=read(package_path);package['created_utc']=prior['created_utc'];assert package==prior
else:dump(package_path,package)
current_package={**file_ref(package_path),'review':str(out/'index.html'),'workbook':package['workbook'],
    'catalogue_csv':package['catalogue_csv'],'listing_treatments_csv':package['listing_treatments_csv'],
    'validation':{'status':'PASS_CURRENT187_SAVED_OUTPUTS','checks_passed':qa['checks'],'active_options':187,
        'new_physically_verified_specifications':0,'platform_writes':0}}
p=copy.deepcopy(old)
p.setdefault('historical_master_publications',[]).append({'pointer':rel(H/'inputs/pointer.json'),'pointer_sha256':manifest['pointer']['sha256'],
    'register':old['register'],'register_sha256':old['register_sha256'],'workbook':old['workbook'],
    'workbook_sha256':old['workbook_sha256'],'preferred_workbook':old['preferred_review_workbook']})
p.update(recorded_utc=now,status='CURRENT_MASTER187_EXACT_OWNER_RETIREMENT_APP_REBASE_PENDING',
    register=rel(H/'canonical-master-register.json'),register_sha256=sha(H/'canonical-master-register.json'),
    workbook=rel(workbooks['core_workbook']['output']),workbook_sha256=workbooks['core_workbook']['sha256'],
    preferred_review_workbook=rel(workbooks['comprehensive_workbook']['output']),summary=copy.deepcopy(g['summary']),
    current_option_count=187,retained_option_count=189,retired_option_count=2,
    latest_catalogue_retirement=copy.deepcopy(g['latest_catalogue_retirement']),
    publication_receipt=rel(H/'publication-receipt.json'))
p['latest_corrections']=old['latest_corrections']+'; Exact White and Black Two Leaves option retired from current187 catalogue;189 history records preserved.'
p['latest_master_metadata_change']={'status':'EXACT_OWNER_RETIREMENT_PUBLISHED',
    'option_id':delta['option_id'],'preceding_receipt':old['publication_receipt'],'other_option_objects_unchanged':188,
    'source_assertions_preserved':1668,'root_native_platform_and_app_review_writes':0}
p['historical_current_individual_sculpture_list']=old['current_individual_sculpture_list']
p['current_individual_sculpture_list']={'recorded_utc':now,'status':'CURRENT187_WORKING_CATALOGUE',
    'register':p['register'],'register_sha256':p['register_sha256'],'workbook':p['workbook'],'workbook_sha256':p['workbook_sha256'],
    'publication_receipt':p['publication_receipt'],'summary':copy.deepcopy(g['summary']),'customisable_records':187,
    'count_definition':g['count_definition'],'unbounded_custom_requests_are_not_enumerated_records':True,
    'physical_stock_verified':False,'current_option_list':rel(out/'Current_Individual_Options_187.csv'),
    'current_option_list_sha256':sha(out/'Current_Individual_Options_187.csv'),'count_summary':rel(out/'current-count-summary.json'),
    'count_summary_sha256':sha(out/'current-count-summary.json'),'retained_option_rows':189,'retired_option_rows':2,
    'retained_component_id_records':112,'grouped_working_design_identities':110}
p['historical_current_listing_population']=old['current_listing_population']
p['current_listing_population']={'status':'CURRENT187_LOCAL_TREATMENTS; NATIVE_PLATFORM_EXECUTION_NOT_PERFORMED',
    'catalogue_options':187,'working_field_groups':1122,'retired_option_history':2,
    'listing_treatments':summary['listing_treatments'],'review':rel(out/'listing-treatments.html'),'platform_writes':0}
p['historical_current_local_draft_completion']=old['current_local_draft_completion']
p['current_local_draft_completion']={'status':'CURRENT187_LOCAL_LISTING_PLAN_WITH_RETIRED_OPTION_EXCLUDED',
    'active_options':187,'platform_execution':False,'review':rel(out/'listing-treatments.html'),
    'latest_complete_listing_plan':current_package,'new_native_drafts_or_variant_assignments':0}
p['current_listing_treatment_plan']={'status':'CURRENT187_LOCAL_LISTING_TREATMENT_NOT_NATIVE_MATCH_CERTIFICATE',
    'register':str(H/'listing-treatment-register.json'),'register_sha256':sha(H/'listing-treatment-register.json'),
    'package':current_package,'summary':{'active_option_count':187,'working_design_groups':110,'working_specification_fields':1122,
        'listing_treatments':summary['listing_treatments'],'primary_references':summary['individual_source_statuses'],
        'owner_held_installation_gaps':22,'owner_held_series_gaps':1,'retired_local_treatments':2,'platform_writes':0},
    'existing_source_edges_unchanged':True,'native_execution_allowed':False,
    'historical_summary_before_retirement':old['current_listing_treatment_plan']['summary']}
p['historical_current_specification_verification']=old['current_specification_verification']
p['current_specification_verification']={**old['current_specification_verification'],
    'path':rel(H/'saved-output-verification.json'),'sha256':sha(H/'saved-output-verification.json'),
    'review':rel(out/'specifications-to-verify.html'),'field_checklist':rel(out/'Specification_Verification_Checklist_1122_Fields.csv'),
    'selling_details':rel(out/'all-options.html'),'current_option_rows':187,'current_field_rows':1122,
    'working_estimated_prices':186,'retained_historical_field_rows':1134,
    'actual_physical_measurement_input':rel(out/'Physical_Verification_Input_187_Options.csv'),
    'current_listing_package':current_package,'current_working_proposals':rel(out/'specifications-to-verify.html'),
    'remaining_face_and_base_material_checks':rel(out/'specifications-to-verify.html'),
    'current_depth_estimates':rel(out/'specifications-to-verify.html'),
    'new_physical_measurements_added':0,'new_physical_verifications':0}
p['historical_current_missing_picture_lists']=old['current_missing_picture_lists']
p['current_missing_picture_lists']={'status':'OWNER_HOLDS_AND_REFERENCE_QUALIFICATIONS_RETAINED',
    'coverage':rel(out/'Photo_Coverage_187.csv'),'active_individual_source_requests':0,'active_in_situ_source_requests':0,
    'active_series_source_requests':0,'individual_gaps':0,'technical_individual_gaps':11,
    'owner_accepted_group_or_combined_reference_exceptions':10,'separate_individual_photographs_required':0,
    'owner_held_in_situ_cases':22,'owner_held_series_cases':1,'optional_series_requirements':summary['optional_series_references'],
    'technical_individual_references':rel(out/'Technical_Individual_References_11.csv'),
    'held_in_situ_cases_csv':rel(out/'Held_In_Situ_Cases_22.csv'),'held_series_cases_csv':rel(out/'Held_Series_Cases_1.csv'),
    'active_individual_requests_csv':rel(out/'Active_Individual_Photograph_Requests_0.csv'),
    'active_in_situ_requests_csv':rel(out/'Active_In_Situ_Photograph_Requests_0.csv'),
    'active_series_requests_csv':rel(out/'Active_Series_Photograph_Requests_0.csv'),
    'optional_series_images':rel(out/('Optional_Series_Images_'+str(summary['optional_series_references'])+'.csv')),
    'native_absent_source_references':rel(out/'Native_Absent_Source_References.csv'),
    'native_absence_does_not_reopen_owner_held_photograph_tasks':True,'retired_option_actions_excluded':True}
p['historical_image_review_links'].append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links']={'all_links':rel(out/'all-options.html'),'all_individual_option_galleries':rel(out/'all-options.html'),
    'historical_saved_app_specification_review':old['current_saved_specification_review']['report'],
    'current_working_specification_review':rel(out/'specifications-to-verify.html'),
    'photograph_checklist':rel(out/'photograph-checklist.html'),'missing_in_situ_images':rel(out/'photograph-checklist.html'),
    'missing_series_images':rel(out/'photograph-checklist.html'),'individual_image_gaps':rel(out/'photograph-checklist.html'),
    'retired_options':rel(out/'retired-history.html'),'current_local_draft_projections':rel(out/'listing-treatments.html'),
    'actual_physical_measurement_input':rel(out/'Physical_Verification_Input_187_Options.csv'),
    'specifications_to_verify':rel(out/'specifications-to-verify.html'),'selling_details':rel(out/'all-options.html'),
    'complete_current_wall_images':rel(out/('Current_Wall_Images_'+str(summary['native_snapshot']['images'])+'.csv')),
    'working_design_groups':rel(out/'Current_Working_Design_Groups_110.csv'),
    'verification':rel(H/'saved-output-verification.json'),'verification_sha256':sha(H/'saved-output-verification.json'),
    'counts':{'current_options':187,'qualified_field_rows':1122,'technical_individual_gaps':11,'held_in_situ_cases':22,
        'held_series_cases':1,'active_individual_source_requests':0,'active_in_situ_requests':0,'active_series_requests':0,
        'optional_series_references':summary['optional_series_references']}}
snapshot=summary['native_snapshot'];native_ref={'status':'APP_NATIVE_SYNC_SNAPSHOT_WITH_SCOPED_RETIREMENT_READBACK',
    'path':rel(H/'current-native-overlay.json'),'sha256':sha(H/'current-native-overlay.json'),'source_snapshot':snapshot,
    'counts':{'current_images':snapshot['images'],'folders_including_root':snapshot['folders_including_root'],
        'exact_retired_owned_native_ids_absent':4},'current_navigation_uses_stable_file_and_folder_ids':True,
    'base_source_maps_are_retained_history':True,'independent_full_native_rescan_by_root':False}
p['historical_current_native_availability']=old['current_native_availability']
p['current_native_availability']={**native_ref,'review':rel(out/'photograph-checklist.html'),
    'all_options_review':rel(out/'all-options.html'),'current_native_files':p['current_image_review_links']['complete_current_wall_images'],
    'retirement_readback':rel(H/'native-readback.json'),'retirement_readback_sha256':sha(H/'native-readback.json'),
    'scope':'Immutable app sync generation20; exact retired folder and three files independently NOT_FOUND. No replacement primary or identity inferred.'}
p['current_live_native_inventory']=native_ref
p['current_effective_native_inventory']={**native_ref['counts'],'source_snapshot':snapshot,'scope':p['current_native_availability']['scope']}
for key in ['current_asset_reference_map','current_native_reference_map']:
    p[key]['native_availability_overlay']={'path':native_ref['path'],'sha256':native_ref['sha256']}
    p[key]['current_live_navigation']=copy.deepcopy(native_ref);p[key]['underlying_map_is_a_retained_snapshot']=True
for key in ['current_published_gallery_projection','current_complete_gallery_mapping']:
    p[key]['current_live_native_inventory']=copy.deepcopy(native_ref)
    p[key]['native_availability_overlay']={'path':native_ref['path'],'sha256':native_ref['sha256']}
p['historical_current_comprehensive_workbook']=old['current_comprehensive_workbook']
p['current_comprehensive_workbook']={'status':'VERIFIED_CURRENT187_WITH_RETIRED_HISTORY_AND_PRESERVED_SOURCE_TABLES',
    'path':p['preferred_review_workbook'],'sha256':workbooks['comprehensive_workbook']['sha256'],
    'active_options':187,'retained_option_records':189,'sheets':23,'verification':rel(H/'saved-workbook-verification.json'),
    'verification_sha256':sha(H/'saved-workbook-verification.json'),'native_availability_sheet_is_an_earlier_snapshot':True,
    'later_verified_native_navigation':native_ref,'later_native_review':rel(out/'photograph-checklist.html')}
p['latest_workbook_validation']={'status':'PASS_SAVED_CURRENT187_WORKBOOKS','path':rel(H/'saved-workbook-verification.json'),
    'sha256':sha(H/'saved-workbook-verification.json'),'existing_hyperlinks_preserved':56849,
    'source_cells_and_links_checked':478528,'unexpected_source_changes':0}
p['current_guided_image_review']={**old['current_guided_image_review'],
    'terminal_review_command':rel(H/'walkthrough.py'),'terminal_review_command_sha256':sha(H/'walkthrough.py'),
    'current_review':rel(out/'photograph-checklist.html'),'native_availability_overlay':p['current_native_availability'],
    'native_refresh_does_not_reopen_owner_held_photograph_requests':True}
p['current_working_design_group_projection']=copy.deepcopy(g['current_working_design_group_projection'])
p['current_saved_specification_review']['historical_original_review_scope_options']=188
p['current_saved_specification_review']['status']='HISTORICAL188_SAVED_REVIEWS_RETAINED; CURRENT187_APP_BINDING_PENDING'
p['current_saved_specification_review']['current_active_options']=187
p['current_saved_specification_review']['retired_review_rows_remain_historical']=True
p['current_saved_specification_review']['current_navigation_review']=rel(out/'all-options.html')
p['current_saved_specification_review']['historical_report_may_contain_retired_option']=True
p['next_catalogue_actions']=[
    'Complete the owning app session guarded source rebase to the published187-option register, preserving review data, versions and retired history.',
    'Use current187-option readers and current actual-folder links; keep22 in situ and1 series owner holds until resumed.',
    'Enter actual dimensions/depth, bare-panel weight, maker material and fitted-fixing inspection when available; accepted working estimates stay qualified.',
    'Do not create or publish Acanthus Two Leaves - White and Black. Related Bronze offer O069 is preserved; no exact live White and Black platform offer is bound.']
p['current_review_application']['canonical_source_transition']={
    'status':'PUBLISHED187_SOURCE_AWAITING_OWNING_APP_SESSION_REBASE','new_source_register':str(H/'canonical-master-register.json'),
    'new_source_register_sha256':p['register_sha256'],'old_app_source_register_sha256':old['register_sha256'],
    'source_ready_packet':str(H/'SOURCE_READY_FOR_APP_REBASE.json'),'source_ready_packet_sha256':sha(H/'SOURCE_READY_FOR_APP_REBASE.json'),
    'owning_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','app_runtime_or_review_database_mutations_by_root':0}
p['current_review_application']['version_observed_during_publication_preparation']='2.4.0'
assert p['all_actual_specifications_complete'] is False and p['exact_platform_matches_not_upgraded'] is True
changed=[k for k in p if p.get(k)!=old.get(k)]
updates={}
for path in controls:
    d=read(path);d.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p))
    for key in changed:
        if key not in {'recorded_utc','status','publication_receipt'} and key in d:d[key]=copy.deepcopy(p[key])
    updates[path]=d
def atomic(path,doc):
    path=Path(path);tmp=path.with_name(path.name+'.retirement-publish-tmp')
    with tmp.open('w') as f:json.dump(doc,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
if not a.apply:
    dump(H/'publication-plan.json',{'status':'READY_GUARDED_CURRENT187_PUBLICATION','before_pointer_sha256':manifest['pointer']['sha256'],
        'register_sha256':p['register_sha256'],'active_options':187,'retained_options':189,'changed_pointer_keys':changed,
        'app_rebase_pending':True,'controls_first_pointer_last':True})
    print(json.dumps({'status':'READY_GUARDED_CURRENT187_PUBLICATION','active_options':187,'register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],'comprehensive_workbook_sha256':p['current_comprehensive_workbook']['sha256']},indent=2));raise SystemExit(0)
pointer=Path(manifest['pointer']['path']);written=[]
try:
    for r in manifest.values():assert sha(r['path'])==r['sha256'],'Input moved before apply '+r['path']
    for path,doc in updates.items():atomic(path,doc);written.append(path)
    assert all(read(path)['current_master_catalogue']==p for path in controls)
    atomic(pointer,p);written.append(pointer)
    assert read(pointer)==p and all(read(path)['current_master_catalogue']==p for path in controls)
    for key in ['register','core_workbook','comprehensive_workbook']:
        r=manifest[key];assert sha(r['path'])==r['sha256'],'Historical input modified'
    receipt={'status':'PUBLISHED_CURRENT187_EXACT_OWNER_RETIREMENT','published_utc':now,'pointer':str(pointer),
        'pointer_sha256':sha(pointer),'previous_pointer_sha256':manifest['pointer']['sha256'],
        'register':str(H/'canonical-master-register.json'),'register_sha256':p['register_sha256'],
        'active_options':187,'retained_option_records':189,'retired_option_records':2,
        'workbooks':workbooks,'package':current_package,'output_manifest_sha256':sha(H/'output-manifest.json'),
        'control_hashes':{str(path):sha(path) for path in controls},'controls_equal_pointer':True,
        'historical_input_bytes_preserved':True,'other_option_objects_unchanged':188,
        'app_source_rebase_status':'WAITING_FOR_OWNING_APP_SESSION','root_app_review_native_platform_writes':0,
        'changed_pointer_keys':changed}
    dump(H/'publication-receipt.json',receipt)
except BaseException:
    for path in reversed(written):
        entry=next(r for r in manifest.values() if Path(r['path'])==path)
        tmp=path.with_name(path.name+'.retirement-rollback-tmp');shutil.copy2(entry['snapshot'],tmp);os.replace(tmp,path)
    raise
print(json.dumps({k:receipt[k] for k in ['status','pointer_sha256','register_sha256','active_options','retained_option_records','retired_option_records','controls_equal_pointer','app_source_rebase_status']},indent=2))
