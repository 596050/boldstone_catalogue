"""Integrate owner-added Pewter options without transferring physical certainty."""
import copy,collections,hashlib,json,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs,urlunsplit
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
g=read(H/'inputs/master_register.before');old=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a);owner=read(H/'owner-instruction.json');did=owner['decision_id'];fields=list(owner['confirmed_table'])
prefix='/BOLDSTONE MASTER/Products/01 Wall Sculptures/'
live=read(H/'acanthus-native.json')['entries']+read(H/'egyptian-native.json')['entries'];byid={x['file_id']:copy.deepcopy(x)for x in live}
for name in ['acanthus-family-metadata.json','pewter-folder-0-metadata.json','pewter-folder-1-metadata.json','pewter-folder-2-metadata.json']:
 d=read(H/name)['folder'];byid[d['id']]={'file_id':d['id'],'object_type':'folder','path_display':d['path_display'],'name':d['name'],'path':'ns:202238505/'+d['path_display']}
for x in byid.values():x['display_path']=x.get('path_display')or'/'+x['path'].split('//',1)[1]
folders={x['display_path'].casefold():x['file_id']for x in byid.values()if x['object_type']=='folder'}
for x in byid.values():x['parent_id']=folders.get(posixpath.dirname(x['display_path']).casefold())
oldobjects={}
prior=Path(m['master_register']['path']).parent
for page in (prior/'native-wall-scan').glob('page-*.json'):
 for x in read(page)['entries']:
  p='/'+x['path'].split('//',1)[1]
  if p.startswith(prefix+'Acanthus/')or p==prefix+'Acanthus'or p.startswith(prefix+'Egyptian Two Palms/')or p==prefix+'Egyptian Two Palms':oldobjects[x['file_id']]={**x,'display_path':p}
oldpaths={x['display_path'].casefold():x['file_id']for x in oldobjects.values()}
for x in byid.values():oldpaths[x['display_path'].casefold()]=x['file_id']
missing={'id:cnqzTNngPVsAAAAAAAudqw':H/'archived-originals/acanthus__acanthus-one-leaf-assorted-colours__001.jpg','id:cnqzTNngPVsAAAAAAAuV6Q':H/'archived-originals/acanthus__acanthus-one-leaf-assorted-colours__003.jpg'}
unavailable=set(missing)|{'id:cnqzTNngPVsAAAAAAAyh4Q'}
for fid in unavailable:assert fid not in byid
family=byid['id:cnqzTNngPVsAAAAAAAt_GA'];familyurl='https://www.dropbox.com/home'+quote(family['display_path'],safe='/')
def urlpath(s):
 if not isinstance(s,str)or not s.startswith('https://www.dropbox.com/'):return None,None
 u=urlsplit(s);p=unquote(u.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):
   p=p[len(route):];name=parse_qs(u.query).get('preview',[''])[0];return u,p+('/'+name if name else '')
 return None,None
def refurl(s):
 u,p=urlpath(s)
 if not u:return s
 fid=oldpaths.get(p.casefold());x=byid.get(fid)
 if x:
  route='/preview'if u.path.startswith('/preview/')else'/home';q=u.query
  target=posixpath.dirname(x['display_path'])if parse_qs(q).get('preview')else x['display_path']
  return urlunsplit((u.scheme,u.netloc,quote(route+target,safe='/'),q,u.fragment))
 return s
def project(z):
 if isinstance(z,list):return[project(v)for v in z]
 if not isinstance(z,dict):return refurl(z)
 z={k:copy.deepcopy(v)if k.startswith(('historical_','prior_','original_','before_'))or k in ['specifications','master_fields','accepted_working_fields','six_working_fields','evidence_ref','master_ref','source_ref']else project(v)for k,v in z.items()}
 for fk,pk,ik,uk in [('file_id','folder_id','image_url','folder_url'),('context_file_id','context_folder_id','context_image_url','context_folder_url')]:
  x=byid.get(z.get(fk))
  if x and x['object_type']=='file':
   if pk in z:z[pk]=x['parent_id']
   if ik in z:z[ik]='https://www.dropbox.com/preview'+quote(x['display_path'],safe='/')
   if uk in z:z[uk]='https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/')
  elif z.get(fk)in missing:
   z['native_reference_status']='NOT_FOUND_IN_CURRENT_DROPBOX_READBACK'
   z['archived_original']=str(missing[z[fk]])
   z['archived_original_sha256']=sha(missing[z[fk]])
   z['current_family_navigation_url']=familyurl
   z['historical_file_and_parent_IDs_retained']=True
 return z
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions','arrangement_context_references']:
 g[layer]=project(g[layer])
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:
  if 'current_primary_reference'in x:x['current_primary_reference']=project(x['current_primary_reference'])
g['current_listing_resolution_details']=project(g['current_listing_resolution_details'])
for layer in ['coverage','missing_pictures','identity_review']:a[layer]=project(a[layer])
assets=project(read(H/'inputs/report_assets.before'));reviews=project(read(H/'inputs/report_reviews.before'))
def native_ref(fid):
 x=byid[fid];parent=x['parent_id'];assert parent and parent in byid
 return {'file_id':fid,'folder_id':parent,'name':x['name'],'path':x['path'],'image_url':'https://www.dropbox.com/preview'+quote(x['display_path'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/'),'native_reference_status':'VERIFIED_CURRENT_ID_AND_PARENT','physical_cast_or_size_certified':False}
def apply_ref(o,r):
 for k in ['file_id','folder_id','image_url','folder_url']:o[k]=r[k]
 o['native_reference_status']=r['native_reference_status']
o=next(x for x in g['options']if x['product_id']=='BSI-3635E3DC3434');old_one=next(x for x in old['options']if x['product_id']==o['product_id']);r=native_ref('id:cnqzTNngPVsAAAAAAA6VmA');apply_ref(o,r)
o['current_link_basis']='Owner-added complete Pewter listing image; original bytes, stable file and actual containing-folder IDs verified23October2026'
o['current_full_individual_image']=copy.deepcopy(r);o['source_scope_notes']+=' Explicit owner reply23October2026 accepts only this One Leaf option\'s six qualified working fields. Current new image origin remains unverified.'
for f in fields:
 v=o['master_fields'][f];before=copy.deepcopy(v);v.setdefault('historical_working_revisions',[]).append({'before':before,'decision_id':did})
 v['state']='Owner explicitly accepted qualified working detail23October2026; estimates, hypothesis and fitted-hardware unknown retained; not physically verified'
 if f=='Availability':v['state']='Owner explicitly confirms made-to-order1–2week catalogue policy23October2026; stock/capacity unverified'
 v['basis']+='\nDirect owner reply23October2026: "These are correct". Scope clarified: "Yes: only to Acanthus One Leaf". Acceptance retains every estimate, hypothesis and unknown in the displayed table.'
 v['explicit_owner_confirmation']={'decision_id':did,'instruction':m['owner-instruction'],'scope':'This Acanthus One Leaf Pewter option only','qualified_working_value_accepted':True,'actual_physical_value_verified':False}
 v.setdefault('source_references',[]).append({'owner_confirmation':m['owner-instruction'],'decision_id':did});assert v['physical_verification']==0
o['selling_details']['owner_accepted_working_estimate']=True;o['selling_details']['exact_selling_price_confirmed']=False
cov=next(x for x in a['coverage']if x['option_id']==o['product_id']);cov.setdefault('historical_individual_references',[]).append(copy.deepcopy(cov['individual']))
cov['individual']={'status':'Available','reference':r,'exact_option':True,'basis':'Owner-added complete isolated Pewter image. Compared with retained One Leaf White and Pewter references; no new crop/edit created. Photographic/generated creation origin and exact physical cast remain unverified.','terminal_review_state':'OWNER_ADDED_STANDALONE_IMAGE','physical_cast_or_size_certified':False}
cov['notes'].append('23October2026: new complete Pewter individual image closes the individual-image gap. Prior workshop-group image is preserved as an archived original; current native file lookup returns NOT_FOUND.')
o['photo_coverage']['individual']='Available';o['current_photo_gap_review']={'decision_id':did,'reference':r,'status':'INDIVIDUAL_ROLE_RESOLVED_ONLY','creation_origin_unverified':True}
for action in a['missing_pictures']:
 if action['option_id']==o['product_id']and action['role']=='Individual':
  action['prior_action_before_pewter_image']=copy.deepcopy(action);action.update(status='Resolved',action_type='Find / capture',action='Complete owner-added individual Pewter image bound to the existing One Leaf component.',reference=copy.deepcopy(r),qualification=cov['individual']['basis'],owner_response='Owner added Pewter image and accepted qualified working specifications for One Leaf only.',owner_decision_id=did)
 if action['option_id']==o['product_id']and action['role']=='In situ':action['reference']=copy.deepcopy(r)
for review in reviews:
 if review.get('product_id',review.get('option_id'))==o['product_id']and review.get('role')=='Individual':review.update(review_state='OWNER_ADDED_STANDALONE_IMAGE',finding=cov['individual']['basis'],next_action='Individual role resolved. Obtain wider in situ context separately.',source_reference=copy.deepcopy(r))
new=[];newcov=[]
def nice(s):
 s=re.sub(r'Approximately(?=\d)', 'Approximately ', s)
 s=re.sub(r'\s*×\s*', ' × ', s)
 s=re.sub(r'(?<=\d)(cm|kg|weeks)\b', r' \1', s)
 return s.replace('range4', 'range 4').replace('time1', 'time 1').replace('weeks', 'weeks')
specs={
 'BC-AC-TWO':{'Dimensions / depth':'Approximately30 ×30 ×6cm — Two Leaves White/Bronze comparator estimate; this Pewter option unmeasured.','Weight':'Approximately5kg; working range4–6kg — comparator estimate; this Pewter option unweighed.','Material / finish':'Cast plaster with a pewter-effect finish — working hypothesis; actual binder, coating recipe and metal content unconfirmed.','Fixing':'Keyhole fixing or French cleat offered — owner policy; fitted hardware, count and load rating unknown.','Individual price':'£175 per individual panel — estimated from the existing Two Leaves working price.','Availability':'Made to order; lead time1–2weeks — owner catalogue policy; current stock and capacity unverified.'},
 'BC-EG-1':{'Dimensions / depth':'Approximately50 ×30 ×7cm — White listing comparator estimate. Related Acanthus draft gives60 ×30cm; actual Pewter size unresolved.','Weight':'Approximately9kg — White/Acanthus comparator estimate; actual Pewter cast unweighed.','Material / finish':'Cast plaster/mineral composite with a pewter-effect finish — working hypothesis; actual binder, reinforcement and coating formulation unconfirmed.','Fixing':'Keyhole fixing or French cleat offered — owner policy; fitted hardware, count and load rating unknown.','Individual price':'£450 per individual panel — estimated from the existing Egyptian Palm One working price.','Availability':'Made to order; lead time1–2weeks — owner catalogue policy; current stock and capacity unverified.'}}
for cid,key,name,fid,comparator in [('BC-AC-TWO','BC-AC-TWO|AC-TWO-PEWTER','Acanthus Two Leaves — Pewter','id:cnqzTNngPVsAAAAAAA6Vlg','BSI-93ADE7C4103D'),('BC-EG-1','BC-EG-1|EG-1-PEWTER','Egyptian Palm One — Pewter','id:cnqzTNngPVsAAAAAAA6VmQ','BSI-3ABEAEE767E8')]:
 oid='BSI-'+hashlib.sha256(key.encode()).hexdigest()[:12].upper();assert all(z['product_id']!=oid and z['canonical_key']!=key for z in g['options']);template=next(z for z in g['options']if z['product_id']==comparator);r=native_ref(fid);familyname=template['family'];mf={}
 for f in fields:
  specs[cid][f]=nice(specs[cid][f])
  state='Qualified working estimate/hypothesis under standing owner policy; not individually confirmed or physically verified'
  if f in ['Fixing','Availability']:state='Standing owner offered-choice / supply policy; fitted hardware, stock and capacity unverified'
  mf[f]={'display':specs[cid][f],'state':state,'basis':'New Pewter finish explicitly added by owner23October2026. Comparator is '+comparator+' ('+template['name']+'). '+('The One Leaf30×30/4kg/£175 confirmation does not apply to this component. ')+('Earlier comparator basis: '+template['master_fields'][f]['basis']if f in ['Dimensions / depth','Weight','Material / finish','Individual price']else 'Standing owner instruction retained; no physical-cast inference.'),'working_recorded':1,'physical_verification':0,'source_scopes':[key],'proposal_ids':[oid+'-'+str(fields.index(f)+1)],'source_references':[{'owner_finish_addition':m['owner-instruction'],'comparator_option_id':comparator,'comparison_is_not_physical_confirmation':True}],'prior_display':''}
 sale='One individually described sculpture or panel; no physical stock quantity asserted';nextaction='Check current authenticated Squarespace/Shopify inventory for this exact individual Pewter option before creating a variant; keep pair offers separate.'
 recon={'product_id':oid,'canonical_key':key,'name':name,'canonical_component_id':cid,'family':familyname,'source_scopes':[key],'sale_unit':sale,'working_specification_status':'COMPLETE_SIX_WORKING_FIELDS','overall_disposition':'NEW_CURRENT_OPTION_PLATFORM_VERIFICATION_PENDING','individual_source_record_supported':False,'match_grade':'UNVERIFIED_CURRENT_PLATFORM_MATCH','exact_current_configuration_certified':False,'exact_current_option_configuration_match_verified':False,'selected_evidence_edge_ids':[],'all_evidence_edge_ids':[],'related_offer_refs':[],'next_action':nextaction,'catalogue_count_increment':0,'platforms':{p:{'disposition':'NEW_CURRENT_OPTION_PLATFORM_VERIFICATION_PENDING','selected_evidence_edge_ids':[],'supported_individual_native_variants':[],'related_offer_refs':[],'individual_native_variant_assignment_count':0,'current_authenticated_admin_inventory_verified':False,'exact_current_option_configuration_match_verified':False,'source_supported_individual_design_record_present':False,'absence_scope':'New owner-added finish; no current native absence claim','next_action':nextaction}for p in ['Squarespace','Shopify']}}
 resolution={'product_id':oid,'canonical_key':key,'name':name,'family':familyname,'prior_overall_disposition':'NEW_CURRENT_OPTION_PLATFORM_VERIFICATION_PENDING','current_source_resolution_disposition':'NEW_CURRENT_OPTION_PLATFORM_VERIFICATION_PENDING','source_supported_individual_record_present':False,'reviewed_in_assigned_106':False,'new_supported_source_matches':[],'conditional_native_tuple':None,'exact_current_physical_or_all_six_field_configuration_certified':False,'correction_case_id':None,'overlap_case_ids':[],'accepted_working_fields_changed':False,'next_action':nextaction,'source':m['owner-instruction']}
 draft={'proposed_sku':'DRAFT-'+oid,'proposed_product_group_id':'DRAFT-PRODUCT-'+cid,'proposed_variant_reference':'Pewter','title':name,'canonical_option_id':oid,'canonical_component_id':cid,'sale_unit':sale,'six_working_fields':copy.deepcopy(mf),'activation_condition':nextaction,'media_condition':'Owner-added full Pewter image is available as a qualified listing reference. Creation origin and actual cast remain unverified.','publication_performed':False,'creation_is_not_authorized_or_performed_by_this_packet':True}
 review={'product_id':oid,'canonical_key':key,'name':name,'source_resolution_disposition':'NEW_CURRENT_OPTION_PLATFORM_VERIFICATION_PENDING','review_status':'OWNER_ADDED_FINISH_NOT_NATIVE_REVIEWED','draft_listing':draft,'custom_unlisted_pattern_draft':None,'supported_source_matches':[],'conditional_native_tuple':None,'remaining_evidence_gaps':['Actual dimensions/depth, weighed mass, material recipe and fitted fixing unverified','Working individual price is a comparator estimate','Current exact Squarespace/Shopify Pewter variant unverified'],'next_action':nextaction,'accepted_working_fields':copy.deepcopy(mf),'accepted_working_fields_changed':False,'physical_configuration_verified':False,'authenticated_admin_inventory_verified':False,'proven_live_absent':False,'source_ref':m['owner-instruction']}
 s=copy.deepcopy(template['selling_details']);s.update(estimated_price=175.0 if cid=='BC-AC-TWO' else 450.0,estimated_price_upper=None,price_status='estimate',price_selection='new_finish_comparator_estimate',physical_stock_quantity=None,customer_listing_readiness_changed=False,owner_accepted_working_estimate=False,policy_ref=did)
 x={'product_id':oid,'canonical_key':key,'canonical_design_id':cid,'canonical_component_id':cid,'option_family_id':None,'name':name,'retained_names':[name],'source_scopes':[key],'record_type':'Individual sculpture finish option','sale_unit':sale,'orientation_options':['Custom orientation available'],'orientation_evidence':'Standing owner wall-sculpture customisation policy','specifications':{f:{'display':v['display'],'state':v['state'],'basis':v['basis'],'working_accepted':True,'assertions':[]}for f,v in mf.items()},'master_fields':mf,'six_working_fields_recorded':True,'working_specification_status':'COMPLETE_SIX_WORKING_FIELDS','physical_specifications_verified':False,'platform_publication_performed':False,**{k:r[k]for k in ['file_id','folder_id','image_url','folder_url']},'native_reference_status':r['native_reference_status'],'context_status':'No verified wider in situ image','context_description':'Full isolated image available. Wider room/garden context remains required.','context_image_url':'','context_folder_url':'','context_file_id':'','context_folder_id':'','original_gap_notes':'New owner-added Pewter finish; individual full image available; physical details remain comparator estimates.','source_scope_notes':'Owner specifically limited the30×30/4kg/£175 table confirmation to One Leaf; it is not transferred to this finish.','family':familyname,'identity_basis':'Owner-added Pewter option mapped to the existing component and compared visually with retained individual/pair sources; no exact mould identity asserted','count_class':'Identified component option','counted_as_individual_option':True,'source_product_sha256':sha(H/'owner-instruction.json'),'size_class':'Comparator estimate; actual size unverified','build_class':'Plaster/mineral composite hypothesis','current_link_basis':'New owner-added original bytes and actual containing-folder IDs verified23October2026','offered_fixing_choices':['Keyhole fixing','French cleat'],'offered_fixing_basis':template['offered_fixing_basis'],'offered_choices_do_not_confirm_current_installed_hardware':True,'confirmed_arrangement_ids':[],'related_platform_offer_refs':[],'source_supported_platform_scope_refs':[],'platform_scope_note':'Exact current individual Pewter platform offer unverified','photo_coverage':{'individual':'Available','in_situ':'No verified image','series':'Available'if cid=='BC-EG-1'else'Optional / no fixed set','audit_option_id':oid},'current_listing_reconciliation':recon,'current_listing_resolution':resolution,'customisation_policy_ref':template['customisation_policy_ref'],'offered_customisation_axes':copy.deepcopy(template['offered_customisation_axes']),'other_customisations_available':True,'selling_details':s,'owner_finish_addition':m['owner-instruction']}
 cov={'option_id':oid,'name':name,'family':familyname,'series_required':cid=='BC-EG-1','notes':['Owner-added finish; six working fields remain estimates or standing policies.'],'scope':'Qualified visual option/role only; no physical-cast or measured-size certification','scene_origin':'New full image creation origin unverified; source pair is a staged wood-wall photograph','owner_review':did,'individual':{'status':'Available','reference':copy.deepcopy(r),'basis':'Owner-added complete Pewter image, compared with retained design reference. Original bytes retained; no crop/edit created.','exact_option':True,'physical_cast_or_size_certified':False},'in_situ':{'status':'No verified image','reference':None,'basis':'Plain isolated wall-background image does not provide wider room/garden context.','physical_cast_or_size_certified':False},'series':{'status':'Available'if cid=='BC-EG-1'else'Optional / no fixed set','reference':native_ref('id:cnqzTNngPVsAAAAAAAt-ZA')if cid=='BC-EG-1'else None,'basis':'Egyptian Palm1 is the tall LEFT panel in the retained Pewter pair; Deco Palm Right remains a separate component. New individual view matches its broad arc sequence.'if cid=='BC-EG-1'else'No fixed set is required; optional family context may be added.','member_position':'LEFT TALL PANEL'if cid=='BC-EG-1'else'','exact_option':True,'physical_cast_or_size_certified':False}}
 for role in ['In situ']+(['Series']if cid=='BC-AC-TWO'else[]):a['missing_pictures'].append({'priority':2 if role=='In situ'else 4,'option_id':oid,'name':name,'role':role,'action_type':'Find / capture'if role=='In situ'else'Optional image','action':'Find or photograph the complete Pewter component in a wider room/garden setting.'if role=='In situ'else'Optional family/series photograph; no fixed set required.','reference':copy.deepcopy(r),'scope':'New finish visual-role task; no physical measurement or platform match inferred','qualification':cov['in_situ'if role=='In situ'else'series']['basis'],'owner_response':'','status':'Open'if role=='In situ'else'Optional'})
 new.append(x);newcov.append(cov);g['current_listing_resolution']['option_overlays'].append(resolution);g['current_listing_resolution_details']['entries'].append(review)
g['options']+=new;a['coverage']+=newcov
for c in g['components']:
 additions=[x for x in new if x['canonical_component_id']==c['component_id']]
 for x in additions:c['option_ids'].append(x['product_id']);c['option_names'].append(x['name']);c['retained_names'].append(x['name'])
 c['option_count']=len(c['option_ids'])
g.setdefault('owner_working_specification_confirmations',[]).append({'decision_id':did,'option_id':o['product_id'],'fields':fields,'scope':'Only Acanthus One Leaf Pewter','source':m['owner-instruction'],'physical_verification':False})
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']==o['product_id']:
  x['accepted_working_fields']=copy.deepcopy(o['master_fields'])
  if x.get('draft_listing'):x['draft_listing']['six_working_fields']=copy.deepcopy(o['master_fields'])
count=len(g['options']);summary=g['summary'];summary.update(individual_options_on_identified_components=180,individual_named_working_options=count,current_option_records=count,current_field_groups=count*6,options_with_six_working_fields=count,individual_options_with_dropbox_reference=187)
lc=g['current_listing_resolution']['counts'];lc.update(catalogue_options=count,accepted_working_field_groups=count*6,remaining_source_scope_gaps_or_identity_candidates=104,nonwall_gap_or_candidate_drafts=101,new_Pewter_options_awaiting_native_review=2)
g['current_listing_resolution']['current_population_note']='Current188 options include two new Pewter finishes, pending native review. Historical source/admin snapshots retain their original scope.'
g['current_listing_resolution_details']['counts'].update(current_population_entries=len(g['current_listing_resolution_details']['entries']),new_Pewter_entries_not_native_reviewed=2)
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];opened=[x for x in a['missing_pictures']if x['status']=='Open'];c=a['counts'];c.update(individual_options=count,individual_statuses=dict(collections.Counter(x['individual']['status']for x in a['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in a['coverage'])),series_required_options=sum(x['series_required']for x in a['coverage']),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),action_rows=len(a['missing_pictures']),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']),active_action_rows=len(active),required_picture_actions=len(opened),archived_source_files_currently_not_found=2)
assert [len(g['options']),len(g['components']),count*6,len(a['coverage']),len(opened)]==[188,112,1128,188,99]
assert c['individual_statuses']=={'Available':170,'Detail only':1,'Group only':16,'Unbound identity':1}
assert c['in_situ_statuses']=={'Available':125,'No verified image':63}and c['series_statuses']=={'Optional / no fixed set':54,'Available':116,'No verified image':18}
for v in read(H/'original-verification.json')['files']+read(H/'comparator-verification.json')['files']:
 assets[v['id']]={'thumb':v['local_original'],'original':v['local_original'],'file_id':v['id'],'sha256':v['sha256'],'pixels_edited':False}
for fid,p in missing.items():assets[fid]={'thumb':str(p),'original':str(p),'sha256':sha(p),'file_id':fid,'native_reference_status':'NOT_FOUND','pixels_edited':False}
repair={'status':'ARCHIVED_ORIGINALS_PRESERVED_NATIVE_LOCATION_REPAIR_REQUIRED','file_ids':list(missing),'last_known_parent_id':'id:cnqzTNngPVsAAAAAAAyh4Q','archived_originals':[{'file_id':f,'path':str(p),'sha256':sha(p)}for f,p in missing.items()],'current_family_id':family['file_id'],'current_family_url':familyurl,'owner_confirmed_series_positions_retained':True,'photograph_capture_gaps_added_for_this_location_issue':0,'native_restore_or_upload_performed':False}
scope={'status':'OWNER_ADDED_PEWTER_FINISHES_AND_ONE_LEAF_WORKING_FIELDS','recorded_utc':now(),'owner_instruction':m['owner-instruction'],'explicit_working_fields_option_id':o['product_id'],'new_finish_option_ids':[x['product_id']for x in new],'existing_component_ids_retained':['BC-AC-ONE','BC-AC-TWO','BC-EG-1'],'new_component_identities':0,'individual_image_role_closed':o['product_id'],'new_images':read(H/'original-verification.json'),'native_source_location_repairs':repair,'current_options':188,'working_component_identities':112,'working_field_groups':1128,'physical_verifications_added':0,'root_native_or_platform_writes':0}
g['latest_pewter_finish_update']=copy.deepcopy(scope);a['latest_pewter_finish_update']=copy.deepcopy(scope);a['recorded_utc']=now();a['status']='CURRENT_PEWTER_FINISH_UPDATE_2026_10_23'
write(H/'image-coverage-current.json',a);g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']));g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),audit_sha256=sha(H/'image-coverage-current.json'),counts=copy.deepcopy(c),scope='188 current options; One Leaf Pewter full image and qualified working acceptance; two new Pewter finish options; archived source-location issues retained separately.',status=a['status'])
for k in ['verification_sha256','visual_verification_sha256','independent_verification','independent_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
g['latest_image_coverage_audit']['verification']=str((H/'saved-file-verification.json').relative_to(B));g['latest_image_coverage_audit']['visual_verification']=str((H/'visual-verification.json').relative_to(B))
assert g['original_review_specification_assertions']==old['original_review_specification_assertions']and len(g['original_review_specification_assertions'])==1668
for x in g['options'][:186]:
 before=next(v for v in old['options']if v['product_id']==x['product_id']);assert x['specifications']==before['specifications'];assert x['canonical_key']==before['canonical_key']and x['canonical_component_id']==before['canonical_component_id']
 if x['product_id']!=o['product_id']:assert x['master_fields']==before['master_fields']and x['selling_details']==before['selling_details']
write(H/'canonical-master-register.json',g);write(H/'current-assets.json',assets);write(H/'photo-review-queue.json',reviews);write(H/'new-current-options.json',new);write(H/'source-location-repairs.json',repair)
write(H/'native-current-crosswalk.json',{'current_objects':byid,'old_objects':oldobjects,'old_path_to_id':oldpaths,'unavailable_IDs':sorted(unavailable),'current_file_paths_changed':sum(fid in oldobjects and x['display_path']!=oldobjects[fid]['display_path']for fid,x in byid.items()if x['object_type']=='file'),'native_writes':0})
write(H/'preparation-verification.json',{'status':'PASS','current_options':188,'components':112,'working_fields':1128,'new_finish_options':2,'working_specification_approval_scope':'One Leaf only','individual_image_gaps':18,'separate_individual_photos_required':17,'deferred_identity':1,'in_situ_gaps':63,'series_gaps':18,'required_actions':99,'new_physical_verifications':0,'original_assertions_preserved':1668,'archived_native_files_not_found':2})
print(json.dumps(read(H/'preparation-verification.json')))
