"""Bind the exact owner answer to one additive design-equivalence edge."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'import-summary.json').exists()
p=read(B/'current-master.json');assert p['register_sha256']=='932ffe756c75528ae4ff9d357de5ce817afccc330694a853064f55dbe58ab8c4';OLD=(B/p['register']).parent
D=B/'components/parallel-reviews/decowaves1-owner-design-equivalence-20261024T035709Z';sealpath=D/'sealed-owner-answer-with-scope.json';assert sha(sealpath)=='e7cc9132d00e708a766a0d07114cc78c32ca36f4b8398adb6d02d8fa62147e05'
seal=read(sealpath);evidence={str(sealpath):{'sha256':sha(sealpath)}}
def sealed_files(x):
 for f in x['files']:
  assert sha(f['path'])==f['sha256'],f['path'];evidence[f['path']]={'sha256':f['sha256']}
sealed_files(seal);sealed_files(read(D/'sealed-handoff.json'))
t=read(D/'transcript-evidence.json')
with Path(t['source_path']).open('rb')as f:
 for r in t['records']:
  f.seek(r['byte_offset']);raw=f.read(r['byte_length']);assert hashlib.sha256(raw).hexdigest()==r['raw_line_sha256'];assert json.loads(raw)==r['source_record']
owner=next(r for r in t['records']if r['kind']=='owner_yes');assert owner['source_record']['payload']['role']=='user'and owner['text_verbatim']=='Yes'
supp=read(D/'count-and-transcript-supplement.json');decision=read(D/'design-relationship-decision.json');assert supp['owner_answer_timestamp']==owner['timestamp'] and decision['baseline']['register_sha256']==p['register_sha256']
OUT.mkdir(parents=True,exist_ok=True);(H/'inputs').mkdir(exist_ok=True)
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json'}
for key,name in [('audit','image-coverage-current.json'),('native_map','current-native-reference-map.json'),('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json'),('photo_source','photo-source-review.json'),('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json')]:files[key]=OLD/name
oldout=Path(read(files['source_report_verification'])['output_directory']);files.update(source_count_summary=oldout/'current-count-summary.json',source_photo_requests=oldout/'remaining-photograph-requests.json')
for i,f in enumerate(evidence):files['owner_evidence_'+str(i)]=Path(f)
m={}
for k,f in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(f,snap);m[k]={'path':str(f),'snapshot':str(snap),'sha256':sha(f)}
write(H/'input-manifest.json',m);g=read(m['master_register']['snapshot']);before=copy.deepcopy(g)
pair=decision['confirmed_pair'];ids=[o['product_id']for o in pair];assert ids==['BSI-612EF4DBB555','BSI-8CC6C8AABCB7']
for x in pair:
 o=next(o for o in g['options']if o['product_id']==x['product_id'])
 for k in ['name','file_id','folder_id','image_url','folder_url','canonical_component_id','canonical_design_id']:assert o[k]==x[k],k
edge=copy.deepcopy(supp['proposed_additive_json']['current_owner_design_equivalence_edges'][0]);edge.update(owner_answer_timestamp=owner['timestamp'],owner_answer_verbatim='Yes',source_evidence={'path':str(sealpath),'sha256':sha(sealpath)},exact_pair_references=pair,number2_confirmed=False,terracotta_owner_photo_approval=False)
assert 'current_owner_design_equivalence_edges'not in g
g['current_owner_design_equivalence_edges']=[edge]
mapping={c['component_id']:c['component_id']for c in g['components']};assert len(mapping)==112;mapping['BC-FDW-1']='BC-DECO-1'
groups=[]
for group_id in dict.fromkeys(mapping.values()):
 members=[i for i,v in mapping.items()if v==group_id];options=[o for o in g['options']if o.get('canonical_component_id')in members and o.get('product_id')in g['active_option_ids']]
 groups.append({'working_design_group_id':group_id,'retained_component_ids':members,'active_option_ids':[o['product_id']for o in options],'owner_directly_confirmed_option_ids':ids if len(members)>1 else[],'grouping_basis':'Owner-confirmed number1 pair; existing component membership retained without a new Terracotta photograph approval'if len(members)>1 else'Existing component ID; no new design review in this import'})
assert len(groups)==111 and sum(len(x['retained_component_ids'])for x in groups)==112
projection={**copy.deepcopy(supp['proposed_additive_json']['current_working_design_group_projection']),'groups':groups,'component_id_to_working_group':mapping,'scope':'A projection over the112 retained identified component ID records. This is not a whole-library unique-design, physical cast, mould or stock count. Seven retained Wall Circle visual options and other unresolved sources are not certified by this grouping.','direct_owner_relationships':1}
g['current_working_design_group_projection']=projection
for o in g['options']:
 if o['product_id']in ids:o['current_owner_design_equivalence']={'edge_id':edge['edge_id'],'working_design_group_id':'BC-DECO-1','same_design_as_option_id':next(i for i in ids if i!=o['product_id']),'source_evidence':edge['source_evidence'],'scope':'Same relief design in different finishes; this option retains its own fields, sources, IDs and individual sale scope.'}
for c in g['components']:
 if c['component_id']in ['BC-DECO-1','BC-FDW-1']:
  c['scope_note']='Retained component ID record in working design group BC-DECO-1. Owner confirmed Decowaves1 Verdigris and Frozen Decowaves1 White share the relief design; finish options and specifications remain separate. Existing Terracotta membership is not a new owner photograph approval.'
  c['current_owner_design_group']={'working_design_group_id':'BC-DECO-1','edge_id':edge['edge_id'],'retained_component_id':c['component_id'],'source_evidence':edge['source_evidence']}
g['summary'].update(retained_component_identity_record_count=112,grouped_working_design_identity_count=111,owner_confirmed_design_equivalence_relationships=1)
g['count_definition']+=' The112 retained identified component ID records project to111 working design groups after the exact owner-confirmed Decowaves1/Frozen Decowaves1 relationship; these are not a certified whole-library unique total.'
summary={'status':'OWNER_DECOWAVES1_PAIR_DESIGN_EQUIVALENCE_IMPORTED','recorded_utc':now(),'owner_answer_timestamp':owner['timestamp'],'owner_confirmed_pair_option_ids':ids,'active_options':188,'retained_options':189,'retained_component_id_records':112,'grouped_working_design_identities':111,'new_design_equivalence_edges':1,'component_ids_removed':0,'component_rows_merged':0,'new_photo_bindings':0,'new_physical_verifications':0,'number2_confirmed':False,'terracotta_new_owner_photo_approval':False,'native_or_platform_writes':0}
g['latest_decowaves1_owner_design_equivalence_import']=summary
g['latest_active_photo_source_review']['path']=str(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='SOURCE_PHOTO_COVERAGE_RETAINED_DURING_OWNER_DESIGN_GROUP_IMPORT')
for k,f in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/f).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
write(H/'canonical-master-register.json',g);write(H/'import-summary.json',summary);write(H/'owner-design-edge.json',edge);write(H/'working-design-group-projection.json',projection)
for name in ['image-coverage-current.json','current-assets.json','current-native-reference-map.json','photo-review-queue.json','photo-source-review.json','guided-owner-review-state.json','pending-followups.json','physical-source-audit.json','original-verification.json','guided_review.py','working-entry-owner-provenance-sidecar.json','current-primary-navigation-health.json']:shutil.copy2(OLD/name,H/name)
changes=[]
def diff(x,y,path):
 if isinstance(x,dict)and isinstance(y,dict):
  for k in x.keys()|y.keys():
   if k not in x:changes.append({'group':'register','path':path+[k],'before_exists':False,'current':y[k]})
   else:diff(x[k],y[k],path+[k])
 elif isinstance(x,list)and isinstance(y,list)and len(x)==len(y):
  for i,(v,z)in enumerate(zip(x,y)):diff(v,z,path+[i])
 elif x!=y:changes.append({'group':'register','path':path,'before_exists':True,'before':x,'current':y})
diff(before,g,[]);write(H/'authorized-current-field-changes.json',changes);write(H/'evidence-manifest.json',evidence)
write(H/'source-evidence-verification.json',{'status':'PASS','sealed_owner_evidence_files':len(evidence),'exact_transcript_records_read_back':2,'answer_timestamp':owner['timestamp'],'owner_design_scope_only':ids,'new_native_reads':0,'new_physical_verifications':0})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'pair_option_ids':ids,'pair_component_ids':['BC-DECO-1','BC-FDW-1']})
write(H/'WORK_STATE.json',{'status':'PREPARED_NOT_PUBLISHED','scope':summary})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps({**summary,'metadata_fields_changed':len(changes)}))
