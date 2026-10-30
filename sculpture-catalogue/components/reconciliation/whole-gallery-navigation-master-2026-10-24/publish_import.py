"""Publish the checked whole-gallery master with guarded, reversible local writes."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
now = lambda: datetime.now(timezone.utc).isoformat()
def write(p, data):
    p = Path(p)
    temp = p.with_name(p.name+'.whole-gallery-tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    os.replace(temp,p)

assert not (H/'publication-receipt.json').exists(), 'Already published; read the existing receipt'
manifest = read(H/'input-manifest.json')
old = read(manifest['pointer']['snapshot'])
g = read(H/'canonical-master-register.json')
v = read(H/'saved-workbook-verification.json')
d = read(H/'final-data-readback.json')
r = read(H/'report-verification.json')
out = Path(r['output_directory'])
assert v['status'] == d['status'] == 'PASS'
assert not v['failures'] and not d['failures'] and not r['failures']
assert r['status'] == 'PASS_CURRENT_REPORTS'
for key,name in [('workbook_sha256','master-workbook.pending'),('register_sha256','canonical-master-register.json'),('audit_sha256','image-coverage-current.json')]:
    assert v[key] == d[key] == sha(H/name), key
assert r['register_sha256'] == v['register_sha256'] and r['audit_sha256'] == v['audit_sha256']
for key,name in [('asset_map_sha256','current-assets.json'),('native_map_sha256','current-native-reference-map.json')]:
    assert d[key] == sha(H/name), key
for x in r['pages']+r['csv_files']+r['thumbnail_files']:
    assert sha(x['path']) == x['sha256'], x['path']

qa_path = B/'components/parallel-reviews/all-record-image-matching-20261024-B/workbook-publication-qa/final-report-links/sealed-handoff.json'
assert sha(qa_path) == '0dd556c00b9546a7b7db55d5c6759c966b838daab9819e9dde350efa915d4900'
qa = read(qa_path)
assert qa['candidate_sha256'] == v['workbook_sha256']
assert qa['counts'] == {'sheets':28,'formulas':3407,'hyperlinks':12206,'total_value_changes':44,'total_hyperlink_changes':225}
for path,digest in qa['files'].items():
    assert sha(path) == digest, path
gallery = g['current_complete_gallery_mapping']
for key in ['source_gallery_handoff','independent_source_gallery_qa','complete_native_roles','remaining_work']:
    assert sha(gallery[key]['path']) == gallery[key]['sha256'], key
assert gallery['counts']['current_wall_images_reviewed'] == 6360
for label,x in manifest.items():
    assert sha(x['path']) == sha(x['snapshot']) == x['sha256'], label

p = copy.deepcopy(old)
old_out = B/'outputs/current-six-url-case-navigation-master-2026-10-24'
old_h = Path(manifest['master_register']['path']).parent
def reroute(value):
    if isinstance(value,list):
        return [reroute(x) for x in value]
    if isinstance(value,dict):
        return {k:reroute(x) for k,x in value.items()}
    if isinstance(value,str):
        for src,dst in [(str(old_out),str(out)),(rel(old_out),rel(out)),(str(old_h),str(H)),(rel(old_h),rel(H))]:
            if value.startswith(src+'/'):
                target = dst+value[len(src):]
                path = Path(target.split('#')[0])
                if not path.is_absolute():
                    path = B/path
                if path.is_file():
                    return target
    return value

for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification',
            'current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion',
            'current_local_draft_completion','current_working_design_group_projection']:
    p[key] = reroute(p[key])
validation = {name: {'path':rel(H/file),'sha256':sha(H/file)} for name,file in [
    ('saved_workbook','saved-workbook-verification.json'),('current_data','final-data-readback.json'),
    ('reports','report-verification.json'),('workbook_link_addendum','current-report-link-routing-addendum.json')]}
independent = {'path':rel(qa_path),'sha256':sha(qa_path),'saved_package_checks':110076,'artifact_tool_value_reads':44,'final_local_report_link_checks':69}
p.update(recorded_utc=now(),status='CURRENT_MASTER188_COMPLETE_WALL_AND_LOCAL_PLATFORM_GALLERY_REVIEW',
    register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],
    workbook_sha256=v['workbook_sha256'],publication_receipt=rel(H/'publication-receipt.json'),
    summary=copy.deepcopy(g['summary']),latest_workbook_validation=validation,
    current_complete_gallery_mapping=copy.deepcopy(gallery),
    latest_complete_wall_navigation_refresh={**copy.deepcopy(g['latest_complete_wall_navigation_candidate']),
        'status':'PUBLISHED_CURRENT_NAVIGATION_WITH_QUALIFIED_GALLERY_EVIDENCE',
        'verification':validation,'independent_workbook_qa':independent},
    current_local_platform_comparison={
        'authority':'Existing local Shopify and Squarespace exports; no live Shopify account access required',
        'review':str(ROOT/'reports/local-platform-crosswalk-corrected-20261024-root/index.html'),
        'seal':str(ROOT/'reports/local-platform-crosswalk-corrected-20261024-root/sealed-handoff.json'),
        'seal_sha256':'39d08659707d6ad99010e64b3503caf6bcb07d330e067cafad1109143bdc7d4f',
        'exact_nonempty_shared_SKU_pairs':37,'unpaired_Squarespace_source_tuples':43,
        'blank_SKU_Shopify_wall_drafts':1,'numeric_Shopify_IDs_exported':False,
        'explicit_variant_image_assignments_exported':False,'platform_writes':0})
assert sha(p['current_local_platform_comparison']['seal']) == p['current_local_platform_comparison']['seal_sha256']
p['current_path_scope'] += '; Complete60-family Wall snapshot:6360 current files and6802 native objects including root; cumulative stable-ID maps retain historical and out-of-scope observations. Two current equivalent Wall Circle photograph references replace deleted selected IDs while their history and owner identity holds remain.'
p['historical_image_review_links'].append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links'].update(all_links=rel(out/'index.html'),verification=rel(H/'report-verification.json'),
    verification_sha256=sha(H/'report-verification.json'),counts=r['counts'],
    current_primary_navigation=rel(out/'current-primary-navigation-health.html'),
    all_individual_option_galleries=gallery['readers']['products'],
    complete_platform_galleries=gallery['readers']['platform_galleries'],
    complete_family_galleries=gallery['readers']['families'],
    complete_current_wall_images=gallery['native_complete_reader'])
p['latest_image_coverage_audit'] = {**old['latest_image_coverage_audit'],
    'path':str(H/'image-coverage-current.json'),'audit':rel(H/'image-coverage-current.json'),
    'audit_sha256':v['audit_sha256'],'status':'SOURCE_PHOTO_COUNTS_AND_OWNER_DEFERRALS_RETAINED_CURRENT_REFERENCE_NAVIGATION_REFRESHED',
    'latest_complete_gallery_mapping':copy.deepcopy(gallery)}
p['current_asset_reference_map'] = {'path':rel(H/'current-assets.json'),'sha256':d['asset_map_sha256'],
    'cumulative_asset_records':6690,'current_wall_file_records':6360,
    'scope':'Complete current Wall metadata and visual source bindings; all6656 prior asset IDs retained;34 existing native IDs newly represented. No new sculpture records.',
    'preceding_reference':copy.deepcopy(old['current_asset_reference_map'])}
p['current_native_reference_map'] = {'path':rel(H/'current-native-reference-map.json'),'sha256':d['native_map_sha256'],
    'schema':'Wrapper with current_objects, path aliases and retained history','cumulative_object_count':7061,
    'current_wall_native_objects_including_root':6802,'current_wall_file_count':6360,
    'scope':'Current BOLDSTONE MASTER Wall snapshot and retained earlier history. Scoped absence does not establish deletion or global unavailability.',
    'native_writes_by_master_import':0,'preceding_reference':copy.deepcopy(old['current_native_reference_map'])}
p['current_primary_navigation_health'] = {'path':rel(H/'current-primary-navigation-health.json'),
    'sha256':sha(H/'current-primary-navigation-health.json'),'review':rel(out/'current-primary-navigation-health.html'),
    'csv':rel(out/'Current_Primary_Navigation_48.csv'),'checked_options_in_this_reference_resolution':2,
    'current_equivalent_primary_references_verified':2,'unresolved_references_in_this_resolution':0,
    'saved_primary_ids_marked_deleted_in_available_history':2,'old_selected_reference_history_retained':True,
    'source_photo_coverage_unchanged':True,'owner_identity_holds_preserved':True,
    'scope':'Two verified current equivalents. Other46 rows in the48-row navigation table retain their earlier readback clocks.',
    'historical_previous_scope':copy.deepcopy(old['current_primary_navigation_health'])}
p['current_individual_sculpture_list'].update(recorded_utc=p['recorded_utc'],register=p['register'],
    register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],
    current_option_list_sha256=sha(out/'Current_Individual_Options_188.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),
    new_physical_measurements_added=0,new_physical_verifications=0,commercial_values_changed_in_this_refresh=0)
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['current_authenticated_squarespace_inventory_observation'].update(register=p['register'],register_sha256=p['register_sha256'])
p['next_catalogue_actions'] = [
    'Continue the recovery session owned Frozen Fish FFL1/FFS2 and Wall Circle exact-pair identity questions; no answer inferred. All current Frozen Fish remain70H x15W cm.',
    'Retain22 held installation and1 held series requirements,0 active capture requests,10 accepted group-image references and all source-photo qualifications.',
    'Review29 Squarespace and3 Shopify exact-photo uncertainties,4 uncertain native image roles,65 options without an existing source association, and625 files retained at family scope without an exact option edge.',
    'Collect actual dimensions/depth, bare-panel weight, maker material and fitted fixing; preserve all1128 active working field objects and their estimate labels until evidence is supplied.',
    'Keep the Squarespace write hold. Local Shopify export comparison is complete; no live Shopify account or platform write is required for this review.']
p['latest_master_metadata_change'] = {'status':'SUPERSEDED_BY_COMPLETE_GALLERY_NAVIGATION_RELEASE','preceding_metadata_receipt':old['publication_receipt']}
protected = ['current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_listing_population','platform_write_holds',
    'current_structure_discovery_scope','current_wall_sculpture_inclusion_policy','current_individual_photo_capture_policy',
    'current_option_count','retained_option_count','current_global_context_owner_hold','current_source_photo_review_index',
    'all_actual_specifications_complete','physical_stock_quantity','whole_library_unique_design_total']
for key in protected:
    assert p[key] == old[key], key

updates = {}
fields = ['summary','current_complete_gallery_mapping','current_local_platform_comparison','latest_complete_wall_navigation_refresh',
    'current_primary_navigation_health','current_authenticated_squarespace_inventory_observation','current_asset_reference_map',
    'current_native_reference_map','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists',
    'current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion',
    'current_local_draft_completion','current_working_design_group_projection','next_catalogue_actions','latest_workbook_validation','latest_master_metadata_change']
for label in ['review_progress','component_checkpoint','checkpoint']:
    dest = Path(manifest[label]['path'])
    value = read(dest)
    value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],
        current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
    for key in fields:
        value[key] = copy.deepcopy(p[key])
    updates[dest] = value
write(H/'prepared-pointer.json',p)
prepared = {'status':'ALL_PUBLICATION_GUARDS_PASS_PREPARED_ONLY','recorded_utc':now(),
    'prepared_pointer_sha256':sha(H/'prepared-pointer.json'),'workbook_sha256':p['workbook_sha256'],
    'register_sha256':p['register_sha256'],'independent_workbook_qa':independent,
    'local_files_to_replace':[str(B/p['workbook']),*[str(x) for x in updates],str(B/'current-master.json')],
    'external_writes':0}
write(H/'prepared-publication-verification.json',prepared)
if '--apply' not in sys.argv:
    print(json.dumps(prepared,indent=2))
    raise SystemExit(0)

lock = H/'publication.lock'
fd = os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
os.close(fd)
changed = []
try:
    for label,x in manifest.items():
        assert sha(x['path']) == x['sha256'], 'Baseline changed before publication: '+label
    target = B/p['workbook']
    tmp = target.with_name(target.name+'.whole-gallery-tmp')
    shutil.copy2(H/'master-workbook.pending',tmp)
    assert sha(tmp) == p['workbook_sha256']
    os.replace(tmp,target)
    changed.append(('master_workbook',target))
    for dest,value in updates.items():
        write(dest,value)
        label = next(k for k in ['review_progress','component_checkpoint','checkpoint'] if manifest[k]['path'] == str(dest))
        changed.append((label,dest))
    write(B/'current-master.json',p)
    changed.append(('pointer',B/'current-master.json'))
    assert read(B/'current-master.json') == p and sha(target) == p['workbook_sha256']
    assert sha(B/p['register']) == p['register_sha256']
    for dest,value in updates.items():
        assert read(dest) == value and value['current_master_catalogue'] == p
    receipt = {'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),
        'current_master_pointer_sha256':sha(B/'current-master.json'),'workbook':str(target),
        'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],
        'asset_map_sha256':d['asset_map_sha256'],'native_map_sha256':d['native_map_sha256'],
        'controls_sha256':{str(x):sha(x) for x in updates},'verification':validation,'independent_workbook_qa':independent,
        'active_options':188,'retained_options':189,'retained_component_ids':112,'working_design_groups':110,
        'sheets':28,'formulas':3407,'native_hyperlinks':12206,'value_changes':44,'target_link_changes':225,
        'new_physical_or_commercial_field_values':0,'external_writes':0,'preceding_pointer_sha256':manifest['pointer']['sha256'],
        'complete_gallery_counts':gallery['counts']}
    write(H/'publication-receipt.json',receipt)
    write(out/'publication-state.json',{'status':'PUBLISHED_AND_READ_BACK','receipt':str(H/'publication-receipt.json'),
        'receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']})
    print(json.dumps(receipt,indent=2))
except BaseException as exc:
    for label,dest in reversed(changed):
        tmp = dest.with_name(dest.name+'.whole-gallery-rollback')
        shutil.copy2(manifest[label]['snapshot'],tmp)
        os.replace(tmp,dest)
    write(H/'publication-rollback.json',{'status':'ROLLED_BACK','recorded_utc':now(),'error':str(exc),'restored':[str(x) for _,x in changed]})
    raise
finally:
    lock.unlink(missing_ok=True)
