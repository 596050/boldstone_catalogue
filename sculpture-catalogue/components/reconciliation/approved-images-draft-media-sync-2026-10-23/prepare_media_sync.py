import json,hashlib,copy,shutil,importlib.util,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');now=lambda:datetime.now(timezone.utc).isoformat()
p=read(B/'current-master.json');prior=(B/p['register']).parent
sources={'master_pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':Path(p['latest_image_coverage_audit']['path']),'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','squarespace_hold':B/'components/parallel-reviews/listing-execution-2026-10-21/SQUARESPACE_WRITE_HOLD.json'}
if not(H/'input-manifest.json').exists():
 m={}
 for k,v in sources.items():
  dest=H/'inputs'/(k+'.before');shutil.copy2(v,dest);m[k]={'path':str(v),'snapshot':str(dest),'sha256':sha(v)}
 write(H/'input-manifest.json',m)
for k,x in read(H/'input-manifest.json').items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
for name in ['current-assets.json','photo-review-queue.json','guided-owner-review-state.json','scope.json','preparation-verification.json','pending-followups.json','native-current-crosswalk.json','download-verification.json','evidence-verification.json','evidence-manifest.json','client-timestamp-verification.json','image-and-parent-metadata-current.json','final-native-readback.json']:
 if not(H/name).exists():shutil.copy2(prior/name,H/name)
for name in ['verify_workbook.py','verify_bindings.py','finalize_visual_review.py']:
 if not(H/name).exists():shutil.copy2(prior/name,H/name)
src=(prior/'build_reports.py').read_text().replace("OUT=B/'outputs/approved-images-folder-refresh-2026-10-23'","OUT=B/'outputs/approved-images-draft-media-sync-2026-10-23'");(H/'build_reports.py').write_text(src)
g=read(H/'inputs/master_register.before');old=copy.deepcopy(g);a=read(H/'inputs/audit.before');scope=read(H/'preparation-verification.json');full=set(scope['complete_individual_images_added']);accepted=set(scope['owner_accepted_qualified_reference_exceptions']);target=full|accepted;changed=[]
for x in g['current_listing_resolution_details']['entries']:
 oid=x['product_id']
 if oid not in target:continue
 x.setdefault('historical_media_review_states',[]).append({'remaining_evidence_gaps':copy.deepcopy(x['remaining_evidence_gaps']),'draft_media_condition':x.get('draft_listing',{}).get('media_condition'),'before_sync_utc':now()})
 if oid in full:
  x['remaining_evidence_gaps']=[v for v in x['remaining_evidence_gaps']if not v.startswith('Existing image-coverage limitation:')]+['Complete individual listing image owner-approved; photographic/generated origin and exact physical cast remain unverified.']
  condition='Use the owner-approved complete individual image linked here. Original group photographs remain context. Creation origin, physical specifications and current exact platform offer remain unverified.'
 else:
  x['remaining_evidence_gaps']=[v for v in x['remaining_evidence_gaps']if not v.startswith('Existing image-coverage limitation:')]+['Owner accepts existing group or combined design/finish references. Technical Group only remains; separate-photo request closed by scoped exception.']
  condition='Use the scoped owner-accepted references; retain technical Group only and the whole original. White design references remain White; Beige finish is shown by the linked pair. See the accepted listing-reference review for exact roles.'if oid in ['BSI-95ECE169007F','BSI-6C2DDC69FB83']else'Use the owner-accepted whole group photograph for this component position. Technical Group only remains; no crop or separate individual photograph is asserted.'
 if x.get('draft_listing'):x['draft_listing']['media_condition']=condition
 x['current_media_review_synchronization']={'recorded_utc':now(),'complete_individual_image_available':oid in full,'accepted_qualified_reference_exception':oid in accepted,'platform_and_physical_dispositions_unchanged':True};changed.append(oid)
assert len(changed)==12
g['latest_draft_media_synchronization']={'recorded_utc':now(),'option_ids':changed,'new_image_approvals':0,'new_physical_verifications':0,'platform_writes':0,'prior_release':str(prior/'publication-receipt.json')}
write(H/'image-coverage-current.json',a);g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']));g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),audit_sha256=sha(H/'image-coverage-current.json'),verification=str((H/'saved-file-verification.json').relative_to(B)),visual_verification=str((H/'visual-verification.json').relative_to(B)))
for k in ['verification_sha256','visual_verification_sha256','native_binding_verification','native_binding_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g)
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');changes=[];links=[];heights=[]
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):links.append({'sheet':sn,'cell':x.get('ref'),'label':b['values'][sn].get(x.get('ref'),''),'target':'#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')]})
for x in g['current_listing_resolution_details']['entries']:
 oid=x['product_id']
 if oid not in target:continue
 gaps='\n'.join(x['remaining_evidence_gaps'])
 for sn,cols in [('Draft Listings',{'N':gaps,'P':x['draft_listing']['media_condition']}),('Listing Resolution',{'V':gaps})]:
  row=next((int(c[1:])for c,v in b['values'][sn].items()if re.fullmatch(r'A\d+',c)and v==oid),None)
  if row is None:continue
  for col,value in cols.items():
   before=b['values'][sn].get(col+str(row),'')
   if sn=='Listing Resolution':value=before+'\nCurrent media: '+x['remaining_evidence_gaps'][-1]
   if before!=value:changes.append({'sheet':sn,'cell':col+str(row),'before':before,'value':value})
  heights.append({'sheet':sn,'row':row,'height':max(180,next((float(r.get('ht','15'))for r in b['sheets'][sn]['root'].find(n.q('sheetData'))if r.get('r')==str(row)),180))})
blocks=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes];first=next(int(c[1:])for c,v in b['values']['Draft Listings'].items()if re.fullmatch(r'A\d+',c)and v=='BSI-53239DE28BCA');raked=next(int(c[1:])for c,v in b['values']['Draft Listings'].items()if re.fullmatch(r'A\d+',c)and v=='BSI-95ECE169007F')
plan={'cell_changes':changes,'formula_changes':[],'value_blocks':blocks,'formula_blocks':[],'hyperlinks':links,'row_heights':heights,'table_appends':[],'new_sheets':{},'expected_original_sheet_count':28,'expected_formula_count':3390,'summary_expected':[{'sheet':'Photo Coverage','cell':'B4','value':177},{'sheet':'Photo Coverage','cell':'B5','value':11},{'sheet':'Missing Pictures','cell':'B4','value':86}],'baseline_ranges':[['Draft Listings','M'+str(first)+':P'+str(first),'baseline-draft-media']],'preview_ranges':[['Draft Listings','M'+str(first)+':P'+str(first),'01-approved-complete-draft-media'],['Draft Listings','M'+str(raked)+':P'+str(raked),'02-approved-qualified-draft-media']]};write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':links,'formulas':[]});write(H/'media-synchronization-verification.json',{'status':'PREPARED','option_records':len(changed),'current_workbook_cells':len(changes),'qualified_working_fields_unchanged':True,'coverage_and_action_counts_unchanged':True})
print(json.dumps({'status':'PREPARED','options':len(changed),'cells':len(changes),'links':len(links)}))
