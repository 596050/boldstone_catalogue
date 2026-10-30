"""Add the newly sealed, exact owner image-role approval before authoring."""
import collections,copy,hashlib,importlib.util,json,posixpath,re,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');path=B/'components/parallel-reviews/acanthus-master-photo-search-2026-10-23/owner-image-approval.json'
if 'bronze_approval'not in m:
 snapshot=H/'inputs/bronze_approval.before';shutil.copy2(path,snapshot);m['bronze_approval']={'path':str(path),'snapshot':str(snapshot),'sha256':sha(path)};write(H/'input-manifest.json',m)
assert m['bronze_approval']['sha256']=='38ffe6062a1b33fc8e41208163f56fb78375e8d94a01331ae7cee91bd34d56d8'
approval=read(m['bronze_approval']['snapshot']);event=approval['source_owner_event'];raw=next(line.rstrip('\n')for line in Path(event['transcript_path']).open()if hashlib.sha256(line.rstrip('\n').encode()).hexdigest()==event['event_sha256']);assert json.loads(raw)['timestamp']==event['timestamp']
fresh=read(H/'fresh-bronze-evidence.json');file=fresh['file']['file'];folder=fresh['folder']['folder'];role=approval['approved_reference_roles'][0];source=approval['source_content_checks'][0]
assert file['id']==source['file_id']=='id:cnqzTNngPVsAAAAAAAuf1w'and file['rev']==role['source']['rev']and file['size']==source['bytes']and posixpath.dirname(file['path_display'])==folder['path_display']and folder['id']==role['folder_id']and sha(source['original_path'])==source['sha256']
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');oid='BSI-A9FE7D79863A';o=next(x for x in g['options']if x['product_id']==oid);c=next(x for x in a['coverage']if x['option_id']==oid);assert c['in_situ']['status']=='No verified image'and o['file_id']==fresh['primary']['file']['id']=='id:cnqzTNngPVsAAAAAAAygFw'
r={'file_id':file['id'],'folder_id':folder['id'],'name':file['name'],'path':'ns:202238505/'+file['path_display'],'image_url':role['image_url'],'folder_url':role['folder_url'],'native_reference_status':'CURRENT_MASTER_FILE_AND_ACTUAL_PARENT_VERIFIED','source_qualified_visual_binding':True,'physical_cast_or_size_certified':False,'scene_authenticity_verified':False}
basis='Owner explicitly accepts the courtyard photograph as the in situ reference for Acanthus Two Leaves — Bronze, the RIGHT-HAND SQUARE PANEL. Its complete outline and two curved leaves are visible on the courtyard wall above planting. The larger left panel is context only; no new component or set is inferred. The original group photograph is retained unchanged. Scene origin/client installation is not authenticated and no dimensions, weight, material recipe or fitted fixing is verified. Existing individual and series references remain unchanged.'
c.setdefault('historical_in_situ_references',[]).append(copy.deepcopy(c['in_situ']));c['in_situ']={'status':'Available','reference':r,'basis':basis,'member_position':'RIGHT-HAND SQUARE PANEL','owner_image_role_approval':{'decision_id':approval['decision_id'],'path':m['bronze_approval']['path'],'sha256':m['bronze_approval']['sha256']},'explicit_owner_image_role_approval':True,'source_qualified_visual_binding':True,'physical_cast_or_size_certified':False,'scene_authenticity_verified':False};c.setdefault('notes',[]).append(basis)
o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(o.get(k))for k in ['context_status','context_file_id','context_folder_id','context_image_url','context_folder_url','context_description']});o.update(context_status='Available',context_file_id=r['file_id'],context_folder_id=r['folder_id'],context_image_url=r['image_url'],context_folder_url=r['folder_url'],context_description=basis);o['photo_coverage']['in_situ']='Available';o['current_owner_approved_courtyard_reference']={'decision_id':approval['decision_id'],'reference':r,'member_position':'RIGHT-HAND SQUARE PANEL','qualification':basis}
state={'state':'OWNER_ACCEPTED_COURTYARD_IN_SITU_REFERENCE','finding':basis,'next_action':'Keep the right-hand-panel scope and original group image.','source_reference':r,'owner_exact_image_role_approved':True}
c.setdefault('terminal_task_review',{})['in_situ']=copy.deepcopy(state);o.setdefault('current_photo_task_review',{}).setdefault('roles',{})['in_situ']=copy.deepcopy(state)
actions=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='In situ'and x['status']=='Open'];assert len(actions)==1;x=actions[0];x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Resolved',action='Use approved courtyard image: RIGHT-HAND SQUARE PANEL.',reference=r,qualification=basis,owner_response='Use image',resolution_kind=state['state'])
reviews=read(H/'photo-review-queue.json')
for x in reviews:
 if x.get('option_id')==oid and x.get('role')=='In situ':x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],source_reference=r)
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']==oid:
  x.setdefault('remaining_evidence_gaps',[]).append(basis)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\n'+basis
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];counts=a['counts'];counts.update(in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=sum(x['status']=='Open'for x in active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']));assert(counts['required_picture_actions'],counts['in_situ_statuses']['No verified image'],counts['actions_by_type']['Find / capture'],counts['resolved_action_rows'])==(70,50,69,84)
item={'option_id':oid,'name':o['name'],'role':'In situ — owner-approved courtyard reference','basis':basis,'references':[{'role':'In situ','reference':r,'target_member_position':'RIGHT-HAND SQUARE PANEL'}],'approval':{'path':m['bronze_approval']['path'],'sha256':m['bronze_approval']['sha256'],'decision_id':approval['decision_id'],'scope':'EXACT_IN_SITU_IMAGE_ROLE_AND_COMPONENT_POSITION'},'technical_individual_status':c['individual']['status']}
prep=read(H/'preparation-verification.json');prep['imported_approvals'].append(item);prep['current_counts']=counts
result=read(H/'context-import-summary.json');result.update(status='FOUNTAIN_AND_ACANTHUS_QUALIFIED_CONTEXTS_IMPORTED',current_counts=counts,qualified_in_situ_roles_closed=2,explicit_owner_image_role_approvals_added=1,imported_approvals=prep['imported_approvals']);g['latest_qualified_display_context_import']=result;g['latest_context_folder_refresh']=result;g['latest_image_coverage_audit'].update(counts=counts,status=result['status']);a['latest_context_folder_refresh']=result;a['status']=result['status'];g['latest_draft_media_synchronization']['option_ids'].append(oid);g.setdefault('imported_owner_review_packets',[]).append(item['approval'])
assets=read(H/'current-assets.json');assets[file['id']]={**assets.get(file['id'],{}),**r,'thumb':source['original_path'],'original':source['original_path'],'sha256':source['sha256'],'current_original_content_rehashed':True,'pixels_edited':False}
originals=read(H/'original-verification.json')
if not any(x['file_id']==file['id']for x in originals['files']):originals['files'].append({'file_id':file['id'],'local_original':source['original_path'],'sha256':source['sha256'],'pixels_edited':False})
ledger=read(H/'context-review-ledger.json')
for x in ledger['tasks']:
 if x['option_id']==oid and x['role']=='In situ':x.update(status_after='Resolved',outcome=state['state'],current_finding=basis,current_reference=r)
rs=read(H/'guided-owner-review-state.json');rs['queues']['in_situ']=[x for x in rs['queues']['in_situ']if x!=oid];rs.setdefault('completed_owner_reviews',[]).append({'option_id':oid,'source_file_id':file['id'],'explicit_exact_image_role_approval':True,'member_position':'RIGHT-HAND SQUARE PANEL','physical_verification':False})
evidence=read(H/'source-evidence-verification.json');evidence.update(bronze_owner_event_sha256=event['event_sha256'],bronze_original_and_fresh_actual_parent_verified=True,three_missing_acanthus_roles_remain_open=True)
for name,z in [('canonical-master-register.json',g),('image-coverage-current.json',a),('preparation-verification.json',prep),('photo-review-queue.json',reviews),('context-import-summary.json',result),('current-assets.json',assets),('original-verification.json',originals),('context-review-ledger.json',ledger),('guided-owner-review-state.json',rs),('source-evidence-verification.json',evidence)]:write(H/name,z)
em=read(H/'evidence-manifest.json');em[str(H/'fresh-bronze-evidence.json')]={'sha256':sha(H/'fresh-bronze-evidence.json')};write(H/'evidence-manifest.json',em)
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);b=v.load(H/'inputs/master_workbook.before');plan=read(H/'workbook-edit-plan.json');changes={(x['sheet'],x['cell']):x for x in plan['cell_changes']};links={(x['sheet'],x['cell']):x for x in plan['hyperlinks']}
def cell(sn,c,val):
 before=b['values'][sn].get(c,'')
 if before!=val:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':val}
def link(sn,c,label,u):cell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':u}
def rowof(sn):return next((int(k[1:])for k,val in b['values'][sn].items()if re.fullmatch('A[0-9]+',k)and val==oid),None)
row=rowof('Master Catalogue');rr=str(row)
for col,val in {'F':'Available','O':r['file_id'],'P':r['folder_id'],'L':basis}.items():cell('Photo Coverage',col+rr,val)
link('Photo Coverage','G'+rr,'Approved courtyard — right square panel',r['image_url']);link('Photo Coverage','H'+rr,'Actual containing folder',r['folder_url']);link('Photo Coverage','U'+rr,'Owner approval and component scope',str(B/'outputs'/H.name/'imported-approvals.html')+'#'+oid)
link('Master Catalogue','T'+rr,'Approved courtyard — right square panel',r['image_url']);link('Master Catalogue','U'+rr,'Actual containing folder',r['folder_url']);cell('Master Catalogue','V'+rr,b['values']['Master Catalogue']['V'+rr].split('\nPhoto review:')[0]+'\nPhoto review: individual '+c['individual']['status']+'; in situ Available; series '+c['series']['status']+'.\n'+basis)
rr=rowof('Listing Resolution')
if rr:cell('Listing Resolution','V'+str(rr),b['values']['Listing Resolution'].get('V'+str(rr),'')+'\n'+basis)
detail=next((x for x in g['current_listing_resolution_details']['entries']if x['product_id']==oid),None);rr=rowof('Draft Listings')
if rr and detail and detail.get('draft_listing'):cell('Draft Listings','N'+str(rr),'\n'.join(detail['remaining_evidence_gaps']));cell('Draft Listings','P'+str(rr),detail['draft_listing']['media_condition'])
for i,x in enumerate(a['missing_pictures'],10):
 if x['option_id']!=oid or x['role']!='In situ':continue
 for col,val in {'F':x['action'],'I':r['file_id'],'J':r['folder_id'],'L':basis,'M':'Use image','N':'Resolved'}.items():cell('Missing Pictures',col+str(i),val)
 link('Missing Pictures','G'+str(i),'Approved courtyard — right square panel',r['image_url']);link('Missing Pictures','H'+str(i),'Actual containing folder',r['folder_url'])
for key,x in list(changes.items()):
 if x['cell']=='A3':x['value']=x['value'].replace('51 in situ','50 in situ').replace('71 required open actions','70 required open actions').replace('83 resolved','84 resolved')+' Bronze Two Leaves uses the owner-approved right square panel in the courtyard photograph.'
 if key in links:links[key]['label']=x['value']
for x in plan['formula_changes']:
 if(x['sheet'],x['cell'])==('Photo Coverage','D4'):x['expected']=138
 if(x['sheet'],x['cell'])==('Missing Pictures','B4'):x['expected']=69
for x in plan['summary_expected']:
 if(x['sheet'],x['cell'])==('Photo Coverage','D4'):x['value']=138
 if(x['sheet'],x['cell'])==('Missing Pictures','B4'):x['value']=69
plan['cell_changes']=list(changes.values());plan['hyperlinks']=list(links.values());plan['value_blocks']=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()];plan['preview_ranges'].append(['Photo Coverage','F'+str(row)+':L'+str(row),'05-bronze-courtyard-reference']);write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
print(json.dumps({'status':'TWO_CONTEXT_IMPORTS_PREPARED','in_situ_gaps':50,'series_gaps':18,'required_actions':70,'bronze_row':row,'changed_cells':len(changes)}))
