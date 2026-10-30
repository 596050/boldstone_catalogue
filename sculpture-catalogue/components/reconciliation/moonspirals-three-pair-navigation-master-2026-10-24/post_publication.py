"""Read back committed master, controls and unchanged commercial/source policies."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');p=read(B/'current-master.json');oldp=read(m['pointer']['snapshot']);r=read(H/'publication-receipt.json');g=read(B/p['register']);old=read(m['master_register']['snapshot']);a=read(H/'image-coverage-current.json');old_a=read(m['audit']['snapshot']);issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
check(p==read(H/'prepared-pointer.json'),'Published pointer exactly matches reviewed prepared pointer')
check(p['register']==str((H/'canonical-master-register.json').relative_to(B)),'Correct canonical release selected')
check(sha(B/p['register'])==p['register_sha256']==r['register_sha256'],'Exact committed register bytes')
check(sha(B/p['workbook'])==p['workbook_sha256']==r['workbook_sha256'],'Exact committed workbook bytes')
check(sha(B/'current-master.json')==r['current_master_pointer_sha256'],'Pointer bytes equal publication receipt')
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);check(d['current_master_catalogue']==p and sha(dest)==r['controls_sha256'][str(dest)],'Exact synchronized control '+key)
check(g['summary']==old['summary'],'Current catalogue summary unchanged')
check(len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112,'188 active options/189 retained rows/112 ID records')
check(sha(H/'working-design-group-projection.json')==m['working_groups']['sha256']and p['current_working_design_group_projection']['grouped_working_design_identity_count']==110,'110 working design groups unchanged')
check(g['current_owner_design_equivalence_edges']==old['current_owner_design_equivalence_edges'],'Both existing separate owner design decisions unchanged')
for key in ['current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_listing_population','platform_write_holds','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy','current_individual_photo_capture_policy','current_option_count','retained_option_count','current_global_context_owner_hold']:check(p[key]==oldp[key],'Unchanged policy '+key)
for key in ['specifications','master_fields','selling_details']:
 check([o[key]for o in g['options']]==[o[key]for o in old['options']],'All189 complete '+key+' dictionaries unchanged')
check(g['source_sets']==old['source_sets']and g['source_offer_edges']==old['source_offer_edges']and g['source_media_configuration_coverage']==old['source_media_configuration_coverage'],'All source offers/BOM/media configurations retained')
check(a['counts']==old_a['counts'],'All source-photo counts/roles and owner actions retained')
native=read(H/'current-native-reference-map.json');assets=read(H/'current-assets.json');history=read(H/'path-change-history.json')
check(len(history)==3,'Only3 approved native path and parent changes')
for x in history:check(native['current_objects'][x['file_id']]==x['current']and assets[x['file_id']]['folder_id']==x['current']['parent_id']=='id:cnqzTNngPVsAAAAAAAyi8w','Moved original ID actual parent '+x['file_id'])
wall=read(H/'wall-circle-history-observations.json')['rows'];check(len(wall)==2 and all(x['deletion_observed_in_exact_id_history']and not x['restored_to_dropbox']and not x['replacement_selected']and x['owner_hold_preserved']for x in wall.values()),'2 explicit deleted-history observations without restore/replacement/hold release')
for x in wall.values():check(sha(x['existing_local_historical_original']['path'])==x['existing_local_historical_original']['sha256'],'Retained historical original bytes '+x['product_id'])
for key,name in [('report_reviews','photo-review-queue.json'),('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('photo_source','photo-source-review.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json')]:check(sha(H/name)==m[key]['sha256'],'Exact retained working/source/owner bytes '+name)
rep=read(H/'report-verification.json');check(rep['register_sha256']==p['register_sha256']and rep['audit_sha256']==r['audit_sha256'],'All reports bind to published canonical release')
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Published report artifact '+x['path'])
check(sha(B/p['current_primary_navigation_health']['path'])==p['current_primary_navigation_health']['sha256'],'Current health pointer and bytes agree')
check(sha(B/p['current_native_reference_map']['path'])==p['current_native_reference_map']['sha256'],'Current native map pointer and bytes agree')
qa=r['independent_qa'];check(sha(qa['path'])==qa['sha256']and sha(qa['seal_path'])==qa['seal_sha256']and read(qa['path'])['status']=='PASS','Independent QA sealed exact candidate')
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'current_master_pointer_sha256':sha(B/'current-master.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256'],'active_options':188,'retained_component_ids':112,'working_design_groups':110,'current_native_paths_changed':3,'native_history_deleted_observations':2,'new_physical_verifications':0,'new_platform_matches':0,'new_image_selections':0}
(H/'post-publication-readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
