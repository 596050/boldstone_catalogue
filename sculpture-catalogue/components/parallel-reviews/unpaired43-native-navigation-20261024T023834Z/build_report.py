import json, hashlib, html, unicodedata
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
BASE=Path(__file__).resolve().parent
def read(name): return json.loads((BASE/name).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(name, data): (BASE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def ptr(obj,p):
 for part in p.strip('/').split('/'): obj=obj[int(part)] if isinstance(obj,list) else obj[part.replace('~1','/').replace('~0','~')]
 return obj
def link(path): return 'https://www.dropbox.com/home'+quote(path,safe='/')
def photo_link(path):
 parent,name=path.rsplit('/',1)
 return link(parent)+'?preview='+quote(name,safe='')
def esc(s): return html.escape(str(s),quote=True)
m=read('input-manifest.json'); raw=read('metadata-receipts.json'); f=read('fallback-receipts.json')
receipts={r['query']:r for r in raw['requests']}
q={r['id']:r for r in m['queries']}
register=json.loads(Path(m['baseline_register']['path']).read_text())
rows=[]; annotations=[]; replacements=[]; checks=[]
def check(name,actual,expected=True):
 ok=actual==expected; checks.append({'name':name,'passed':ok,'actual':actual,'expected':expected}); return ok
check('exact_query_receipt_set',set(receipts)==set(q))
check('unique_receipts',len(raw['requests']),len(q))
check('triage_input_unchanged',sha(m['source_triage']['path']),m['source_triage']['sha256'])
check('pinned_register_bytes_unchanged',sha(m['baseline_register']['path']),m['baseline_register']['sha256'])
for o in m['options']:
 current=ptr(register,o['current_option_pointer'])
 assert current['product_id']==o['product_id']
 for k in ['file_id','folder_id','image_url','folder_url']: assert current.get(k)==o[k],(o['name'],k)
 fr=receipts[o['file_id']]; dr=receipts[o['folder_id']]
 fm=fr.get('metadata'); dm=dr.get('metadata')
 row={**o,'file_lookup_status':fr['status'],'folder_lookup_status':dr['status'],
      'native_file_metadata':fm,'native_folder_metadata':dm}
 folderok=bool(dm and dm['id']==o['folder_id'] and dr['metadata_type']=='folder' and dm['path_display'].startswith(m['scope_root']))
 fileok=bool(fm and fm['id']==o['file_id'] and fr['metadata_type']=='file' and fm['path_display'].startswith(m['scope_root']))
 row['folder_verified_by_id']=folderok
 row['file_verified_by_id']=fileok
 row['verified_folder_url']=link(dm['path_display']) if folderok else None
 row['verified_image_url']=photo_link(fm['path_display']) if fileok else None
 row['actual_containing_folder_verified']=bool(fileok and folderok and fm['path_display'].rsplit('/',1)[0]==dm['path_display'])
 if fileok and folderok:
  assert row['actual_containing_folder_verified'],o['name']
  same=fm['path_display']==o['expected_file_path'] and dm['path_display']==o['expected_folder_path']
  if same: row['navigation_status']='EXACT_STABLE_ID_AND_PATH_PAIR_VERIFIED'
  elif fm['path_display'].casefold()==o['expected_file_path'].casefold() and dm['path_display'].casefold()==o['expected_folder_path'].casefold():
   row['navigation_status']='CASE_ONLY_DISPLAY_PATH_NORMALIZATION'
   for field,value in [('image_url',row['verified_image_url']),('folder_url',row['verified_folder_url'])]:
    if value!=o[field]: replacements.append({'product_id':o['product_id'],'name':o['name'],'json_pointer':o['current_option_pointer']+'/'+field,'before':o[field],'after':value,'reason':'Match native path_display capitalization; stable IDs and selected photograph unchanged. No functional broken-link claim.'})
  else: row['navigation_status']='MOVED_OR_RENAMED_REFERENCE_REQUIRES_CORRECTION'
 else:
  row['navigation_status']='PRIMARY_FILE_UNRESOLVED_CONTAINING_FOLDER_VERIFIED'
  fall=next(x for x in f['path_metadata'] if x['original_query']==o['file_id'])
  listing=next(x for x in f['direct_folder_listings'] if x['original_file_id']==o['file_id'])
  complete=all(not p['isError'] for p in listing['pages']) and not listing['pages'][-1].get('has_more') and not listing['pages'][-1].get('cursor')
  entries=[e for p in listing['pages'] for e in p.get('entries',[]) if e]
  absent_id=all(e.get('file_id')!=o['file_id'] for e in entries)
  absent_path=all(e.get('path_display','').casefold()!=o['expected_file_path'].casefold() for e in entries)
  row['path_fallback_status']=fall['status'];row['containing_folder_listing_complete']=complete
  row['selected_id_absent_from_listed_folder']=complete and absent_id
  row['selected_path_absent_from_listed_folder']=complete and absent_path
  row['other_entries_in_containing_folder']=len(entries)
  row['current_primary_verified']=False
  row['preserve_owner_review_hold']=True
  row['replacement_selected']=False
  row['qualification']='Both stable-ID and exact-path metadata calls returned INVALID_ARGUMENT. The saved ID and path were not in the complete direct-child listing of the verified containing folder. This does not establish deletion or account-wide absence. No alternate image is selected or visually reviewed; the Wall Circle owner hold remains.'
  annotations.append({'product_id':o['product_id'],'name':o['name'],'option_pointer':o['current_option_pointer'],'file_id':o['file_id'],'folder_id':o['folder_id'],'status':row['navigation_status'],'current_primary_verified':False,'evidence':row['qualification'],'verified_folder_url':row['verified_folder_url'],'saved_reference_retained_as_history':True,'replacement_selected':False,'owner_hold_preserved':True,'recommended_catalogue_handling':'Record unavailable current navigation separately from historical photo coverage; preserve saved selection, source identity, specifications and held review status.'})
 rows.append(row)
counts={
 'source_rows':m['counts']['source_rows'],'related_options':len(rows),'unique_file_ids':m['counts']['files'],'unique_folder_ids':m['counts']['folders'],
 'initial_metadata_calls':len(raw['requests']),'metadata_returned':sum(r['status']=='METADATA_RETURNED' for r in raw['requests']),
 'metadata_call_errors':sum(r['status']!='METADATA_RETURNED' for r in raw['requests']),
 'fallback_exact_path_metadata_calls':len(f['path_metadata']),'direct_folder_listing_calls':sum(len(x['pages']) for x in f['direct_folder_listings']),
 'primary_files_verified':sum(r['file_verified_by_id'] for r in rows),'containing_folders_verified':sum(r['folder_verified_by_id'] for r in rows),
 'actual_parent_pairs_verified':sum(r['actual_containing_folder_verified'] for r in rows),
 'exact_native_path_pairs':sum(r['navigation_status']=='EXACT_STABLE_ID_AND_PATH_PAIR_VERIFIED' for r in rows),
 'case_only_normalization_options':sum(r['navigation_status']=='CASE_ONLY_DISPLAY_PATH_NORMALIZATION' for r in rows),
 'case_only_url_field_proposals':len(replacements),'unresolved_primary_options':len(annotations),
 'new_image_selections':0,'native_mutations':0,'downloads':0,'new_owner_questions':0,'new_physical_verifications':0,'shared_master_writes':0}
for name,value in [('related_options',48),('initial_metadata_calls',96),('primary_files_verified',46),('containing_folders_verified',48),('exact_native_path_pairs',45),('case_only_normalization_options',1),('unresolved_primary_options',2)]:check(name,counts[name],value)
check('all_returned_native_ids_and_types_match',all(r['status']!='METADATA_RETURNED' or (r['metadata']['id']==r['query'] and r['metadata_type']==q[r['query']]['expected_type']) for r in raw['requests']))
check('returned_objects_remain_inside_authorized_subtree',all(r['status']!='METADATA_RETURNED' or r['metadata']['path_display'].startswith(m['scope_root']) for r in raw['requests']))
check('all_resolvable_files_have_verified_actual_parent',all(not r['file_verified_by_id'] or r['actual_containing_folder_verified'] for r in rows))
check('unresolved_files_evidence_is_complete_but_no_absence_overclaim',all(r.get('containing_folder_listing_complete') and r.get('selected_id_absent_from_listed_folder') and r.get('selected_path_absent_from_listed_folder') and not r.get('replacement_selected') for r in rows if not r['file_verified_by_id']))
check('case_only_proposals_touch_only_current_urls',all(x['json_pointer'].endswith(('/image_url','/folder_url')) and x['product_id']=='BSI-70C7029C1DB1' for x in replacements))
check('current_pointer_unchanged',sha(m['baseline_pointer']['path']),m['baseline_pointer']['sha256'])
status='METADATA_REVIEW_COMPLETE_TWO_UNRESOLVED_PRIMARY_REFERENCES_ONE_CASE_ONLY_NORMALIZATION'
report={'schema':'boldstone.current-primary-navigation-review.v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'status':status,'baseline_register':m['baseline_register'],'baseline_pointer':m['baseline_pointer'],'source_triage':m['source_triage'],'counts':counts,'rows':rows,'scope':'Native metadata and navigation only. Verification of location does not certify image identity, photo role, pattern assignment, source matching or physical specifications.'}
proposal={'schema':'boldstone.current-primary-navigation-proposal.v1','status':'PREPARED_FOR_MAIN_SOLE_WRITER_NOT_APPLIED','recorded_utc':report['recorded_utc'],'baseline_register':m['baseline_register'],'case_only_url_replacements':replacements,'unavailable_primary_annotations':annotations,'existing_owner_holds_preserved':True,'historical_source_evidence_unchanged':True,'platform_payloads':[],'native_operations':[],'selection_or_physical_changes':[],'master_writes':0}
save('navigation-review.json',report);save('correction-proposal.json',proposal)
cards=[]
for row in rows:
 img='<a href="'+esc(row['verified_image_url'])+'">Verified image location</a>' if row['verified_image_url'] else '<span class="hold">Saved primary unresolved</span>'
 folder='<a href="'+esc(row['verified_folder_url'])+'">Containing folder</a>' if row['verified_folder_url'] else 'Folder unresolved'
 status={'EXACT_STABLE_ID_AND_PATH_PAIR_VERIFIED':'Image and actual parent verified','CASE_ONLY_DISPLAY_PATH_NORMALIZATION':'Same selection; native capitalization differs','PRIMARY_FILE_UNRESOLVED_CONTAINING_FOLDER_VERIFIED':'Held Wall Circle reference unresolved'}[row['navigation_status']]
 cards.append('<tr><td>'+esc(row['name'])+'<small>'+esc(row['product_id'])+'</small></td><td>'+img+'<br>'+folder+'</td><td>'+esc(status)+'</td></tr>')
details=[]
for a in annotations: details.append('<li><strong>'+esc(a['name'])+'</strong>: saved primary unavailable by ID and path, and absent from its fully listed containing folder. <a href="'+esc(a['verified_folder_url'])+'">Verified folder</a>. No replacement selected; review remains held.</li>')
page='<!doctype html><html lang="en"><meta charset="utf-8"><title>48 sculpture primary-image locations</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:36px auto;padding:0 20px;color:#202b27}h1{line-height:1.2}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:12px;vertical-align:top;border-bottom:1px solid #cbd6cf}th{background:#eef3ef}a{color:#00624b}small{display:block;color:#66746c;font-size:12px}.hold{color:#985300}.note{background:#f1f5f2;padding:16px;border-radius:8px}</style><h1>48 sculpture primary-image locations</h1><p>Live Dropbox metadata checked '+esc(report['recorded_utc'])+'.</p><p class="note"><strong>46 primary images and all 48 containing folders verified.</strong> There are45 exact path pairs,1 case-only naming normalization and2 unresolved primary references. These are navigation findings, not image-content or physical-specification approvals.</p><ul>'+''.join(details)+'</ul><p><strong>Moon Water Catcher — White:</strong> native family spelling is “Moonwater Catcher”; saved primary URLs use “Moonwater catcher”. The image and folder IDs are unchanged. Normalization is proposed without claiming the old URLs are broken.</p><p>All Wall Circle holds remain. No image was downloaded, moved, replaced or newly approved. Readable current links below come from returned native paths.</p><p><a href="correction-proposal.json">Exact proposal</a> · <a href="navigation-review.json">Full metadata comparison</a> · <a href="saved-readback.json">Integrity readback</a></p><table><thead><tr><th>Sculpture</th><th>Image and folder</th><th>Navigation result</th></tr></thead><tbody>'+''.join(cards)+'</tbody></table></html>'
(BASE/'review.html').write_text(page)
saved=read('navigation-review.json')
check('saved_report_count_readback',len(saved['rows']),48)
check('saved_proposal_has_no_native_operations',read('correction-proposal.json')['native_operations'],[])
validation={'schema':'boldstone.navigation-evidence-integrity.v1','status':'PASS' if all(x['passed'] for x in checks) else 'FAIL','checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),'checks':checks,'native_navigation_outcome':status,'qualification':'Integrity PASS validates the packet and its limits. It does not mark the two unavailable primary images as verified.'}
save('saved-readback.json',validation)
assert validation['status']=='PASS',validation
files=['input-manifest.json','metadata-receipts.json','fallback-receipts.json','build_report.py','navigation-review.json','correction-proposal.json','review.html','saved-readback.json']
seal={'schema':'boldstone.navigation-handoff-seal.v1','status':'SEALED_READ_ONLY_NAVIGATION_REVIEW_WITH_TWO_UNRESOLVED_REFERENCES','recorded_utc':report['recorded_utc'],'reviewer_thread':m['reviewer_thread'],'baseline_register':m['baseline_register'],'counts':counts,'validation':{'status':validation['status'],'checks_passed':validation['checks_passed'],'checks_total':validation['checks_total']},'files':[{'path':str(BASE/x),'sha256':sha(BASE/x),'bytes':(BASE/x).stat().st_size} for x in files],'main_import_performed':False,'native_mutations':0}
save('sealed-handoff.json',seal)
print(json.dumps({'lane':str(BASE),'counts':counts,'validation':seal['validation'],'seal_sha256':sha(BASE/'sealed-handoff.json')},ensure_ascii=False))
