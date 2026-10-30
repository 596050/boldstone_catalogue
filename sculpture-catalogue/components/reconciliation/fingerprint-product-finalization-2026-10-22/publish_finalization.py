"""CAS-publish the checked current Fingerprint population and all current controls."""
import copy,csv,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone

H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
 p=Path(p);tmp=p.with_name(p.name+'.fp-publish-tmp')
 tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
def bound(p):
 p=Path(p);return {'path':str(p),'sha256':sha(p)}

assert not (H/'publication-receipt.json').exists(),'Already published; use readback, never duplicate the population change'
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json')
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json')
reports=read(H/'link-report-verification.json');visual=read(H/'visual-verification.json')
cf=read(H/'conditional-format-extension-verification.json');out=Path(reports['output_directory'])
assert v['status']==visual['status']==cf['status']=='PASS' and not v['issues']
assert reports['status']=='PASS_OWNER_CORRECTION_REPORTS'
assert sha(H/'master-workbook.pending')==v['workbook_sha256']==visual['workbook_sha256']==cf['workbook_sha256']
assert sha(H/'canonical-master-register.json')==v['register_sha256'] and sha(H/'image-coverage-current.json')==v['audit_sha256']
assert (len(g['options']),len(g['components']),g['summary']['current_field_groups'])==(186,112,1116)
assert a['counts']['required_picture_actions']==101 and reports['counts']['individual_gaps']==22
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+visual['previews']:
 assert sha(x['path'])==x['sha256'],'Rendered/report artifact drift '+x['path']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen input drift '+x['path']

# The independent lane owns its changing user HTML. Seal its immutable input
# packet here; its final HTML and separate receipt are finalized after readback.
option_csv=out/'Current_Individual_Options_186.csv'
with option_csv.open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
assert len(rows)==186 and {r['option_id']for r in rows}=={x['product_id']for x in g['options']}
assert len({r['component_id']for r in rows if r['component_id']})==112
count_summary=read(out/'current-count-summary.json')
assert count_summary['current_option_list']['sha256']==sha(option_csv)
count_summary.update(status='VERIFIED_COUNT_RECONCILIATION',verified_utc=now())
write(out/'current-count-summary.json',count_summary)
count_report={'status':'PASS','recorded_utc':now(),'current_options':186,'working_component_identities':112,
 'physical_counts_verified':False,'files':[bound(p)for p in [option_csv,out/'current-count-summary.json',H/'current-fingerprint-inventory.json',H/'archived-records-and-actions.json',Path(m['product_packet']['path']),Path(m['packet_seal']['path'])]],
 'independent_product_report_owned_by_lane_B':'outputs/fingerprint-product-finalization-2026-10-22/index.html'}
write(H/'count-report-verification.json',count_report)

ptr=read(BASE/'current-master.json');prior=copy.deepcopy(ptr)
scope=copy.deepcopy(g['latest_fingerprint_product_finalization'])
scope.update(verification=rel(H/'saved-file-verification.json'),verification_sha256=sha(H/'saved-file-verification.json'),
 visual_verification=rel(H/'visual-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'),
 conditional_format_verification=rel(H/'conditional-format-extension-verification.json'),
 workbook_sheets=['Master Catalogue','Specifications','Components','Photo Coverage','Fingerprint Current','Fingerprint History'],
 current_inventory=rel(H/'current-fingerprint-inventory.json'),current_inventory_sha256=sha(H/'current-fingerprint-inventory.json'),
 historical_records=rel(H/'archived-records-and-actions.json'),historical_records_sha256=sha(H/'archived-records-and-actions.json'))
ptr.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],
 publication_receipt=rel(H/'publication-receipt.json'),summary=copy.deepcopy(g['summary']),latest_fingerprint_product_finalization=scope,
 latest_fingerprint_numbered_reconciliation=copy.deepcopy(g['latest_fingerprint_numbered_reconciliation']),
 all_current_options_have_six_working_fields_recorded=True,current_option_count=186)
ptr.pop('all184_options_have_six_working_fields_recorded',None)
ptr['current_path_scope']=ptr['current_path_scope'].replace('numbered design/version alias unresolved','three current Fingerprint Concentric designs selected by owner; six Cream/White options included once; legacy Left/Right offers archived')
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification_sha256=scope['verification_sha256'],visual_verification_sha256=scope['visual_verification_sha256'])
ptr.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(prior['latest_image_coverage_audit']))
ptr['latest_image_coverage_audit']=coverage
ptr.setdefault('historical_image_review_links',[]).append(copy.deepcopy(prior['current_image_review_links']))
links=copy.deepcopy(prior['current_image_review_links'])
for k in ['all_links','individual_image_gaps','missing_in_situ_images','missing_series_images','existing_images_to_check','resolved_image_roles']:
 links[k]=rel(out/Path(links[k]).name);assert (BASE/links[k]).is_file()
links.pop('fingerprint_legacy_alias_review',None)
links.update(verification=rel(H/'link-report-verification.json'),verification_sha256=sha(H/'link-report-verification.json'),counts=copy.deepcopy(reports['counts']),
 fingerprint_current='outputs/fingerprint-product-finalization-2026-10-22/index.html',
 fingerprint_legacy_history=rel(H/'archived-records-and-actions.json'),
 fingerprint_link_verification=rel(H/'count-report-verification.json'),fingerprint_link_verification_sha256=sha(H/'count-report-verification.json'))
assert (BASE/links['fingerprint_current']).is_file() and (BASE/links['fingerprint_all26_photographs']).is_file()
ptr['current_image_review_links']=links
missing=copy.deepcopy(prior['current_missing_picture_lists'])
for k,x in list(missing.items()):
 if isinstance(x,str)and x.startswith('outputs/'):
  missing[k]=rel(out/Path(x).name);assert(BASE/missing[k]).is_file()
missing.update(required_actions=101,find_capture=100,verify_existing=1,individual_gaps=22,in_situ_gaps=61,series_gaps=18,
 current_resolved_actions=51,historical_resolved_actions=53,exact_crop_candidates=13,separate_individual_photos_required=8,
 superseded_Fingerprint_actions_archived=6,current_action_rows=205,legacy_binding_deferred=True)
ptr['current_missing_picture_lists']=missing
count={'recorded_utc':now(),'status':'CURRENT_WORKING_CATALOGUE_COUNT','register':ptr['register'],'register_sha256':ptr['register_sha256'],
 'workbook':ptr['workbook'],'workbook_sha256':ptr['workbook_sha256'],'publication_receipt':ptr['publication_receipt'],
 'summary':copy.deepcopy(g['summary']),'customisable_records':186,'unbounded_custom_requests_are_not_enumerated_records':True,
 'count_definition':'Working component identities and individually offered finish/size/build options; not a physical cast, mould or stock count.',
 'physical_stock_verified':False,'current_option_list':rel(option_csv),'current_option_list_sha256':sha(option_csv),
 'count_summary':rel(out/'current-count-summary.json'),'count_summary_sha256':sha(out/'current-count-summary.json')}
ptr['current_individual_sculpture_list']=copy.deepcopy(count)
ptr['current_listing_population']={'status':'CURRENT_LOCAL_POPULATION; NATIVE_REVIEW_PENDING','catalogue_options':186,'working_field_groups':1116,
 'local_draft_scopes':102,'nonwall_individual_drafts':99,'nonwall_draft_groups':77,'wall_circle_custom_draft_scopes':3,
 'new_current_Fingerprint_options_awaiting_native_review':6,'original_106_case_review_is_historical':True,
 'current_resolution_population_entries':len(g['current_listing_resolution_details']['entries']),'platform_writes':0}
ptr.setdefault('historical_guided_image_reviews',[]).append(copy.deepcopy(prior['current_guided_image_review']))
guided={'status':'READY_NEXT_CURRENT_INDIVIDUAL_IMAGE_REVIEW','path':rel(H/'photo-review-queue.json'),'sha256':sha(H/'photo-review-queue.json'),
 'review_list':links['individual_image_gaps'],'current_individual_gaps':22,'superseded_case':'Historical Fingerprint Left/Right crop criterion retired with old active offers; do not repeat as a current offer-selection question.',
 'owner_answers_preserved_in_historical_walkthrough':prior['current_guided_image_review']}
ptr['current_guided_image_review']=guided
if(H/'queued-path-refreshes.json').exists():ptr['queued_native_path_refreshes']=bound(H/'queued-path-refreshes.json')
next_actions=[
 'Project queued owner-approved Moonphases folder renames and Dune Ripple1=Waves/2=Spiral renames by stable native IDs; no additional designs inferred.',
 'Work through22 current individual-image gaps:13 exact-crop candidates,8 separate-photo requirements and1 deferred legacy Frozen Fish identity. Keep current Frozen Fish70 H x15 W cm.',
 'Complete61 current in situ and18 current series gaps using linked source images and actual containing folder IDs.',
 'Verify physical dimensions/depth, weighed mass, material and fitted hardware where required; confirm numeric prices, stock/capacity and lead times. Existing proposals remain qualified.',
 'Read-only verify individual current Squarespace/Shopify products and variants, including six new Fingerprint options. Keep owner Squarespace write hold in force.'
]
ptr['next_catalogue_actions']=next_actions
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[key]['path']);d=read(p)
 if 'current_individual_catalogue_count'in d:d.setdefault('historical_individual_catalogue_count_snapshots',[]).append(copy.deepcopy(d['current_individual_catalogue_count']))
 d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],
  current_individual_catalogue_count=copy.deepcopy(count),latest_fingerprint_product_finalization=copy.deepcopy(scope),
  latest_fingerprint_numbered_reconciliation=copy.deepcopy(ptr['latest_fingerprint_numbered_reconciliation']),
  latest_image_coverage_audit=copy.deepcopy(coverage),current_image_review_links=copy.deepcopy(links),current_missing_picture_lists=copy.deepcopy(missing),
  current_guided_image_review=copy.deepcopy(guided),next_image_review_actions=copy.deepcopy(next_actions),
  current_listing_population=copy.deepcopy(ptr['current_listing_population']))
 if key=='component_checkpoint':d['current_master_validation']={'path':scope['verification'],'sha256':scope['verification_sha256']}
 updates[p]=d

# All content and guards are concrete before the atomic replacement of the
# authoritative workbook. No Dropbox or native platform mutation occurs here.
for k in ['latest_listing_resolution','latest_listing_reconciliation','latest_image_identity_resolution','latest_moon_and_shellwave_numbering','latest_gleneagles_numbering','latest_raked_spiral_paths','latest_lava_moon_numbering','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds']:
 assert ptr.get(k)==prior.get(k),'Unrelated evidence/policy change '+k
for x in m.values():assert sha(x['path'])==x['sha256'],'Final compare-and-swap drift '+x['path']
for x in count_report['files']:assert sha(x['path'])==x['sha256']
write(H/'export-receipt.json',{'status':'PASS_READY_TO_PUBLISH','recorded_utc':now(),'workbook_sha256':v['workbook_sha256'],'register_sha256':v['register_sha256'],
 'sheets':26,'native_hyperlinks':11427,'formulas':2791,'current_options':186,'working_component_identities':112,'checks':v['checks']})
write(H/'prepared-pointer.json',ptr)
target=BASE/ptr['workbook'];os.replace(H/'master-workbook.pending',target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)

assert read(BASE/'current-master.json')==ptr and sha(target)==ptr['workbook_sha256']
assert sha(BASE/ptr['register'])==ptr['register_sha256']
for p,d in updates.items():assert read(p)==d and d['current_master_catalogue']==ptr
for k,x in m.items():
 if k not in ['master_workbook','master_pointer','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256']
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':v['workbook_sha256'],
 'register':str(H/'canonical-master-register.json'),'register_sha256':v['register_sha256'],'audit':str(H/'image-coverage-current.json'),'audit_sha256':v['audit_sha256'],
 'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},
 'verification':scope['verification'],'visual_verification':scope['visual_verification'],'count_report_verification':rel(H/'count-report-verification.json'),
 'checks':v['checks'],'current_options':186,'working_component_identities':112,'qualified_working_field_groups':1116,
 'sheets':26,'formulas':2791,'native_hyperlinks':11427,'unrelated_current_options_preserved':180,'unrelated_current_components_preserved':109,
 'original_specification_assertions_preserved':1668,'current_Fingerprint_components':3,'current_Fingerprint_options':6,
 'legacy_Fingerprint_options_archived':4,'legacy_Fingerprint_components_archived':2,'legacy_Fingerprint_actions_archived':6,
 'current_individual_gaps':22,'current_in_situ_gaps':61,'current_series_gaps':18,'current_required_picture_actions':101,
 'current_action_rows':205,'current_resolved_actions':51,'historical_resolved_actions':53,
 'legacy_capture_actions_retired_by_scope_not_new_photos':4,'numeric_price_and_actual_physical_specs_verified':False,
 'root_Dropbox_or_platform_writes':0,'separate_native_lane_action_receipts_retained':True}
write(H/'publication-receipt.json',receipt)
write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_FINGERPRINT_PRODUCTS_SPECS_COUNTS_AND_IMAGE_GAPS','recorded_utc':now(),
 'publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),
 'workbook_sha256':v['workbook_sha256'],'register_sha256':v['register_sha256'],'current_options':186,'working_component_identities':112,
 'individual_gaps':22,'in_situ_gaps':61,'series_gaps':18})
state=read(H/'WORK_STATE.json');state.update(status='COMPLETE_PUBLISHED_AND_READ_BACK',publication_receipt=rel(H/'publication-receipt.json'),next='Queued Moonphases/Dune Ripple stable-ID path projection and remaining current photo/specification/platform review')
write(H/'WORK_STATE.json',state)
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256','current_options','working_component_identities','current_individual_gaps']}))
