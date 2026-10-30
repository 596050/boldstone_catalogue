"""Independent read-only audit of the 278-scope refresh; writes only beside this file."""
import json
import re
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone

W=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
PATHS={
 'refresh':ROOT/'components/reviews/workbook-refresh-2026-10-19/refresh-data.json',
 'progress':ROOT/'components/reviews/specification_review_progress.json',
 'decisions':ROOT/'components/reviews/user_classifications.json',
}
raw={k:v.read_bytes() for k,v in PATHS.items()}
hashes={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
x,p,u=[json.loads(raw[k]) for k in ['refresh','progress','decisions']]
fields=['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']
review={tuple(r[:2]):r for r in x['reviews']}
specs=defaultdict(list)
for i,r in enumerate(x['specifications']):specs[tuple(r[:2])].append((i,r))

# Locate actual scoped nodes without importing the mutating refresh builder.
nodes={};locators={}
for cid,n in p['reviews'].items():
 own=n.get('size_finish_variant_id') or n.get('build_variant_id')
 if own:nodes[(cid,own)]=n;locators[(cid,own)]=['reviews',cid]
 elif n.get('canonical_design_record'):
  nodes[(cid,'BASE')]=n['canonical_design_record'];locators[(cid,'BASE')]=['reviews',cid,'canonical_design_record']
 else:nodes[(cid,'BASE')]=n;locators[(cid,'BASE')]=['reviews',cid]
 for ck in ['size_finish_variants','build_variants','component_layouts','source_reference_reviews']:
  for scope,v in n.get(ck,{}).items():
   if (cid,scope) not in nodes:nodes[(cid,scope)]=v;locators[(cid,scope)]=['reviews',cid,ck,scope]
for scope,n in p.get('catalogue_alias_reviews',{}).items():
 cid=n.get('catalogue_design_key',scope);nodes[(cid,scope)]=n;locators[(cid,scope)]=['catalogue_alias_reviews',scope]
for scope,n in p.get('source_design_reviews',{}).items():
 if n.get('record_kind','').startswith('INDIVIDUAL_WHOLE_SOURCE'):
  nodes[('UGR-G310',scope)]=n;locators[('UGR-G310',scope)]=['source_design_reviews',scope]
for batch in range(92,98):
 rp=ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}/import-receipt.json'
 if not rp.is_file():continue
 for item in json.loads(rp.read_text())['scopes']:
  cid,scope=item['component_id'],item['size_finish_variant_id']
  loc=item.get('model_locator') or ['reviews',cid,'build_variants' if item['review_scope']=='BUILD' else 'size_finish_variants',scope]
  n=p
  for part in loc:n=n[part]
  nodes[(cid,scope)]=n;locators[(cid,scope)]=loc

pid_evidence=defaultdict(list)
for ledger,items in u.items():
 if not isinstance(items,list):continue
 for d in items:
  if not isinstance(d,dict):continue
  for pid in d.get('approved_proposal_ids',[]):
   pid_evidence[pid].append({'ledger':ledger,'decision_id':d.get('decision_id'),'approval_record':d.get('approval_record'),'standing_policy_id':d.get('standing_working_approval_policy_id')})

ref_dispositions=p['weight_review_output_overlays']['reference_dispositions']
refkeys={tuple(k.split('|',1)) for k in ref_dispositions}
unknown_starts=('Not established for this exact review scope','No component dimensions established','No individual weight established','No object-specific substrate claim identified','Unconfirmed; size and construction')
appearance_material=[]
quote_price=[]
historical_only=[]

def category(r,reference_scope):
 display,state=r[4],r[5]
 if reference_scope:return 'REFERENCE_OR_DEFERRED_SCOPE'
 if display.startswith('Use the finish-specific record;'):return 'REFERENCE_ONLY_FIELD'
 if display.startswith('Previous proposed price') and 'retained in history' in display:return 'PRIOR_PRICE_REFERENCE_CURRENT_QUOTE_PENDING'
 if r[3]=='Fixing' and ('Fixing choice: Keyhole fixing or French cleat' in display) and (display.startswith(unknown_starts) or display.startswith('See linked native/source claims')):
  return 'OWNER_CATALOGUE_FIXING_CHOICE_ONLY_ACTUAL_HARDWARE_UNKNOWN'
 if display.startswith(unknown_starts):return 'UNKNOWN_ONLY_FIELD'
 if r[3]=='Individual price' and not re.search(r'\d',display) and re.search(r'quote|enquir|request',display,re.I):return 'ENQUIRY_QUOTE_POLICY_NO_NUMERIC_PRICE'
 if r[3]=='Material / finish' and re.search(r'appearance',display,re.I) and not re.search(r'Jesmonite|gypsum|plaster|cast |cement|wood|fibrous|fibre|composite|resin',display,re.I):return 'VISIBLE_APPEARANCE_ONLY_SUBSTRATE_UNKNOWN'
 if re.search(r'guess|hypothes|proposal|proposed|assum|conditional',display,re.I):return 'SUBSTANTIVE_WORKING_PROPOSAL_OR_CONDITIONAL_ESTIMATE'
 return 'SUBSTANTIVE_SOURCE_OWNER_OR_DESCRIPTION_BODY'

field_audit=[];scope_audit=[];structural=[]
for key,rr in review.items():
 items=specs[key];labels=[r[3] for _,r in items];missing=sorted(set(fields)-set(labels));duplicates=[k for k,v in Counter(labels).items() if v!=1]
 if len(items)!=6 or missing or duplicates:structural.append({'key':list(key),'rows':len(items),'missing':missing,'duplicate_or_extra_labels':duplicates})
 node=nodes.get(key,{})
 reference_scope=key in refkeys
 statuses={r[3]:('Owner accepted working proposal; not physically verified' in r[5]) for _,r in items}
 kept=rr[4].startswith('Owner kept') or rr[3]=='Catalogue alias'
 if reference_scope:scope_category='REFERENCE_OR_OWNER_DEFERRED_NOT_NEW_INDIVIDUAL'
 elif all(statuses.values()):scope_category='SIX_FIELDS_EXPLICITLY_LABELLED_WORKING_ACCEPTED'
 elif kept:scope_category='KEPT_SCOPE_MIXED_FIELD_ACCEPTANCE'
 else:scope_category='UNREVIEWED_SOURCE_OR_ALIAS_CANDIDATE'
 acceptance_path=node.get('specification_approval')
 if acceptance_path:
  ap=Path(acceptance_path);ap=ap if ap.is_absolute() else ROOT/ap
  approval={'record':acceptance_path,'exists':ap.is_file(),'sha256':hashlib.sha256(ap.read_bytes()).hexdigest() if ap.is_file() else None}
 else:approval=None
 sa={'component_id':key[0],'scope':key[1],'name':rr[2],'kind':rr[3],'identity_display':rr[4],'specification_status_display':rr[5],'scope_category':scope_category,'kept_name_or_catalogue_alias':kept,'structurally_complete_six_fields':not(missing or duplicates) and len(items)==6,'node_locator':locators.get(key),'explicit_working_accepted_field_count':sum(statuses.values()),'specification_approval':approval,'node_all_six_working_accepted':node.get('all_six_working_specification_fields_accepted'),'working_acceptance_basis':node.get('working_acceptance_basis'),'standing_policy_id':node.get('standing_working_approval_policy_id'),'owner_answer_for_this_scope':node.get('owner_answer_for_this_scope'),'reference_disposition':ref_dispositions.get('|'.join(key)),'fields':{},'missing_working_body_fields':[],'physical_specs_verified':node.get('physical_specs_verified'),'actual_stock_verified':node.get('actual_stock_verified')}
 for ix,r in items:
  cat=category(r,reference_scope)
  accepted=statuses[r[3]]
  if reference_scope:acceptance='REFERENCE_OR_DEFERRED_NOT_INDIVIDUAL_WORKING_ACCEPTANCE'
  elif accepted:acceptance='EXPLICIT_WORKING_ACCEPTANCE_LABEL'
  elif r[3]=='Weight' and 'accepted' in r[5].lower() and not reference_scope:acceptance='GLOBAL_WEIGHT_ACCEPTANCE_WITH_CONDITIONS'
  elif r[3]=='Fixing' and 'Owner instructed catalogue fixing choice' in r[5]:acceptance='GLOBAL_FIXING_CHOICE_ONLY'
  elif 'Scoped owner statement' in r[5]:acceptance='SCOPED_OWNER_STATEMENT_NOT_WHOLE_CARD_ACCEPTANCE'
  else:acceptance='NO_WORKING_ACCEPTANCE_LABEL'
  pids=[z for z in r[11].split('\n') if z]
  covered_body=cat not in ['UNKNOWN_ONLY_FIELD','REFERENCE_ONLY_FIELD','REFERENCE_OR_DEFERRED_SCOPE','PRIOR_PRICE_REFERENCE_CURRENT_QUOTE_PENDING']
  record={'refresh_array_index_zero_based':ix,'component_id':key[0],'scope':key[1],'name':r[2],'field':r[3],'display':r[4],'state':r[5],'basis':r[6],'content_class':cat,'substantive_scoped_body_present':covered_body,'acceptance_class':acceptance,'proposal_ids':pids,'decision_ledger_matches':{pid:pid_evidence[pid] for pid in pids if pid_evidence.get(pid)},'approval_record':approval['record'] if approval else None,'kept_name_or_catalogue_alias':kept,'scope_category':scope_category}
  field_audit.append(record);sa['fields'][r[3]]={'content_class':cat,'substantive_scoped_body_present':covered_body,'acceptance_class':acceptance,'display':r[4]}
  if not covered_body:sa['missing_working_body_fields'].append(r[3])
  if kept and cat=='VISIBLE_APPEARANCE_ONLY_SUBSTRATE_UNKNOWN':appearance_material.append(record)
  if kept and cat=='ENQUIRY_QUOTE_POLICY_NO_NUMERIC_PRICE':quote_price.append(record)
  if kept and cat=='PRIOR_PRICE_REFERENCE_CURRENT_QUOTE_PENDING':historical_only.append(record)
 sa['complete_substantive_working_representation']=not sa['missing_working_body_fields']
 scope_audit.append(sa)

def resolved_record(value):
 pp=Path(value);pp=pp if pp.is_absolute() else ROOT/pp
 return {'path':str(pp),'exists':pp.is_file(),'sha256':hashlib.sha256(pp.read_bytes()).hexdigest() if pp.is_file() else None}

group_audit=[];group_identity_defects=[]
source_decisions={d['source_design_key']:d for d in u['source_design_name_decisions']}
for row in x['groups']:
 gid=row[0]
 if gid.startswith('FINGERPRINT-'):
  node=p['source_design_reviews'][gid];decision=source_decisions.get(gid,{})
  typ='OWNER_DEFERRED_COMPONENT_IDENTIFICATION_GROUP_REFERENCE'
  decision_ref=decision.get('approval_record');name_supported=bool(decision_ref)
  mismatch=name_supported and row[2].startswith('Name proposed / unconfirmed')
  if mismatch:group_identity_defects.append({'group_id':gid,'name':row[1],'displayed_identity':row[2],'name_decision_id':decision.get('decision_id'),'approval_record':decision_ref,'recommended_display':'Owner kept source name; owner says design was made; individual components deferred','limits':'Name-only approval, not component decomposition or whole-group specifications/stock.'})
  scope_records=[p['group_photo_review_policy'].get('approval_record')]
  record_kind=node['record_kind'];duplicate=node.get('duplicate_source_image_evidence')
 elif gid.startswith('MOONPHASE-WATER-'):
  node=p['arrangement_reviews'][gid];typ='ARRANGEMENT_NAME_ONLY_NOT_INDIVIDUAL_WHOLE_PRODUCT';decision_ref=node.get('approval_record');name_supported=node.get('name_identity_confirmed');mismatch=False;scope_records=[p['group_photo_review_policy'].get('approval_record')];record_kind=node['record_kind'];duplicate=None
 elif gid in p['group_photo_review_dispositions']:
  node=p['group_photo_review_dispositions'][gid];typ='OWNER_DEFERRED_MIXED_GROUP_CONTEXT';decision_ref=node.get('owner_scope_record');name_supported=True;mismatch=False;scope_records=[decision_ref];record_kind=node['treatment'];duplicate=None
 else:
  node=next(d for d in u['collection_scope_decisions'] if d['group_ref']==gid);typ='OWNER_COLLECTION_ONLY_ALL_INDIVIDUAL_WORK_DEFERRED';decision_ref=node.get('approval_record');name_supported=True;mismatch=False;scope_records=[decision_ref];record_kind=node['classification'];duplicate=None
 group_audit.append({'group_id':gid,'name':row[1],'classification':typ,'record_kind':record_kind,'whole_individually_sellable_product_established':False,'name_approval_supported_by_existing_record':name_supported,'name_display_defect':mismatch,'name_or_scope_decision':resolved_record(decision_ref) if decision_ref else None,'owner_scope_record':scope_records,'six_field_group_body':row[4],'specification_display_state':row[5],'source_notes':row[10],'individual_component_identification_required_now':False,'component_decomposition_only_on_owner_request':True,'physical_manufacture_basis':'Owner universal manufacture policy; no independent per-image manufacture or stock proof','actual_stock_verified':False,'duplicate_image_evidence':duplicate})

# Verify primary owner-policy and key group receipts against exact local transcript lines.
def policy_evidence(node):
 for k in ['authoritative_user_evidence','verified_authoritative_user','owner_evidence']:
  d=node.get(k)
  if isinstance(d,dict) and d.get('line') and d.get('text') and (d.get('transcript') or d.get('transcript_path')):return d
 return None

targets=[]
for name in ['physical_manufacture_review_policy','working_specification_acceptance_policy','global_fixing_choice_policy','global_approximate_weight_policy','group_photo_review_policy']:
 targets.append((name,policy_evidence(p[name])))
for gid in ['FINGERPRINT-WAVY-WHITE-G156001','FINGERPRINT-SEGMENTED-WHITE-G156002']:
 d=source_decisions[gid];rp=ROOT/d['approval_record'];targets.append((gid,policy_evidence(json.loads(rp.read_text()))))
targets.append(('MOONPHASE-WATER-FEATURE-WHITE-01',policy_evidence(p['arrangement_reviews']['MOONPHASE-WATER-FEATURE-WHITE-01'])))

by_path=defaultdict(dict)
for name,d in targets:
 if d:by_path[d.get('transcript') or d['transcript_path']][d['line']]=d
line_cache={}
for pathname,lines in by_path.items():
 with open(pathname,'rb') as stream:
  for i,line in enumerate(stream,1):
   if i in lines:line_cache[(pathname,i)]=line
   if i>=max(lines):break

transcript_checks=[]
for name,d in targets:
 if not d:transcript_checks.append({'name':name,'status':'NO_EXACT_TRANSCRIPT_LOCATOR'});continue
 path=d.get('transcript') or d['transcript_path'];line=line_cache.get((path,d['line']))
 if line is None:transcript_checks.append({'name':name,'status':'MISSING_TRANSCRIPT_LINE'});continue
 data=json.loads(line);payload=data.get('payload',{});texts=[]
 if isinstance(payload.get('message'),str):texts.append(payload['message'])
 if isinstance(payload.get('text'),str):texts.append(payload['text'])
 for part in payload.get('content',[]) if isinstance(payload.get('content'),list) else []:
  if isinstance(part,dict) and isinstance(part.get('text'),str):texts.append(part['text'])
 literal='\n'.join(texts)
 # User response_item content is authoritative; event_msg wrappers vary by exporter.
 role=payload.get('role') or ('user' if payload.get('type')=='user_message' else None)
 same_text=literal==d['text']
 digest=hashlib.sha256(d['text'].encode()).hexdigest()
 declared=d.get('text_sha256') or d.get('text_sha256_utf8')
 raw_digests={hashlib.sha256(line).hexdigest(),hashlib.sha256(line.rstrip(b'\r\n')).hexdigest()}
 transcript_checks.append({'name':name,'transcript':path,'line':d['line'],'role':role,'text':d['text'],'text_matches_exact_transcript':same_text,'text_sha256_matches':not declared or declared==digest,'raw_line_sha256_matches_either_line_ending_convention':not d.get('raw_line_sha256') or d['raw_line_sha256'] in raw_digests,'status':'PASS' if role=='user' and same_text and (not declared or declared==digest) else 'CHECK_NEEDED'})

old_progress_source=next(z for z in x['source_files'] if z.get('source','').endswith('specification_review_progress.json'))
old_progress=json.loads(Path(old_progress_source['snapshot']).read_text())
drift=[k for k in p if p[k]!=old_progress.get(k)]
accepted_scopes=[s for s in scope_audit if s['explicit_working_accepted_field_count']==6]
kept=[s for s in scope_audit if s['kept_name_or_catalogue_alias']]
summary={
 'schema':'boldstone.independent-six-field-and-group-coverage-audit.v1','worker_number':3,
 'audited_utc':datetime.now(timezone.utc).isoformat(),'refresh_as_of_utc':x['as_of_utc'],
 'inputs':{k:{'path':str(PATHS[k]),'sha256':hashes[k]} for k in PATHS},
 'scope_counts':{'review_rows':len(x['reviews']),'unique_review_scopes':len(review),'specification_rows':len(x['specifications']),'group_reference_rows':len(x['groups']),'structurally_complete_six_field_scopes':len(scope_audit)-len(structural),'blank_display_rows':sum(not r[4].strip() for r in x['specifications']),'explicitly_six_field_working_accepted_scopes':len(accepted_scopes),'explicit_working_accepted_field_rows':sum(z['acceptance_class']=='EXPLICIT_WORKING_ACCEPTANCE_LABEL' for z in field_audit),'kept_name_or_catalogue_alias_scopes':len(kept),'kept_scopes_with_six_substantive_current_working_bodies':sum(s['complete_substantive_working_representation'] for s in kept),'kept_scopes_with_history_only_current_price_gap':len(historical_only),'kept_scopes_with_numeric_price_not_assigned_but_quote_policy':len(quote_price),'kept_material_rows_appearance_only_substrate_unknown':len(appearance_material)},
 'scope_categories':dict(Counter(s['scope_category'] for s in scope_audit)),
 'field_content_counts':dict(Counter(r['content_class'] for r in field_audit)),
 'field_acceptance_counts':dict(Counter(r['acceptance_class'] for r in field_audit)),
 'field_content_by_field':{f:dict(Counter(r['content_class'] for r in field_audit if r['field']==f)) for f in fields},
 'group_categories':dict(Counter(g['classification'] for g in group_audit)),
 'structural_missing_fields_or_duplicate_rows':structural,
 'kept_scope_working_body_gaps':[{'component_id':s['component_id'],'scope':s['scope'],'name':s['name'],'fields':s['missing_working_body_fields']} for s in kept if s['missing_working_body_fields']],
 'group_identity_display_defects':group_identity_defects,
 'key_findings':[
  'All 278 scopes have all six unique field rows and nonblank displays. Row presence is not evidence that a physical value, current stock or current price is known.',
  '173 scopes have six explicit working-acceptance labels; Chelsea BASE adds five old accepted labels and an accepted replacement conditional weight under the global policy. Its displayed £1,100 is retained history awaiting reconfirmation for the corrected 250×100 cm size.',
  '174 kept-name/catalogue-alias scopes are overlapping review units, not 174 unique physical sculptures or independently verified sellable stock.',
  '19 kept-name/catalogue-alias scope price rows explicitly say quote required rather than assigning a numeric ask (15 owner-kept non-alias rows plus four current Moonphase alias finish scopes). They provide a commercial enquiry policy, not a numerical selling price.',
  'First two Fingerprint group-name displays are stale: batch18 and batch19 already approve their source names. Only those name labels should be corrected; component identification and actual specifications remain deferred.',
  'Moonphases Water Feature is sealed ARRANGEMENT_NAME_ONLY, not an approved individual whole product. Wall-set dimensions/weight exclude basin/water and cannot become whole-fountain values.',
  'Soundwave — White is a distinct contrast: INDIVIDUAL_WHOLE_SOURCE_OWNER_NAMED, listed in the 278 review scopes with accepted working fields, not among the 22 groups.',
  'The 18 Fingerprint group rows include the same-pixels Offset Spiral/Rough Concentric canonical-name pair. They are source references and not 18 new individual products.',
  'Owner universal manufacture, standing working acceptance, catalogue fixing choice and approximate weights have different scopes. None independently certifies current stock, engineering, measured values or image authenticity.',
 ],
 'acceptance_receipt_inventory':{'kept_scopes_with_specification_approval_path':sum(bool(s['specification_approval']) for s in kept),'missing_approval_paths':[s['specification_approval'] for s in kept if s['specification_approval'] and not s['specification_approval']['exists']],'no_node_approval_path_scopes':[[s['component_id'],s['scope']] for s in kept if not s['specification_approval']]},
 'policy_and_key_receipt_transcript_checks':transcript_checks,
 'progress_since_refresh_snapshot':{'snapshot_sha256':old_progress_source['sha256'],'current_sha256':hashes['progress'],'changed_top_level_keys':drift,'reviews_and_decisions_unchanged':all(k not in drift for k in ['reviews','source_design_reviews','arrangement_reviews','catalogue_alias_reviews','physical_manufacture_review_policy','working_specification_acceptance_policy','global_fixing_choice_policy','global_approximate_weight_policy'])},
 'boundaries':{'central_edits':0,'remote_reads':0,'remote_mutations':0,'new_owner_approvals':0,'new_physical_stock_claims':0,'new_images_reviewed':0,'method':'Read-only JSON/source-receipt/transcript audit; no workbook authoring, file mutation or remote link inspection.'},
 'inputs_changed_during_audit':{k:hashlib.sha256(PATHS[k].read_bytes()).hexdigest()!=hashes[k] for k in PATHS},
}
for name,data in [('findings.json',summary),('scope-coverage.json',scope_audit),('field-audit.json',field_audit),('group-audit.json',group_audit),('quote-only-price-scopes.json',quote_price),('appearance-only-material-scopes.json',appearance_material)]:
 (W/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'counts':summary['scope_counts'],'scope_categories':summary['scope_categories'],'field_content_counts':summary['field_content_counts'],'field_acceptance_counts':summary['field_acceptance_counts'],'group_categories':summary['group_categories'],'receipt_inventory':summary['acceptance_receipt_inventory'],'policy_checks':[(z['name'],z['status']) for z in transcript_checks],'input_drift':summary['inputs_changed_during_audit']},ensure_ascii=False,indent=2))
