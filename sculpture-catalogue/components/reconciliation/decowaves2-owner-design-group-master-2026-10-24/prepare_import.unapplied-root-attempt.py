"""Recover one exact Number2 owner answer and extend the additive design groups."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'import-summary.json').exists()
p=read(B/'current-master.json');assert p['register_sha256']=='164211ed960d363e3e249142096997821ff80c63404a5ee8db6254959f9a42e5';OLD=(B/p['register']).parent
D=B/'components/parallel-reviews/decowaves2-owner-answer-recovery-20261024';sealpath=D/'sealed-handoff.json';assert sha(sealpath)=='06d6dbd345c81f5e1bc0505020f614b71dc42aac28e685ac009554f8b009e161';seal=read(sealpath)
evidence={str(sealpath):{'sha256':sha(sealpath)}}
for f in seal['files']:assert sha(f['path'])==f['sha256'] and Path(f['path']).stat().st_size==f['bytes'];evidence[f['path']]={'sha256':f['sha256']}
t=read(D/'transcript-evidence.json')
with Path(t['source_path']).open('rb')as f:
 first=f.readline();assert hashlib.sha256(first).hexdigest()==t['session_meta_sha256'];assert json.loads(first)['payload']['id']==t['session_id']
 for r in t['records']:
  f.seek(r['byte_offset']);raw=f.read(r['byte_length']);assert hashlib.sha256(raw).hexdigest()==r['raw_line_sha256'] and json.loads(raw)==r['source_record']
assert len(t['records'])==3 and all(r['text_verbatim']=='wYes'for r in t['records'][1:])
OUT.mkdir(parents=True,exist_ok=True);(H/'inputs').mkdir(exist_ok=True)
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json'}
for key,name in [('audit','image-coverage-current.json'),('native_map','current-native-reference-map.json'),('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json'),('photo_source','photo-source-review.json'),('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json')]:files[key]=OLD/name
oldout=Path(read(files['source_report_verification'])['output_directory']);files.update(source_count_summary=oldout/'current-count-summary.json',source_photo_requests=oldout/'remaining-photograph-requests.json')
for i,f in enumerate(evidence):files['owner_evidence_'+str(i)]=Path(f)
m={}
for k,f in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(f,snap);m[k]={'path':str(f),'snapshot':str(snap),'sha256':sha(f)}
write(H/'input-manifest.json',m);g=read(m['master_register']['snapshot']);before=copy.deepcopy(g)
edge=read(D/'owner-design-edge.json');ids=edge['owner_confirmed_option_ids'];assert ids==['BSI-FE830AE502C3','BSI-837E9B0B3B36']
for x in edge['exact_pair_references']:
 o=next(o for o in g['options']if o['product_id']==x['product_id']);assert all(o[k]==v for k,v in x.items())
edge.update(import_authority={'path':str(sealpath),'sha256':sha(sealpath)},number2_confirmed=True)
assert len(g['current_owner_design_equivalence_edges'])==1;g['current_owner_design_equivalence_edges'].append(edge)
mapping={c['component_id']:c['component_id']for c in g['components']};mapping.update({'BC-FDW-1':'BC-DECO-1','BC-FDW-2':'BC-DECO-2'});groups=[]
for gid in dict.fromkeys(mapping.values()):
 members=[i for i,v in mapping.items()if v==gid];opts=[o for o in g['options']if o.get('canonical_component_id')in members and o['product_id']in g['active_option_ids']];authority=next((x for x in g['current_owner_design_equivalence_edges']if set(x['component_ids'])==set(members)),None)
 groups.append({'working_design_group_id':gid,'retained_component_ids':members,'active_option_ids':[o['product_id']for o in opts],'owner_directly_confirmed_option_ids':authority['owner_confirmed_option_ids']if authority else[],'grouping_basis':('Owner-confirmed numbered pair; existing component membership retained without a new Terracotta photograph approval'if authority else'Existing component ID; no new design review in this import')})
proj=copy.deepcopy(g['current_working_design_group_projection']);proj.pop('one_equivalence_group',None);proj.update(grouped_working_design_identity_count=110,equivalence_groups=[x['component_ids']for x in g['current_owner_design_equivalence_edges']],groups=groups,component_id_to_working_group=mapping,direct_owner_relationships=2)
assert len(groups)==110 and sum(len(x['retained_component_ids'])for x in groups)==112;g['current_working_design_group_projection']=proj
for o in g['options']:
 if o['product_id']in ids:o['current_owner_design_equivalence']={'edge_id':edge['edge_id'],'working_design_group_id':'BC-DECO-2','same_design_as_option_id':next(i for i in ids if i!=o['product_id']),'source_evidence':edge['import_authority'],'scope':'Same relief design in different finishes; this option retains its own fields, sources, IDs and individual sale scope.'}
for c in g['components']:
 if c['component_id']in edge['component_ids']:
  c['scope_note']='Retained component ID record in working design group BC-DECO-2. Owner confirmed Decowaves2 Verdigris and Frozen Decowaves2 White share the relief design; finish options and specifications remain separate. Existing Terracotta membership is not a new owner photograph approval.'
  c['current_owner_design_group']={'working_design_group_id':'BC-DECO-2','edge_id':edge['edge_id'],'retained_component_id':c['component_id'],'source_evidence':edge['import_authority']}
g['summary'].update(grouped_working_design_identity_count=110,owner_confirmed_design_equivalence_relationships=2)
g['count_definition']='Active individually offered finish/size/build options, excluding retired options. All189 history rows are retained;188 remain current. The112 retained identified component ID records project to110 working design groups after two separate owner-confirmed Decowaves/Frozen Decowaves number1 and number2 relationships. These are not physical cast, mould or stock counts, or a certified whole-library unique total.'
summary={'status':'OWNER_DECOWAVES2_PAIR_DESIGN_EQUIVALENCE_IMPORTED','recorded_utc':now(),'owner_answer_timestamp':edge['owner_answer_timestamp'],'duplicate_retry_timestamp':edge['duplicate_retry_timestamp'],'owner_answer_verbatim':'wYes','counted_owner_decisions':1,'owner_confirmed_pair_option_ids':ids,'active_options':188,'retained_options':189,'retained_component_id_records':112,'grouped_working_design_identities':110,'new_design_equivalence_edges':1,'total_design_equivalence_edges':2,'component_ids_removed':0,'component_rows_merged':0,'new_photo_bindings':0,'new_physical_verifications':0,'terracotta_new_owner_photo_approval':False,'native_or_platform_writes':0}
g['latest_decowaves2_owner_design_equivalence_import']=summary;g['latest_active_photo_source_review']['path']=str(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='SOURCE_PHOTO_COVERAGE_RETAINED_DURING_OWNER_NUMBER2_DESIGN_GROUP_IMPORT')
for k,f in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/f).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for name in ['image-coverage-current.json','current-assets.json','current-native-reference-map.json','photo-review-queue.json','photo-source-review.json','guided-owner-review-state.json','pending-followups.json','physical-source-audit.json','original-verification.json','guided_review.py','working-entry-owner-provenance-sidecar.json','current-primary-navigation-health.json','physical-checklist-label-alignment.json']:shutil.copy2(OLD/name,H/name)
for f,x in [('canonical-master-register.json',g),('import-summary.json',summary),('owner-design-edge.json',edge),('working-design-group-projection.json',proj)]:write(H/f,x)
changes=[]
def diff(x,y,path):
 if isinstance(x,dict)and isinstance(y,dict):
  for k in x.keys()|y.keys():
   if k not in x:changes.append({'group':'register','path':path+[k],'before_exists':False,'current':y[k]})
   elif k not in y:changes.append({'group':'register','path':path+[k],'before_exists':True,'before':x[k],'current_exists':False})
   else:diff(x[k],y[k],path+[k])
 elif isinstance(x,list)and isinstance(y,list)and len(x)==len(y):
  for i,(v,z)in enumerate(zip(x,y)):diff(v,z,path+[i])
 elif x!=y:changes.append({'group':'register','path':path,'before_exists':True,'before':x,'current':y})
diff(before,g,[]);write(H/'authorized-current-field-changes.json',changes);write(H/'evidence-manifest.json',evidence)
write(H/'source-evidence-verification.json',{'status':'PASS','sealed_owner_evidence_files':len(evidence),'exact_transcript_records_read_back':3,'owner_decisions_counted':1,'duplicate_answer_retry_retained':True,'owner_design_scope_only':ids,'new_native_reads':0,'new_physical_verifications':0})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'pair_option_ids':ids,'pair_component_ids':edge['component_ids']});write(H/'WORK_STATE.json',{'status':'PREPARED_NOT_PUBLISHED','scope':summary})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps({**summary,'metadata_fields_changed':len(changes)}))
