"""Project the verified Fingerprint split without changing image-role claims."""
import copy,hashlib,importlib.util,json,posixpath,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit,quote,unquote
from xml.etree import ElementTree as E
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2];ROOT=BASE.parent
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
op=ROOT/'reports/dropbox-fingerprint-components-2026-10-21/fingerprint-component-split-current-overlay.json'
assert digest(op)=='83003a439f28cddde7eff29128399599141f86e0f1948cff6946d24cfce9925c'
d=read(op);assert d['verification']['status']=='PASS'and d['verification']['pending_native_jobs']==0
assert d['summary']['original_files_preserved']==75 and d['summary']['original_files_with_updated_paths']==35
assert len(d['component_finish_bindings'])==4 and all(x['individual_member_number']is None and x['individual_photo_status']=='Group only'for x in d['component_finish_bindings'])
ptr=read(BASE/'current-master.json');book=BASE/ptr['workbook'];graph=BASE/ptr['register']
assert digest(book)==ptr['workbook_sha256']and digest(graph)==ptr['register_sha256']
sources={'master_workbook':book,'master_register':graph,'master_pointer':BASE/'current-master.json','overlay':op,
 'review_progress':BASE/'components/reviews/specification_review_progress.json','component_checkpoint':BASE/'components/checkpoint.json','root_checkpoint':BASE/'checkpoint.json',
 'owner_ledger':BASE/'components/reviews/user_classifications.json','source_model':BASE/'components/evidence/component_register.json',
 'prior_audit':BASE/ptr['latest_image_coverage_audit']['audit'],'native_metadata':HERE/'fresh-native-metadata.json',
 'verification':op.parent/'verification.json','after_native':op.parent/'after-native-readback.json','split_plan':op.parent/'split-plan.json',
 'squarespace_hold':BASE/'components/parallel-reviews/listing-execution-2026-10-21/SQUARESPACE_WRITE_HOLD.json'}
assert read(sources['squarespace_hold'])['status']=='OWNER_HOLD_NO_SQUARESPACE_WRITES'
manifest={}
for k,p in sources.items():
 s=HERE/'inputs'/(k+'.before')
 if s.exists():assert digest(s)==digest(p),'Input drift '+str(p)
 else:shutil.copy2(p,s)
 manifest[k]={'path':str(p),'snapshot':str(s),'sha256':digest(p)}
write(HERE/'input-manifest.json',manifest)
objects={x['file_id']:x for x in d['objects']}
created={x['file_id']:x for x in d['created_folders']+d['created_reference_documents']}
for md in read(sources['native_metadata']):
 x=objects.get(md['id'])or created.get(md['id']);assert x,md['id']
 assert md['path_display']==x.get('current_path',x.get('path')),(md['id'],md['path_display'],x)
 if md['metadata_type']=='file':assert md['size']==x['size']
maps=sorted(d['prefix_maps'],key=lambda x:len(x['old_path']),reverse=True)
def rewrite_path(p):
 for m in maps:
  old=m['old_path']
  if p.casefold()==old.casefold()or p.casefold().startswith(old.casefold()+'/'):return m['current_path']+p[len(old):]
 return p
def rewrite_url(u):
 if not isinstance(u,str)or not u.startswith('https://www.dropbox.com/'):return u
 p=urlsplit(u);decoded=unquote(p.path)
 for route in ['/home','/preview']:
  if decoded.startswith(route+'/'):
   old=decoded[len(route):];new=rewrite_path(old)
   if old!=new:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return u
g=read(graph);oldg=copy.deepcopy(g);changes=[]
def project(node,path):
 for k in ['image_url','folder_url','context_image_url','context_folder_url']:
  if node.get(k):
   new=rewrite_url(node[k])
   if new!=node[k]:changes.append({'path':path+[k],'before':node[k],'after':new});node[k]=new
for k in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
 for i,x in enumerate(g[k]):project(x,[k,i])
for k in ['source_sets','source_offer_edges']:
 for i,x in enumerate(g[k]):project(x.get('current_primary_reference',{}),[k,i,'current_primary_reference'])
for i,x in enumerate(g['arrangement_context_references']):
 project(x,['arrangement_context_references',i])
 for j,im in enumerate(x.get('images',[])):project(im,['arrangement_context_references',i,'images',j])
for binding in d['component_finish_bindings']:
 opt=next(x for x in g['options']if x['product_id']==binding['product_id']);assert opt['canonical_component_id']==binding['component_id']
 opt['component_folder_binding']=copy.deepcopy(binding)
for comp in g['components']:
 bs=[x for x in d['component_finish_bindings']if x['component_id']==comp['component_id']]
 if bs:comp['component_finish_folder_bindings']=copy.deepcopy(bs)
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);b=n.load(book)
links=[];link_changes=[]
for sn,s in b['sheets'].items():
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={r.get('Id'):r for r in E.fromstring(b['files'][rp])}
 for h in s['root'].findall('.//'+n.q('hyperlink')):
  before='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target');after=rewrite_url(before)
  rec={'sheet':sn,'cell':h.get('ref'),'target':after,'label':b['values'][sn][h.get('ref')]};links.append(rec)
  if before!=after:link_changes.append({**rec,'before':before})
# The new component folders are separate from image-containing arrangement folders.
rows=[]
for binding in d['component_finish_bindings']:
 opt=next(x for x in g['options']if x['product_id']==binding['product_id']);im=objects[opt['file_id']];parent=objects[im['current_parent_id']]
 assert opt['folder_id']==im['current_parent_id']and opt['photo_coverage']['individual']=='Group only'
 def link(label,target):return{'label':label,'target':target}
 rows.append([opt['product_id'],opt['name'],binding['finish'],link('Component folder',binding['component_folder_url']),link('Finish folder',binding['finish_folder_url']),
  link('Pair/group references',binding['reference_document_url']),link('Pair example',im['current_native_url']),link('Actual image folder',parent['current_native_url']),
  binding['component_folder_id'],binding['finish_folder_id'],binding['reference_document_id'],im['file_id'],parent['file_id'],'Group only','2',
  'Complete isolated individual image still required. Pair/group images remain arrangement references; source composition2 contains both Left/Right members.'])
sheet={'title':'Fingerprint component folders and image references','note':'Folder split verified21 October. Component/finish folders hold reference documents; actual pair photographs stay under Arrangements. Four isolated individual-image gaps remain.',
 'headers':['Option ID','Accepted sculpture / option','Finish','Component folder','Finish folder','Reference document','Example image','Containing image folder','Component folder ID','Finish folder ID','Reference document ID','Example file ID','Image folder ID','Individual image status','Whole composition label','Scope and next action'],
 'widths':[25,49,15,25,25,30,24,29,35,35,35,35,35,24,24,88],'rows':rows}
write(HERE/'workbook-data.json',{'sheets':{'Fingerprint Folders':sheet}})
write(HERE/'workbook-edit-plan.json',{'hyperlinks':links,'target_changes':link_changes,'graph_changes':changes,'old_sheet_count':20,'new_sheet_count':1,'old_cell_value_changes':0,
 'preview_ranges':[['Fingerprint Folders','A2:H5','01-fingerprint-summary'],['Fingerprint Folders','A9:H13','02-component-image-folders'],['Fingerprint Folders','I9:P13','03-stable-IDs-and-gaps']]})
audit=read(sources['prior_audit']);oldcounts=copy.deepcopy(audit['counts'])
def rebase(node):
 if isinstance(node,list):return[rebase(x)for x in node]
 if isinstance(node,dict):return{k:rebase(x)for k,x in node.items()}
 if isinstance(node,str):
  if node.startswith('https://www.dropbox.com/'):return rewrite_url(node)
  if node.startswith('ns:202238505//'):return'ns:202238505/'+rewrite_path('/'+node.split('//',1)[1].lstrip('/'))
  if node.startswith('/BOLDSTONE MASTER/'):return rewrite_path(node)
 return node
audit=rebase(audit);audit['recorded_utc']=now();audit['fingerprint_component_folder_bindings']=copy.deepcopy(d['component_finish_bindings'])
audit['latest_path_refresh']={'overlay':manifest['overlay'],'prior_audit':manifest['prior_audit'],'image_roles_and_counts_unchanged':True,'reference_documents_are_photographs':False}
assert audit['counts']==oldcounts
write(HERE/'image-coverage-current.json',audit)
g['historical_image_coverage_before_fingerprint_split']=copy.deepcopy(g['latest_image_coverage_audit'])
g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'recorded_utc':now(),'audit':str((HERE/'image-coverage-current.json').relative_to(BASE)),'audit_sha256':digest(HERE/'image-coverage-current.json'),
 'verification':str((HERE/'saved-file-verification.json').relative_to(BASE)),'component_folder_sheet':'Fingerprint Folders'}
for k in ['verification_sha256','visual_verification','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
scope={'status':'COMPLETE_VERIFIED_FINGERPRINT_COMPONENT_AND_IMAGE_FOLDER_BINDINGS','recorded_utc':now(),'overlay':manifest['overlay'],
 'summary':d['summary'],'component_finish_bindings':d['component_finish_bindings'],'graph_reference_changes':changes,
 'actual_image_folders_preserved':True,'new_individual_photographs':0,'individual_gaps_retained':4,'source_composition_number':'2','individual_member_numbers':None,
 'accepted_names_or_specifications_changed':0,'new_catalogue_records':0,'native_link_destinations_updated':len(link_changes),'root_remote_writes':0,'squarespace_write_hold':manifest['squarespace_hold']}
g['latest_fingerprint_component_paths']=scope
restored=copy.deepcopy(g)
for opt in restored['options']:opt.pop('component_folder_binding',None)
for comp in restored['components']:comp.pop('component_finish_folder_bindings',None)
restored['latest_image_coverage_audit']=copy.deepcopy(oldg['latest_image_coverage_audit'])
for k in ['historical_image_coverage_before_fingerprint_split','latest_fingerprint_component_paths']:restored.pop(k)
for c in changes:
 node=restored
 for k in c['path'][:-1]:node=node[k]
 node[c['path'][-1]]=c['before']
assert restored==oldg
write(HERE/'canonical-master-register.json',g)
write(HERE/'preparation-verification.json',{'status':'PASS','graph_current_reference_changes':len(changes),'native_link_destinations_updated':len(link_changes),'new_component_finish_bindings':4,
 'new_photographs':0,'individual_gaps':26,'all184_names1104_fields_and_listing_source_layers_preserved':True,'squarespace_write_hold_preserved':True})
print(json.dumps(read(HERE/'preparation-verification.json')))
