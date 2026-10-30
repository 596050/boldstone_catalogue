"""Verify pair-only owner scope, retained fields and the112-to111 group projection."""
import copy,csv,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');old=read(m['master_register']['snapshot']);edge=read(H/'owner-design-edge.json');proj=read(H/'working-design-group-projection.json');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
pair=set(edge['owner_confirmed_option_ids']);check(pair=={'BSI-612EF4DBB555','BSI-8CC6C8AABCB7'},'Exact owner-confirmed number1 pair only')
restored=copy.deepcopy(g)
for c in read(H/'authorized-current-field-changes.json'):
 x=restored
 for k in c['path'][:-1]:x=x[k]
 k=c['path'][-1];check(x[k]==c['current'],'Exact declared owner current value '+str(c['path']))
 if c['before_exists']:x[k]=c['before']
 else:del x[k]
check(restored==old,'No undeclared register changes')
for x,y in zip(g['options'],old['options']):
 z=copy.deepcopy(x)
 if x['product_id']in pair:z.pop('current_owner_design_equivalence')
 check(z==y,'All prior option fields retained '+x['product_id'])
 for k in ['master_fields','specifications','selling_details','file_id','folder_id','canonical_component_id','canonical_design_id','photo_coverage']:
  check(x.get(k)==y.get(k),'No field/ID/role transfer '+k+' '+x['product_id'])
for x,y in zip(g['components'],old['components']):
 z=copy.deepcopy(x)
 if x['component_id']in edge['component_ids']:z.pop('current_owner_design_group');z['scope_note']=y['scope_note']
 check(z==y,'Retained component record '+x['component_id'])
for k in ['source_sets','source_offer_edges','aliases','original_review_specification_assertions','wall_circle_native_options','listing_resolution_native_action_drafts','current_authenticated_squarespace_inventory_observation','current_global_context_owner_hold','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_primary_navigation_health']:
 check(g[k]==old[k],'Unchanged source/owner/native-health scope '+k)
check(len(g['options'])==189 and len(g['active_option_ids'])==188 and len(g['components'])==112,'Option and retained ID counts')
check(len(proj['groups'])==111,'111 working design groups')
flat=[i for x in proj['groups']for i in x['retained_component_ids']];check(len(flat)==len(set(flat))==112 and set(flat)=={c['component_id']for c in g['components']},'Every retained component ID projected exactly once')
multiple=[x for x in proj['groups']if len(x['retained_component_ids'])>1];check(len(multiple)==1 and set(multiple[0]['retained_component_ids'])=={'BC-DECO-1','BC-FDW-1'},'One and only one confirmed component equivalence group')
check(set(multiple[0]['owner_directly_confirmed_option_ids'])==pair,'Terracotta membership has no new direct owner approval')
check(proj['whole_library_unique_design_count']is None and not edge['number2_confirmed']and not edge['terracotta_owner_photo_approval'],'Unique library total and number2/Terracotta remain unconfirmed')
for o in g['options']:
 if o.get('canonical_component_id')in ['BC-DECO-2','BC-FDW-2']:
  check(o==next(x for x in old['options']if x['product_id']==o['product_id']),'Whole number2 option unchanged '+o['product_id'])
for file,key in [('image-coverage-current.json','audit'),('current-assets.json','report_assets'),('current-native-reference-map.json','native_map'),('photo-review-queue.json','report_reviews'),('photo-source-review.json','photo_source'),('guided-owner-review-state.json','review_state'),('pending-followups.json','pending'),('physical-source-audit.json','physical_audit'),('original-verification.json','originals')]:check(sha(H/file)==m[key]['sha256'],'Byte-identical unchanged '+file)
for path,x in read(H/'evidence-manifest.json').items():check(sha(path)==x['sha256'],'Sealed owner evidence '+path)
rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
with (out/'Current_Working_Design_Groups_111.csv').open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
check(len(rows)==111 and len({r['working_design_group_id']for r in rows})==111,'111 CSV group rows')
with (out/'Current_Individual_Options_188.csv').open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
check(len(rows)==188 and {r['option_id']for r in rows if r['owner_confirmed_design_equivalence_edge']}==pair,'188 CSV options with direct owner approval on exactly two')
with (out/'Owner_Decowaves1_Design_Equivalence_2.csv').open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
check({r['option_id']for r in rows}==pair and all(r['number2_confirmed']=='False'and r['specifications_transferred']=='False'for r in rows),'Pair CSV no scope or specification transfer')
physical=read(H/'physical-source-audit.json')['summary'];check(physical['active_options_reviewed']==188 and physical['physical_field_groups_reviewed']==752 and physical['new_qualified_comparator_field_groups_reviewed']==4 and physical['new_independent_physical_source_assertions']==0,'Display scope matches existing physical ledger with four comparator-only fields')
plan=read(H/'workbook-edit-plan.json');label=next(x['value']for x in plan['cell_changes']if x['sheet']=='Specifications'and x['cell']=='A3');check('188 options' in label and '752 physical' in label and '4 water-build comparator-only' in label and 'no new measured or inspected evidence' in label,'Workbook physical label states current checklist and qualification')
for k,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen baseline/source '+k)
r={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'retained_component_id_records':112,'working_design_groups':111,'active_options':188,'new_native_or_platform_writes':0,'new_physical_verifications':0}
(H/'native-binding-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));assert not issues
