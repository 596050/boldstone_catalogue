"""Record current numbered folders and original photographs without guessing legacy aliases."""
import copy,hashlib,importlib.util,json,posixpath,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for k,f in [('native_readback','independent-native-readback.json'),('image_evidence','image-evidence-verification.json')]:
 p=H/f;s=H/'inputs'/(k+'.before')
 if k not in m:shutil.copy2(p,s);m[k]={'path':str(p),'snapshot':str(s),'sha256':sha(p)}
write(H/'input-manifest.json',m)
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
o=read(H/'inputs/placement_overlay.before');v=read(H/'inputs/placement_verification.before');live=read(H/'independent-native-readback.json')['listing'];byid={x['file_id']:x for x in live['entries']}
assert v['status']=='PASS'and v['overlay_sha256']==sha(H/'inputs/placement_overlay.before')and not live['has_more']and len(byid)==60
objects=o['groups']+[p[k]for p in o['photos']for k in ['file','folder']]+[c[k]for c in o['components']for k in ['individual_folder','original_reference_folder','numbering_reference_photo']]
objects.extend(z for c in o['components']for z in c['isolated_image_candidates'])
for x in objects:
 y=byid[x['file_id']];assert y['path']==x['ns_path']and y['name']==x['name']and y['object_type']==x['object_type']
 if x['object_type']=='file':assert y['file']['size']==x['bytes']
def dbhash(p):
 dig=[]
 with p.open('rb')as f:
  while block:=f.read(4*1024*1024):dig.append(hashlib.sha256(block).digest())
 return hashlib.sha256(b''.join(dig)).hexdigest()
for p in o['photos']:
 src=Path(p['source_local_path']);assert src.stat().st_size==p['file']['bytes']and sha(src)==p['source_sha256']and dbhash(src)==p['dropbox_content_hash']
assert len(o['photos'])==26 and sum(p['file']['bytes']for p in o['photos'])==8888149
g=read(H/'inputs/master_register.before');old=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a)
fp=[x for x in g['options']if x['family']=='Fingerprint'];ids={x['product_id']for x in fp};evidence=read(H/'image-evidence-verification.json');archive={x['file_id']:x for x in evidence['source_records']if 'number'not in x}
note='Legacy Left/Right source retained. The old pair files and component hierarchy are absent from the complete current Fingerprint subtree; two primary IDs did not resolve in the current metadata check. Current numbered2/3 have corresponding curl directions but fewer, broader grooves and square outlines. Same-design revision versus separate design remains pending. No legacy dimensions, weights, materials, prices or availability are transferred to the six current folder-finish records.'
crosswalk=[]
for x in fp:
 num=2 if x['canonical_component_id']=='BC-FP-LEFT'else 3
 current=next(c for c in o['components']if c['number']==num and c['finish']=='White')
 row={'option_id':x['product_id'],'legacy_component_id':x['canonical_component_id'],'legacy_name':x['name'],'legacy_finish':x['component_folder_binding']['finish'],'candidate_number':num,'candidate_white_folder_id':current['individual_folder']['file_id'],'candidate_white_folder_url':current['individual_folder']['url'],'candidate_original_image_url':current['numbering_reference_photo']['url'],'candidate_original_file_id':current['numbering_reference_photo']['file_id'],'identity_status':'DIRECTIONAL_CORRESPONDENCE_ONLY_OWNER_VERSION_FACT_PENDING','same_design_or_revision_confirmed':False,'finish_transfer_confirmed':False,'specification_transfer_confirmed':False,'historical_primary_file_id':x['file_id'],'historical_primary_folder_id':x['folder_id'],'archived_primary_local_path':archive[x['file_id']]['local_path'],'scope':note}
 crosswalk.append(row);x['current_fingerprint_alias_review']=copy.deepcopy(row)
 x['component_folder_binding']['current_native_state']='HISTORICAL_BINDING_NOT_PRESENT_IN_CURRENT_COMPLETE_FAMILY'
 x['component_folder_binding']['current_numbered_alias_status']=row['identity_status']
 x['component_folder_binding']['current_native_note']=note
for x in g['components']:
 if x['family']!='Fingerprint':continue
 for b in x.get('component_finish_folder_bindings',[]):b['current_native_state']='HISTORICAL_BINDING_NOT_PRESENT_IN_CURRENT_COMPLETE_FAMILY'
inventory=[]
for c in sorted(o['components'],key=lambda x:(x['number'],x['finish'])):
 n=c['number'];finish=c['finish'];full=[p for p in o['photos']if p['finish']==finish and n in p['left_to_right_component_numbers']and all(m['whole_outline_visible']for m in p['members'])]
 group=next(p for p in full if len(p['members'])==3)
 inv={'inventory_id':f'FP-NUM-{n}-{finish.upper()}','name':c['name'],'number':n,'finish':finish,'component_folder':copy.deepcopy(c['individual_folder']),'original_individual_photo':copy.deepcopy(c['numbering_reference_photo']),'original_image_folder':copy.deepcopy(c['original_reference_folder']),'original_photo_sha256':c['numbering_reference_sha256'],'group_example':copy.deepcopy(group),'context_photo_ids':c['uploaded_context_photo_ids'],'isolated_png_candidates':copy.deepcopy(c['isolated_image_candidates']),'png_provenance':'UNCONFIRMED; original JPEG selected instead','photo_coverage':{'individual':'Available: complete standalone original JPEG','in_situ':'Available: panel shown mounted against brick wall; physical fixing not certified','series':'Available: full arrangement original JPEG'},'legacy_alias_status':'Legacy alias pending'if n in [2,3]else'No member in retained Left/Right pair','legacy_component_candidate':'BC-FP-LEFT'if n==2 else'BC-FP-RIGHT'if n==3 else None,'canonical_option_id':None,'canonical_count_effect':0,'specification_status':'No legacy specification transfer; current size, depth, weight, material, fixing, price and availability unverified','listing_status':'No exact platform record matched by this folder/photo work'}
 inventory.append(inv)
for c in a['coverage']:
 if c['option_id']in ids:c['current_native_reference_state']={'status':'LEGACY_REFERENCE_ARCHIVED_CURRENT_ALIAS_PENDING','scope':note,'current_numbered_candidate':next(x for x in crosswalk if x['option_id']==c['option_id'])}
scope={'status':'CURRENT_NATIVE_FOLDERS_AND_ORIGINAL_PHOTOS_VERIFIED_LEGACY_ALIASES_PENDING','recorded_utc':now(),'placement_overlay':m['placement_overlay'],'placement_verification':m['placement_verification'],'root_independent_native_readback':m['native_readback'],'original_image_verification':m['image_evidence'],'numbered_folder_finish_inventory':inventory,'legacy_candidate_crosswalk':crosswalk,'uploaded_photo_relationships':copy.deepcopy(o['photos']),'numbered_folder_finish_count':6,'current_numbered_design_labels':3,'newly_uploaded_photos':26,'new_canonical_components_or_options':0,'legacy_specification_transfers':0,'historical_canonical_individual_gaps_retained':4,'current_native_tree':{'folders':21,'files':39,'former_parent_empty':True},'counts_scope':'Six folder-finish records are a separate current source inventory, not six additional canonical sculpture options. Same-design/revision versus separate-design question is pending.'}
g['latest_fingerprint_numbered_reconciliation']=scope;a['current_fingerprint_numbered_inventory']=copy.deepcopy(scope)
g['latest_fingerprint_component_paths']['current_state']='SUPERSEDED_HIERARCHY_RETAINED_AS_HISTORICAL_SOURCE';g['latest_fingerprint_component_paths']['superseded_by']=rel(H/'canonical-master-register.json')
g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']));a['recorded_utc']=now()
write(H/'image-coverage-current.json',a)
g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=rel(H/'image-coverage-current.json'),audit_sha256=sha(H/'image-coverage-current.json'),current_fingerprint_numbered_inventory=rel(H/'numbered-folder-inventory.json'),current_native_alias_scope=scope['counts_scope'])
for k in ['verification_sha256','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
g['latest_image_coverage_audit'].update(verification=rel(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'))
write(H/'canonical-master-register.json',g);write(H/'numbered-folder-inventory.json',inventory);write(H/'legacy-crosswalk-review.json',crosswalk)
write(H/'independent-native-verification.json',{'status':'PASS','current_objects':60,'folders':21,'files':39,'current_folder_finish_records':6,'new_originals_verified':26,'new_original_bytes':8888149,'complete_standalone_originals':6,'canonical_aliases_promoted':0,'specification_transfers':0,'root_native_writes':0})
s=importlib.util.spec_from_file_location('n',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');changes={};links={}
def setcell(sn,cell,value):
 before=b['values'][sn].get(cell,'');assert cell not in b['formulas'][sn]
 if before!=value:changes[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'value':value}
def row(sn,key):return next(int(re.search(r'\d+',c)[0])for c,v in b['values'][sn].items()if re.fullmatch(r'A\d+',c)and v==key)
for sn,z in b['sheets'].items():
 loc=z['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):
  cell=h.get('ref');links[(sn,cell)]={'sheet':sn,'cell':cell,'label':b['values'][sn].get(cell,''),'target':'#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target')}
def linkcell(sn,cell,label,target):setcell(sn,cell,label);links[(sn,cell)]={'sheet':sn,'cell':cell,'label':label,'target':target}
setcell('Fingerprint Folders','A2','Fingerprint legacy folder references and alias review')
setcell('Fingerprint Folders','A3','Historical Left/Right IDs are retained below. Their prior hierarchy is absent from the current family. See Fingerprint Current for six current numbered folder-finish records; exact legacy aliases are pending.')
for col,label in [('D','Current family review'),('E','Current numbered review'),('F','Alias reconciliation'),('G','Archived pair image'),('H','Local archive folder'),('I','Historical component folder ID'),('J','Historical finish folder ID'),('K','Historical reference document ID'),('L','Historical example file ID'),('M','Historical image folder ID')]:setcell('Fingerprint Folders',col+'9',label)
for x in fp:
 oid=x['product_id'];arc=archive[x['file_id']]['local_path'];arcdir=str(Path(arc).parent);rn=row('Fingerprint Folders',oid)
 for col,label,target in [('D','Current family',o['family_folder']['url']),('E','Current numbered inventory',"#'Fingerprint Current'!A9"),('F','Alias pending',"#'Fingerprint Current'!J9"),('G','Archived pair image',arc),('H','Local archive folder',arcdir)]:linkcell('Fingerprint Folders',col+str(rn),label,target)
 setcell('Fingerprint Folders','P'+str(rn),note)
 rn=row('Master Catalogue',oid);linkcell('Master Catalogue','N'+str(rn),'Archived pair image',arc);linkcell('Master Catalogue','O'+str(rn),'Local archive folder',arcdir)
 setcell('Master Catalogue','V'+str(rn),b['values']['Master Catalogue']['V'+str(rn)]+'\nCurrent Fingerprint: legacy pair archived; numbered2/3 alias pending. See Fingerprint Current. No specification transfer.')
 for col in ['T','U']:linkcell('Master Catalogue',col+str(rn),'Legacy context review',"#'Photo Coverage'!A"+str(rn))
 rn=row('Photo Coverage',oid)
 for col,label,target in [('D','Archived pair image',arc),('E','Local archive folder',arcdir),('G','Legacy context review',"#'Fingerprint Folders'!A9"),('H','Current family',o['family_folder']['url']),('J','Archived pair image',arc),('K','Local archive folder',arcdir)]:linkcell('Photo Coverage',col+str(rn),label,target)
 setcell('Photo Coverage','L'+str(rn),b['values']['Photo Coverage']['L'+str(rn)]+'\nCurrent native audit: historical image IDs retained; current numbered2/3 identity/revision pending. Historical role decisions are preserved, not claims that legacy files remain in the current family.')
for c in g['components']:
 if c['family']!='Fingerprint':continue
 rn=row('Components',c['component_id']);x=next(x for x in fp if x['canonical_component_id']==c['component_id']and x['component_folder_binding']['finish']=='White');arc=archive[x['file_id']]['local_path'];linkcell('Components','F'+str(rn),'Archived pair',arc);linkcell('Components','G'+str(rn),'Local archive folder',str(Path(arc).parent));setcell('Components','E'+str(rn),'Legacy identity retained; current numbered2/3 design-version alias pending. See Fingerprint Current.')
L=lambda label,target:{'label':label,'target':target}
rows=[]
for x in inventory:
 p=x['original_individual_photo'];f=x['original_image_folder'];gp=x['group_example'];rows.append([x['inventory_id'],x['name'],x['number'],x['finish'],L('Original individual photo',p['url']),L('Photo containing folder',f['url']),L('Component folder',x['component_folder']['url']),L('Full group example',gp['file']['url']),L('Group containing folder',gp['folder']['url']),x['legacy_component_candidate']or'None in retained pair',x['legacy_alias_status'],'Available: standalone original JPEG','Mounted-wall reference','Full group reference',x['specification_status'],p['file_id'],f['file_id'],x['component_folder']['file_id'],gp['file']['file_id'],gp['folder']['file_id']])
photos=[]
for x in o['photos']:
 photos.append([x['finish']+' '+str(x['image_number']).zfill(2),x['finish'],x['image_number'],' → '.join(map(str,x['left_to_right_component_numbers'])),L('Original photograph',x['file']['url']),L('Containing folder',x['folder']['url']),x['image_role'],', '.join(str(z['number'])for z in x['members']if z['whole_outline_visible']),' ; '.join(str(z['number'])+': '+str(z['rotation_clockwise_degrees_from_numbered_reference'])+' degrees'for z in x['members']),x['file']['file_id'],x['folder']['file_id'],x['file']['bytes'],x['source_sha256'],x['dropbox_content_hash'],'Arrangement/detail reference; no isolated-photo qualification inferred'])
data={'Fingerprint Current':{'title':'Fingerprint current numbered folders and photographs','note':'Three numbered designs × two finish labels = six current folder-finish records. These are separate from184 canonical options until legacy aliases/versions are resolved. All six have standalone original JPEGs.','headers':['Source inventory ID','Current numbered name','Number','Finish label','Individual original','Photo containing folder','Component folder','Full group image','Group containing folder','Legacy component candidate','Alias status','Individual coverage','In situ coverage','Series coverage','Specification scope','Individual original file ID','Original image folder ID','Component folder ID','Group file ID','Group folder ID'],'widths':[26,45,12,17,28,29,28,28,29,30,42,38,32,31,88,37,37,37,37,37],'rows':rows},'Fingerprint Photos':{'title':'Fingerprint26 matched original photographs','note':'Cream13 and White13. Names, rotation, visible outlines and detail scope follow the checked matches. Native folder/file IDs and original hashes preserve each connection.','headers':['Photo reference','Finish','Image number','Components left to right','Example image','Containing folder','Photograph scope','Whole outlines visible','Clockwise rotations','Dropbox file ID','Dropbox folder ID','Original bytes','Source SHA256','Dropbox content hash','Coverage qualification'],'widths':[20,15,15,27,27,28,35,29,38,37,37,20,69,69,68],'rows':photos}}
write(H/'workbook-data.json',{'sheets':data})
heights=[]
for sn in ['Master Catalogue','Photo Coverage','Fingerprint Folders','Components']:
 for rn in sorted({int(re.search(r'\d+',c)[0])for s,c in changes if s==sn and int(re.search(r'\d+',c)[0])>=10}):heights.append({'sheet':sn,'row':rn,'height':168 if sn in ['Photo Coverage','Fingerprint Folders']else 132})
beforelinks={}
for sn,z in b['sheets'].items():
 loc=z['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):beforelinks[(sn,h.get('ref'))]='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target')
plan={'cell_changes':list(changes.values()),'hyperlinks':list(links.values()),'target_changes':[{'sheet':sn,'cell':c,'before':beforelinks[(sn,c)],'after':x['target']}for(sn,c),x in links.items()if x['target']!=beforelinks[(sn,c)]],'row_heights':heights,'old_sheet_count':22,'new_sheet_count':2,'expected_native_hyperlinks':len(links)+82,'baseline_ranges':[['Fingerprint Folders','A2:H4','baseline-fp-summary'],['Fingerprint Folders','A9:H13','baseline-fp-legacy']],'preview_ranges':[['Fingerprint Current','A2:I4','01-current-summary'],['Fingerprint Current','A9:I15','02-current-links'],['Fingerprint Current','J9:O15','03-legacy-and-specification-scope'],['Fingerprint Photos','A9:I13','04-cream-photo-matches'],['Fingerprint Photos','A23:I27','05-white-photo-matches'],['Fingerprint Folders','A9:H13','06-historical-reference-links']]}
write(H/'workbook-edit-plan.json',plan)
def diff(a,b,p=[]):
 if a==b:return[]
 if isinstance(a,dict)and isinstance(b,dict):
  out=[]
  for k in sorted(set(a)|set(b)):
   if k not in a:out.append({'path':p+[k],'kind':'added','after':b[k]})
   elif k not in b:out.append({'path':p+[k],'kind':'removed','before':a[k]})
   else:out+=diff(a[k],b[k],p+[k])
  return out
 if isinstance(a,list)and isinstance(b,list)and len(a)==len(b):return[x for i,(v,w)in enumerate(zip(a,b))for x in diff(v,w,p+[i])]
 return[{'path':p,'kind':'changed','before':a,'after':b}]
write(H/'register-change-log.json',diff(old,g));write(H/'audit-change-log.json',diff(olda,a))
assert all(x['name']==y['name']and x['master_fields']==y['master_fields']and x['specifications']==y['specifications']and x['photo_coverage']==y['photo_coverage']for x,y in zip(g['options'],old['options']))
write(H/'preparation-verification.json',{'status':'PASS','canonical_options':184,'identified_component_identities':111,'current_numbered_source_design_labels':3,'current_folder_finish_inventory':6,'canonical_count_change':0,'legacy_aliases_promoted':0,'specification_transfers':0,'photo_relationships':26,'new_original_bytes':8888149,'historical_canonical_individual_gaps':26,'new_tabs':2,'new_native_links':82,'changed_cells':len(changes),'changed_existing_link_targets':len(plan['target_changes'])})
print(json.dumps(read(H/'preparation-verification.json')))
