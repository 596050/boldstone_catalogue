from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
b=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue');j=b/'components/parallel-reviews/deco-import-and-residual-photo-review-20261023T203834Z';oldj=b/'components/parallel-reviews/remaining-photo-sources-and-bordered-import-20261023T200049Z';bj=b/'components/parallel-reviews/remaining-photo-source-followup-20261023T200107Z';fresh=b/'components/reconciliation/deco004-photo-and-physical-review-2026-10-23/fresh-family-inventory.json'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def dump(n,d):
 p=j/n;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');return ref(p)
# Reuse root's fresh family lists; each returned page and completeness is checked.
new=[]
for r in json.loads(fresh.read_text())['records']:
 assert r['pages'] and r['pages'][-1]['structuredContent']['has_more'] is False
 for page in r['pages']:
  assert page.get('isError') is not True;new.extend(page['structuredContent']['entries'])
old=[]
for r in json.loads((oldj/'current-unique-family-listings.json').read_text())['records']:
 assert r.get('isError') is not True and r['result']['has_more'] is False;old.extend(r['result']['entries'])
shared=json.loads((bj/'current-family-listings.json').read_text())
retained_prior_unrelated_errors=[]
for r in shared['family_tops']:
 if 'entries' not in r['data']:
  retained_prior_unrelated_errors.append(r);continue
 old.extend(r['data']['entries'])
for r in shared['option_listings']:
 for p in r['pages']:old.extend(p['entries'])
old.extend(json.loads((oldj/'current-mp4-silver-folder.json').read_text())['entries'])
oldmap={x['file_id']:x for x in old if x['object_type']=='file'};newmap={x['file_id']:x for x in new if x['object_type']=='file'};parentmap={x['path'].casefold():x['file_id'] for x in new if x['object_type']=='folder'}
rows=json.loads((j/'series17-current-plan.json').read_text());assert len(rows)==17
prior={x['option_id']:x for x in json.loads((b/'components/parallel-reviews/series-gap-review-20261023T190939Z/review-findings.json').read_text())['residual_tasks']}
reviews=[]
for row in rows:
 p=row['primary'];parent=p['path'].rsplit('/',1)[0];prefix=parent.casefold()+'/'
 before={k:x for k,x in oldmap.items() if x['path'].rsplit('/',1)[0].casefold()==parent.casefold()};after={k:x for k,x in newmap.items() if x['path'].rsplit('/',1)[0].casefold()==parent.casefold()}
 assert p['file_id'] in after and parentmap[parent.casefold()]==p['folder_id']
 added=sorted(after.keys()-before.keys());absent=sorted(before.keys()-after.keys());changed=[]
 for fid in after.keys()&before.keys():
  a=after[fid];z=before[fid];fields={k:{'before':z.get(k),'after':a.get(k)} for k in ['name','path','client_modified','modified_time'] if z.get(k)!=a.get(k)}
  if z.get('file',{}).get('size')!=a.get('file',{}).get('size'):fields['size']={'before':z.get('file',{}).get('size'),'after':a.get('file',{}).get('size')}
  if fields:changed.append({'file_id':fid,'fields':fields})
 assert not added and not absent and not changed,(row['name'],added,absent,changed)
 reviews.append({'option_id':row['option_id'],'name':row['name'],'family':row['family'],'requested_role':'Series','current_status':'No verified image','review_status':'CURRENT_EXACT_PARENT_METADATA_UNCHANGED_PRIOR_QUALIFIED_VISUAL_FINDINGS_RETAINED','exact_parent':parent,'actual_parent_id':p['folder_id'],'current_files':len(after),'current_primary_found':True,'added_ids':added,'absent_ids':absent,'changed_metadata':changed,'previous_visual_finding':prior[row['option_id']]['current_role_basis'],'required_input':prior[row['option_id']]['next_required_input'],'new_qualified_reference':None,'all_current_originals_rehashed':False,'personal_owner_image_approval_added':False,'physical_verification_added':False})
report={'schema':'boldstone.residual-series-source-review.v2','recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'ALL17_CURRENT_SERIES_PARENT_REVIEWS_COMPLETE_NO_NEW_SUPPORTED_BINDING','current_source_scope':'Current BOLDSTONE MASTER exact target parents from root complete17-family lists. Prior whole-image visual reviews reused for unchanged source metadata. Targeted Pewter search adds no current exact group source. Not an exhaustive global visual absence proof; metadata equality does not claim all file-byte equality.','fresh_shared_inventory':ref(fresh),'baseline_current_register':json.loads((j/'baseline-pointer.json').read_text())['register'],'prior_full_series_review':ref(b/'components/parallel-reviews/series-gap-review-20261023T190939Z/review-findings.json'),'previous_review_delta':ref(oldj/'residual-source-delta-review.json'),'pewter_targeted_searches':ref(j/'pewter-targeted-searches.json'),'reviews':reviews,'counts':{'series_roles_reviewed':17,'new_series_bindings':0,'series_source_requests_remaining':17,'parent_file_memberships_checked':sum(x['current_files'] for x in reviews),'target_parent_metadata_changes':0,'target_parent_id_changes':0,'native_or_platform_writes':0,'canonical_or_workbook_writes':0,'physical_photographs_taken':0},'pewter':{'current_exact_folder':ref(j/'fresh-pewter-folder.json'),'current_individual_primary_unchanged':'id:cnqzTNngPVsAAAAAAA6VmA','current_folder_files':2,'current_group_display_source_found':False,'no_historical_ID_errors_retried':True,'historical_owner_back_right_identity_preserved':True,'filename_search_completeness':'Six returned title matches, has_more=false. Newly created primary6VmA is absent from search results despite a successful live metadata and folder listing, so search index completeness is not inferred.','physical_capture_needed_if_no_exact_source_supplied':'One whole group/display photo with the complete One Leaf Left Pewter, identifiable companions and visible setting; identify its position.'}}
report['retained_prior_inventory_errors']={'source':ref(bj/'current-family-listings.json'),'records':retained_prior_unrelated_errors,'treatment':'Prior Egyptian Two Palms alias INVALID_ARGUMENT retained as dated failure. Correct current Egyptian Palm record and exact complete17-parent memberships independently checked; no current failure suppressed.'}
r=dump('series17-review-and-pewter-outcome.json',report);print(json.dumps({'receipt':r,'counts':report['counts'],'pewter_files':2}))
