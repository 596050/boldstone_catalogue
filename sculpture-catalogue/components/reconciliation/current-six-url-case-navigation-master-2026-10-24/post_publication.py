import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');p=read(B/'current-master.json');pub=read(H/'publication-receipt.json');oldp=read(m['pointer']['snapshot']);g=read(B/p['register']);old=read(m['master_register']['snapshot']);a=read(H/'image-coverage-current.json');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
check(p==read(H/'prepared-pointer.json'),'Exact committed prepared pointer')
check(sha(B/'current-master.json')==pub['current_master_pointer_sha256'],'Publication pointer bytes')
check(sha(B/p['register'])==p['register_sha256']==pub['register_sha256'],'Committed register bytes')
check(sha(B/p['workbook'])==p['workbook_sha256']==pub['workbook_sha256'],'Committed workbook bytes')
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);check(sha(dest)==pub['controls_sha256'][str(dest)]and read(dest)['current_master_catalogue']==p,'Synchronized control '+key)
check(g['summary']==old['summary']and len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['components'])==112,'188active/189retained/112 ID records')
check(sha(H/'working-design-group-projection.json')==m['working_groups']['sha256']and p['current_working_design_group_projection']['grouped_working_design_identity_count']==110,'110 working groups unchanged')
for key in ['specifications','master_fields','selling_details']:check([o[key]for o in g['options']]==[o[key]for o in old['options']],'All complete qualified '+key+' dictionaries unchanged')
for key in ['platform_write_holds','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_global_context_owner_hold','current_individual_photo_capture_policy','latest_moonwave_proposal_withdrawal']:check(p[key]==oldp[key],'Standing policy/withdrawn-history retained '+key)
check(a['counts']==read(m['audit']['snapshot'])['counts'],'Source photo roles/counts/held actions unchanged')
for i,(x,y)in enumerate(zip(g['source_offer_edges'],old['source_offer_edges'])):check(x['source_offer']==y['source_offer']and x['members']==y['members'],'Captured source and BOM unchanged '+str(i))
edge=g['source_offer_edges'][15];check(edge['offer_ref']=='O016'and edge['current_primary_reference']['file_id']=='id:cnqzTNngPVsAAAAAAArp1g'and edge['current_primary_reference']['folder_id']=='id:cnqzTNngPVsAAAAAAAyi-A','O016 own-source file has verified actual White parent')
check(g['source_offer_edges'][14]==old['source_offer_edges'][14],'O015 unrelated Concave/MWC source untouched')
cfg=copy.deepcopy(g['source_media_configuration_coverage']);nav=cfg[163].pop('current_example_reference_navigation');check(cfg==old['source_media_configuration_coverage'],'All original configuration coverage/4exampleIDs retained')
check(nav['id:cnqzTNngPVsAAAAAAArp2Q']['folder_id']=='id:cnqzTNngPVsAAAAAAAyi-A','Coverage163 own-file current parent explicit')
native=read(H/'current-native-reference-map.json');assets=read(H/'current-assets.json');ov=read(H/'moonwave-native-overlay.json');moved=[o for o in ov['objects']if o['old_path']!=o['current_path']]
check(len(moved)==10 and sum(x['object_type']=='file'for x in ov['objects'])==99,'Exact10 moves/99originals')
for o in moved:check(native['current_objects'][o['file_id']]['parent_id']==assets[o['file_id']]['folder_id']==o['current_parent_id'],'Own native/asset actual parent '+o['file_id'])
check(g['latest_moonwave_approved_native_navigation']['White_files']==84 and g['latest_moonwave_approved_native_navigation']['InSitu_files']==15,'Verified84White/15InSitu')
for key,name in [('physical_audit','physical-source-audit.json'),('originals','original-verification.json'),('primary_health','current-primary-navigation-health.json'),('review_state','guided-owner-review-state.json')]:check(sha(H/name)==m[key]['sha256'],'Preserved original bytes '+name)
rep=read(H/'report-verification.json');check(rep['register_sha256']==p['register_sha256']and rep['audit_sha256']==pub['audit_sha256'],'Current reports bind exact published data')
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']:check(sha(x['path'])==x['sha256'],'Published report bytes '+x['path'])
q=pub['independent_qa'];check(sha(q['path'])==q['sha256']and sha(q['seal_path'])==q['seal_sha256']and read(q['path'])['status']=='PASS','Independent candidate QA exact bytes')
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'pointer_sha256':sha(B/'current-master.json'),'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],'active_options':188,'retained_component_ids':112,'working_design_groups':110,'normalized_option_URL_fields':12,'approved_Moonwave_path_parent_updates':10,'Moonwave_originals':99,'Moonwave_White':84,'Moonwave_InSitu':15,'new_specifications_or_source_matches':0};(H/'post-publication-readback.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if issues:raise SystemExit(1)
