"""Check the navigation observation independently of source-photo content counts."""
import copy,csv,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(m['master_register']['snapshot']);oa=read(m['audit']['snapshot']);nav=read(H/'current-primary-navigation-health.json');plan=read(H/'workbook-edit-plan.json');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
groups={'register':('canonical-master-register.json','master_register'),'audit':('image-coverage-current.json','audit'),'assets':('current-assets.json','report_assets'),'native_map':('current-native-reference-map.json','native_map'),'reviews':('photo-review-queue.json','report_reviews'),'photo_source':('photo-source-review.json','photo_source')}
changes=read(H/'authorized-current-field-changes.json')
for group,(file,source)in groups.items():
 current=read(H/file);restored=copy.deepcopy(current)
 for c in [c for c in changes if c['group']==group]:
  x=restored
  for key in c['path'][:-1]:x=x[key]
  key=c['path'][-1]
  check(c.get('current_exists',True)and x[key]==c['current'],'Exact declared after-value '+group+str(c['path']))
  if c['before_exists']:x[key]=c['before']
  else:del x[key]
 check(restored==read(m[source]['snapshot']),'All undeclared '+group+' data preserved by reversible projection')
for x,y in zip(g['options'],old['options']):
 for key in ['product_id','file_id','folder_id','name','canonical_component_id','master_fields','specifications','selling_details','photo_coverage','physical_specifications_verified']:
  check(x.get(key)==y.get(key),'Preserved '+key+' '+x['product_id'])
for x,y in zip(a['coverage'],oa['coverage']):
 for key in ['option_id','owner_review','series_required','scope','scene_origin']:
  check(x.get(key)==y.get(key),'Retained owner/coverage qualification '+key+' '+x['option_id'])
 for role in ['individual','in_situ','series']:
  check(x[role]['status']==y[role]['status'],'Source photo status retained '+role+' '+x['option_id'])
  for key in ['file_id','folder_id']:
   check((x[role].get('reference')or{}).get(key)==(y[role].get('reference')or{}).get(key),'Selected role identity retained '+role+' '+key+' '+x['option_id'])
check(g['summary']==old['summary']and a['counts']==oa['counts'],'Catalogue and source-photo counts unchanged')
check(g['current_authenticated_squarespace_inventory_observation']==old['current_authenticated_squarespace_inventory_observation'],'Exact captured platform observation preserved')
for k in ['source_offer_edges','source_sets','source_component_dispositions','original_review_specification_assertions','wall_circle_native_options','listing_resolution_native_action_drafts']:
 # Only explicit current-primary navigation inside a historical offer may normalize.
 for c in changes:
  if c['group']=='register'and c['path'][0]==k:check('current_primary_reference'in c['path'],'No raw/source offer mutation '+str(c['path']))
check(len(nav['rows'])==48 and len({r['product_id']for r in nav['rows']})==48,'48 unique observed options')
check(sum(r['file_verified_by_id']for r in nav['rows'])==46 and all(r['folder_verified_by_id']for r in nav['rows']),'46 selected files and all48 containing folders verified')
unresolved=[o for o in g['options']if o.get('current_primary_navigation')]
check({o['product_id']for o in unresolved}=={'BSI-D5A939264C82','BSI-65520F070145'},'Exactly two held Wall Circle navigation annotations')
for o in unresolved:
 n=o['current_primary_navigation'];check(not n['current_primary_verified']and n['folder_verified']and not n['replacement_selected']and not n['global_deletion_inferred']and not n['web_url_openability_verified']and n['owner_hold_preserved'],'No replacement, deletion or web-access inference '+o['product_id'])
 for sn,col in [('Master Catalogue','N'),('Photo Coverage','D')]:
  row=next(i for i,x in enumerate(g['options'],10)if x['product_id']==o['product_id']);check(any(x['sheet']==sn and x['cell']==col+str(row)and x['value']=='Saved image (unverified)'for x in plan['cell_changes']),'Workbook link label exposes unresolved native primary '+o['product_id'])
for file,key in [('physical-source-audit.json','physical_audit'),('original-verification.json','originals'),('guided-owner-review-state.json','review_state'),('pending-followups.json','pending')]:check(sha(H/file)==m[key]['sha256'],'Unchanged '+file)
check(g['options'][138]['image_url'].startswith('https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Moonwater%20Catcher/'),'MWC capitalization corrected')
check(not any(o['physical_specifications_verified']for o in g['options']),'No new physical verification')
reports=read(H/'report-verification.json');out=Path(reports['output_directory'])
with (out/'Current_Individual_Options_188.csv').open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
check(len(rows)==188,'188 current CSV options')
check(sum(bool(r['current_primary_native_status'])for r in rows)==48,'CSV checked/unchecked scope separated')
check(sum(r['current_primary_file_verified']=='False'for r in rows)==2,'Both unresolved selected references exposed in CSV')
check(read(out/'remaining-photograph-requests.json')==read(m['source_photo_requests']['snapshot']),'No new capture prompts')
for k,x in m.items():check(sha(x['path'])==sha(x['snapshot'])==x['sha256'],'Frozen baseline/evidence '+k)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'checked_options':48,'unresolved_primary_files':2,'new_native_or_platform_writes':0,'physical_verifications':0,'new_capture_requests':0}
(H/'native-binding-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if issues:raise SystemExit(1)
