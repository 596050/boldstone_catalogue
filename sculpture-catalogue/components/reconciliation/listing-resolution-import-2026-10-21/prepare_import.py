"""Prepare the sealed 106-case overlay without changing accepted catalogue data."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2];PACKET=BASE/'components/parallel-reviews/listing-resolution-2026-10-21'
read=lambda p:json.loads(Path(p).read_text());digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
seal=read(PACKET/'SEAL.json');handoff=read(PACKET/'HANDOFF.json')
assert digest(PACKET/'SEAL.json')=='b3a6788386522fd2e0c347572c079d8d8db956789f82acd2a7f56a5f3696d388'
for x in seal['artifacts']:
 p=PACKET/x['relative_path'];assert p.stat().st_size==x['bytes'] and digest(p)==x['sha256']
ind=handoff['independent_validation'];assert digest(ind['path'])==ind['sha256']
iv=read(ind['path']);assert str(iv['status']).startswith('PASS')
assert read(PACKET/'VALIDATION.json')['checks_passed']==3106
prior_manifest=read(HERE/'input-manifest.json') if (HERE/'input-manifest.json').exists() else None
if prior_manifest:
 for x in prior_manifest.values():assert digest(x['path'])==digest(x['snapshot'])==x['sha256']
ptr=read(BASE/'current-master.json');graph=BASE/ptr['register'];book=BASE/ptr['workbook']
assert digest(graph)==ptr['register_sha256']=='b8ee42e12b6465e7dba5fa9beeff7fd1eacca6dd233a74041f556a1a87b2c785'
assert digest(book)==ptr['workbook_sha256']=='299de1cbdab78355b0ab58fb19c1863a757aee832ea9c0b556d3187026db0efa'
sources={'master_workbook':book,'master_register':graph,'master_pointer':BASE/'current-master.json',
 'review_progress':BASE/'components/reviews/specification_review_progress.json','component_checkpoint':BASE/'components/checkpoint.json','root_checkpoint':BASE/'checkpoint.json',
 'owner_ledger':BASE/'components/reviews/user_classifications.json','source_model':BASE/'components/evidence/component_register.json'}
for name in ['SEAL.json','HANDOFF.json','LISTING_RESOLUTION.json','OPTION_RESOLUTIONS_106.json','FOUR_LISTING_CORRECTIONS.json','NEW_SOURCE_LINKS.json','NATIVE_ACTION_DRAFTS.json','IMPORT_PLAN.json']:
 sources[name]=PACKET/name
manifest={}
for key,p in sources.items():
 snap=HERE/'inputs'/(key+'.before');snap.write_bytes(p.read_bytes());manifest[key]={'path':str(p),'snapshot':str(snap),'sha256':digest(p)}
write(HERE/'input-manifest.json',manifest)
g=read(graph);before=copy.deepcopy(g);payload=read(PACKET/'LISTING_RESOLUTION.json');review=read(PACKET/'OPTION_RESOLUTIONS_106.json');corrections=read(PACKET/'FOUR_LISTING_CORRECTIONS.json');actions=read(PACKET/'NATIVE_ACTION_DRAFTS.json');edges=read(PACKET/'NEW_SOURCE_LINKS.json')
byid={x['product_id']:x for x in g['options']};reviewed={x['product_id']:x for x in review['entries']};overlays={x['product_id']:x for x in payload['option_overlays']}
assert len(overlays)==184 and len(reviewed)==106 and len(edges['edges'])==3
for o in g['options']:
 x=overlays[o['product_id']];assert x['canonical_key']==o['canonical_key'] and x['name']==o['name'] and not x['accepted_working_fields_changed']
 if o['product_id'] in reviewed:assert reviewed[o['product_id']]['accepted_working_fields']==o['master_fields']
 o['current_listing_resolution']=copy.deepcopy(x)
for c in corrections['records']:assert c['accepted_working_specifications']=={k:v['display'] for k,v in byid[c['product_id']]['master_fields'].items()}
g['current_listing_resolution']=payload;g['current_listing_resolution_details']=review;g['listing_resolution_source_edges']=edges;g['listing_resolution_native_action_drafts']=actions
summary={'status':'IMPORTED_SOURCE_RESOLUTION_AND_DRAFTS; NO_NATIVE_EXECUTION','recorded_utc':datetime.now(timezone.utc).isoformat(),
 'source_packet':str(PACKET),'source_seal_sha256':digest(PACKET/'SEAL.json'),'payload_sha256':digest(PACKET/'LISTING_RESOLUTION.json'),'counts':handoff['counts'],
 'independent_validation':ind,'current_paths_rebased_from':ptr['register'],'current_paths_input_sha256':ptr['register_sha256'],
 'guards':payload['global_limits'],'sheets':['Listing Resolution','Listing Corrections','Draft Listings','Listing Actions'],'platform_writes':0}
g['latest_listing_resolution']=summary
for key in ['summary','original_review_specification_assertions','current_listing_source_links','current_listing_match_evidence','current_listing_issues','latest_four_family_matching','latest_cup_frozen_manual_paths']:
 assert g[key]==before[key]
write(HERE/'canonical-master-register.json',g)
human=lambda x:str(x).replace('_',' ').capitalize()
join=lambda seq:'\n'.join(dict.fromkeys(str(x) for x in seq if x not in [None,'']))
link=lambda u,l:({'target':u,'label':l} if u else '')
def image(o):return link(o.get('image_url'),'Image' if o.get('file_id') else 'Related reference only')
specrow={o['product_id']:10+i*6 for i,o in enumerate(g['options'])}
current_rows=[]
for o in g['options']:
 x=overlays[o['product_id']];r=reviewed.get(o['product_id'],{});t=x.get('conditional_native_tuple') or {};draft=r.get('draft_listing') or {};custom=r.get('custom_unlisted_pattern_draft') or {}
 state=x['current_source_resolution_disposition']
 if state=='PRIOR_SOURCE_RECONCILIATION_RETAINED':state=x['prior_overall_disposition']
 current_rows.append([o['product_id'],o['name'],human(state),int(x['source_supported_individual_record_present']),int(bool(t)),int(x['reviewed_in_assigned_106']),
  t.get('pattern_short_name',''),t.get('diameter_option',''),t.get('lighting_option',''),t.get('native_product_id',''),t.get('native_variant_id',''),t.get('sku',''),
  draft.get('proposed_sku',''),custom.get('draft_scope_id',''),x['correction_case_id'] or '',join(x['overlap_case_ids']),x['next_action'],
  image(o),link(o.get('folder_url'),'Dropbox folder'),o.get('file_id') or 'Unbound',o.get('folder_id') or 'Unbound',
  'Working visual-pattern attribution; exact native tuple lookup. Owner pattern declaration and exact physical/configuration certification remain unconfirmed.' if t else 'Source/draft scope only; no current native execution or exact physical configuration claim.',
  '',human(x['prior_overall_disposition'])])
fieldmap=[('Dimensions / depth','Dimensions'),('Weight','Approximate weight'),('Material / finish','Finish'),('Fixing','Fixing options'),('Individual price','Price'),('Availability','Availability')]
correction_rows=[]
for c in corrections['records']:
 o=byid[c['product_id']];native=c['native_record_identity']
 for field,public in fieldmap:
  f=o['master_fields'][field]
  correction_rows.append([c['case_id'],o['product_id'],o['name'],field,f['display'],c['proposed_public_specification_fields'][public],f['state'],
   native.get('product_id',''),native.get('variant_id',''),native.get('sku',''),link(native.get('url'),'Source page'),
   'Prepared copy for review. Accepted working values and source conflicts remain authoritative; physical specifications and current native configuration are unverified.',
   image(o),link(o.get('folder_url'),'Dropbox folder'),'Prepared; not executed',''])
draft_rows=[]
for r in review['entries']:
 o=byid[r['product_id']];d=r.get('draft_listing');custom=r.get('custom_unlisted_pattern_draft')
 if not d and not custom:continue
 if d:
  typ='Individual option draft';sku=d['proposed_sku'];group=d['proposed_product_group_id'];ref=d['proposed_variant_reference'];condition=d['activation_condition'];media=d['media_condition'];drafttitle=d['title']
 else:
  typ='Custom / unlisted pattern scope';sku='';group=custom['draft_scope_id'];ref='No existing native pattern/variant assigned';condition='Check current admin/drafts and pattern identity before creating a custom listing. This scope does not prove live absence.';media='Use the kept visual-name reference; material/size/build and exact native-pattern identity retain their recorded qualifications.';drafttitle=o['name']
 draft_rows.append([o['product_id'],drafttitle,typ,sku,group,ref,o['sale_unit'],link("#'Specifications'!D"+str(specrow[o['product_id']]),'Six working fields'),
  image(o),link(o.get('folder_url'),'Dropbox folder'),o.get('file_id') or 'Unbound',o.get('folder_id') or 'Unbound',
  human(r['source_resolution_disposition']),join(r['remaining_evidence_gaps']),condition,media,'Draft only; not created',''])
assert len(draft_rows)==100 and sum(r[2]=='Individual option draft' for r in draft_rows)==97
action_rows=[]
for a in actions['actions']:
 o=byid.get(a.get('catalogue_option_id'));source=next((s for s in g['current_listing_source_links']['offers'] if s['offer_ref']==a.get('source_offer_ref')),None)
 ident=a.get('native_identity') or {'product_id':a.get('native_product_id',''),'url':source['Squarespace'].get('url') if source else None}
 body=a['request_draft']['body'];parts=[]
 for k,v in body.items():
  if k=='description':parts.append('Description: see Listing Corrections')
  elif k=='isVisible':parts.append('Catalogue visibility: hidden (draft proposal)')
  else:parts.append(k+': '+str(v.get('value') if isinstance(v,dict) and 'value' in v else v))
 if a.get('reason'):parts.append('Reason: '+a['reason'])
 action_rows.append([a['action_id'],o['name'] if o else source['source_title'] if source else a.get('catalogue_option_id',''),human(a['action_type']),ident.get('product_id',''),ident.get('variant_id',''),ident.get('sku',''),
  link(ident.get('url'),'Source page'),'\n'.join(parts),'\n'.join(a['preconditions']),json.dumps(a.get('commercial_mode_dependency'),ensure_ascii=False),
  a.get('native_sku_action','See proposed change; not executed'),a.get('inventory_and_shipping_measurements_action','No stock/shipping change in this request draft'),'Prepared; not executed','',a.get('catalogue_option_id','')])
defs={
 'Listing Resolution':{'title':'Current listing resolution','note':'21October review.47 source-supported individual design options,4 conditional Wall Circle tuple lookups,33 retained set-only options and100 remaining source gaps/candidates. No native changes executed.',
 'headers':['Option ID','Individual sculpture / option','Current source result','Source record (1=yes)','Conditional WC (1=yes)','Reviewed in106 (1=yes)','Working native pattern','Working diameter','Working lighting','Conditional SS product ID','Conditional SS variant ID','Conditional native SKU','Proposed draft SKU','Custom pattern draft scope','Copy correction case','Overlap / collision cases','Next action','Current image','Containing folder','Dropbox file ID','Dropbox folder ID','Evidence and execution scope','Owner review notes','20October source result'],
 'rows':current_rows,'widths':[25,58,94,22,22,18,48,26,28,35,51,29,35,61,53,70,126,23,20,40,40,120,95,85],'editable':['W']},
 'Listing Corrections':{'title':'Prepared corrections for four existing listings','note':'24 proposed public-copy fields. Accepted specifications are shown alongside the proposals and remain unchanged. These drafts have not been applied to Squarespace or Shopify.',
 'headers':['Correction case','Option ID','Individual sculpture / option','Specification','Accepted working description','Proposed listing copy','Accepted review state','Native product ID','Native variant ID','Native source SKU','Source page','Qualification','Current image','Containing folder','Execution status','Owner response'],
 'rows':correction_rows,'widths':[51,25,58,26,112,112,98,35,51,29,23,120,23,20,29,100],'editable':['P']},
 'Draft Listings':{'title':'Individual listing drafts and custom pattern scopes','note':'97 proposed individual-option SKUs in76 draft product groups, plus3 custom/unlisted Wall Circle scopes. DRAFT identifiers are local proposals. Check existing native records before creating products.',
 'headers':['Option ID','Draft title','Draft type','Proposed draft SKU','Proposed product group / scope','Proposed variant reference','Sale unit','Accepted specifications','Current image','Containing folder','Dropbox file ID','Dropbox folder ID','Source resolution','Remaining evidence gaps','Before creating a native listing','Media conditions','Draft status','Owner response'],
 'rows':draft_rows,'widths':[25,58,43,37,67,66,100,25,23,20,40,40,95,124,128,119,35,100],'editable':['R']},
 'Listing Actions':{'title':'Prepared native listing actions','note':'Seven local request drafts for copy, legacy SKU and visibility changes. Source identity, before-values and access must be verified before any native action. No requests have been executed.',
 'headers':['Action ID','Related sculpture / option','Proposed action','Native product ID','Native variant ID','Native source SKU','Source page','Proposed change','Execution prerequisites','Commercial-mode dependency','SKU treatment','Stock / shipping treatment','Execution status','Owner response','Option ID'],
 'rows':action_rows,'widths':[74,58,72,35,51,29,23,115,135,108,83,88,31,100,25],'editable':['N']}}
for d in defs.values():assert len(d['headers'])==len(d['widths']) and all(len(r)==len(d['headers']) for r in d['rows'])
write(HERE/'workbook-data.json',{'sheets':defs,'counts':handoff['counts'],'old_note_updates':[
 {'sheet':'Listing Reconciliation','cell':'A3','value':'20October source reconciliation retained as dated evidence. Use Listing Resolution for the21October source review. Missing snapshot associations do not prove live absence.'},
 {'sheet':'Listing Issues','cell':'A3','value':'20October issue snapshot retained as dated evidence. Use Listing Resolution, Listing Corrections and Listing Actions for the21October review and prepared changes. No native execution is claimed.'}]})
write(HERE/'preparation-verification.json',{'status':'PASS','sealed_artifacts_verified':241,'options':184,'assigned_review_options':106,'accepted_current_fields':1104,'source_edges_added_separately':3,'draft_rows':100,'correction_rows':24,'native_action_rows':7,'all_current_paths_preserved':True})
print(json.dumps({'status':'PREPARED','sheet_rows':{k:len(v['rows']) for k,v in defs.items()},'source_options':47,'conditional_WC':4,'remaining_cases':100}))
