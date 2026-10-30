"""Compare every projected scope with the last publication and frozen imports."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
BASE='89c628442d2740db92064f7c66e203c965fabd59b7bcb00e0360971ffacc7c98'
old=read(HERE/'history'/BASE/'refresh-data.json');cur=read(HERE/'refresh-data.json');p=read(HERE/'snapshot/reviews.json');u=read(HERE/'snapshot/decisions.json');checks={};allowed={};scopes=[]
fields={'dimensions':'Dimensions / depth','weight':'Weight','material_finish':'Material / finish','fixing':'Fixing','individual_price':'Individual price','availability':'Availability'}
for batch in range(92,98):
 r=read(ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}/import-receipt.json')
 for x in r['scopes']:
  key=(x['component_id'],x['size_finish_variant_id']);allowed[key]=x;scopes.append((batch,x))
allowed.update({('BC-BAR-WAVE','BASE'):{},('BC-MCP-4','BASE'):{},('BC-PORTMAN-1','BASE'):{}})
oldreviews={tuple(x[:2]):x for x in old['reviews']};reviews={tuple(x[:2]):x for x in cur['reviews']};oldspec={tuple(x[:2])+(x[3],):x for x in old['specifications']};specs={tuple(x[:2])+(x[3],):x for x in cur['specifications']}
nativefolders={}
for batch in range(92,97):
 for x in read(ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}/current-reference-check.json')['metadata']:
  if x['metadata_type']=='folder':nativefolders[x['folder']['id']]=x['folder']['path_display']
def unchanged_or_native_folder_case(prior,row):
 if prior==row:return True
 changed=[i for i,(a,b) in enumerate(zip(prior,row)) if a!=b]
 return changed==[8] and prior[8].lower()==row[8].lower() and row[10] in nativefolders and row[8]=='https://www.dropbox.com/home'+quote(nativefolders[row[10]],safe='/')
checks['all278_review_keys_and1668_six_field_keys_unchanged']=set(reviews)==set(oldreviews) and set(specs)==set(oldspec) and len(reviews)==278 and len(specs)==1668
for key,row in reviews.items():
 if key not in allowed:checks['prior_review_unchanged_or_native_folder_case:'+str(key)]=unchanged_or_native_folder_case(oldreviews[key],row)
for key,row in specs.items():
 if key[:2] not in allowed:checks['prior_specification_unchanged_or_native_folder_case:'+str(key)]=unchanged_or_native_folder_case(oldspec[key],row)
for batch,x in scopes:
 key=(x['component_id'],x['size_finish_variant_id']);loc=x.get('model_locator') or ['reviews',key[0],('build_variants' if x['review_scope']=='BUILD' else 'size_finish_variants'),key[1]];node=p
 for part in loc:node=node[part]
 checks['imported_scope:'+str(key)]=node['all_six_working_specification_fields_accepted'] and all(node['accepted_working_specifications'][f]['display'] in specs[key+(label,)][4] and 'Owner accepted working proposal; not physically verified' in specs[key+(label,)][5] and node['accepted_working_specifications'][f].get('proposal_id',node['approved_proposal_ids'][i]) in specs[key+(label,)][11].split('\n') for i,(f,label) in enumerate(fields.items()))
 checks['exact_IDs_and_working_status:'+str(key)]=reviews[key][9:11]==[node['current_dropbox_reference']['file_id'],node['current_dropbox_reference']['folder_id']] and ('working' in reviews[key][5].lower()) and reviews[key][6]==oldreviews[key][6]
 checks['no_per_scope_fabricated_reply:'+str(key)]=node.get('owner_answer_for_this_scope') is None and all('no individual reply recorded' in specs[key+(label,)][5] or 'fixing type subsequently owner-stated' in specs[key+(label,)][5] for label in fields.values())
checks['121_new_working_scopes_and_prior_IDs_deduplicated']=len(scopes)==121 and len({(x['component_id'],x['size_finish_variant_id']) for _,x in scopes})==121 and u['specification_approval_counts']['proposal_groups']==1045
for field,label in fields.items():
 checks['Barbados_recovered_prior_field:'+field]=p['reviews']['BC-BAR-WAVE']['accepted_working_specifications'][field]['display'] in specs[('BC-BAR-WAVE','BASE',label)][4] and specs[('BC-BAR-WAVE','BASE',label)][11].startswith('BARWAVE-')
for key in [('BC-MCP-4','BASE'),('BC-PORTMAN-1','BASE')]:checks['reference_disposition:'+str(key)]='Reference disposition' in reviews[key][5] and 'no additional sale unit' in reviews[key][4]
oldgaps={x['values'][0]:x for x in old['additional_photograph_gaps']};gaps={x['values'][0]:x for x in cur['additional_photograph_gaps']};checks['164_supplemental_unique_photo_rows_and272total']=len(gaps)==len(cur['additional_photograph_gaps'])==164 and cur['baseline_photo_gaps']==108
changedgaps={x.get('photo_gap_id') or (x['component_id']+'|BASE' if x['size_finish_variant_id']=='BASE' else 'SOURCE-G310003' if x['review_scope']=='WHOLE_SOURCE' else x['size_finish_variant_id']) for _,x in scopes}|{'BC-BAR-WAVE|BASE'}
for key,x in oldgaps.items():
 if key not in changedgaps:checks['prior_photo_gap_unchanged:'+key]=gaps[key]==x
checks['single_Soundwave_and_root_VerdigrisRust_gap_not_duplicated']=sum(x['values'][0]=='SOURCE-G310003' for x in cur['additional_photograph_gaps'])==1 and sum(x['values'][0]=='MCP4-VERDIGRIS-RUST' for x in cur['additional_photograph_gaps'])==1
checks['all_group_reference_records_unchanged']=old['groups']==cur['groups']
oldoffers={x['offer_ref']:x for x in old['platform_updates']};newoffers={x['offer_ref']:x for x in cur['platform_updates']};baseoffers={x['offer_ref']:x for x in read(HERE/'snapshot/model.json')['platform_records']}
checks['all_source_offer_counts_and_existing_photo_binding_statuses_retained']=old['platform_source_counts']==cur['platform_source_counts']=={'Squarespace only':43,'Squarespace + Shopify':37,'Shopify only':1} and set(oldoffers)<=set(newoffers) and all({k:v for k,v in x.items() if k!='image_path'}=={k:v for k,v in oldoffers.get(offer,baseoffers[offer]).items() if k!='image_path'} for offer,x in newoffers.items())
# Every newly normalised source path is tied to a same-day native head.
heads={}
for b in range(92,97):
 for x in read(ROOT/f'components/reviews/parallel-import-2026-10-19-batch{b}/current-reference-check.json')['metadata']:
  z=x[x['metadata_type']];heads[z['id']]=z
for name in ['CURRENT_METADATA.json','CONTEXT_CURRENT_METADATA.json']:
 for x in read(ROOT/'components/reviews/root-remaining-normalization-2026-10-20'/name)['metadata']:
  z=x[x['metadata_type']];heads[z['id']]=z
oldassets={x['id']:x for x in old['asset_updates']};changedassets=[]
for a in cur['asset_updates']:
 if a!=oldassets.get(a['id']):
  checks['new_path_native_head:'+a['id']]=a['id'] in heads and a['path']==heads[a['id']]['path_display']
  changedassets.append(a['id'])
checks['policy_records_unchanged_not_replayed']=all(old[k]==cur[k] for k in ['working_specification_acceptance_policy','global_fixing_choice_policy','global_approximate_weight_policy','physical_manufacture_review_policy','weight_policy_counts'])
checks['Azure_net_estimate_not_shipping_mass']=all(x in specs[('BC-AZURE','AZURE-BLUE-WHITE','Weight')][4] for x in ['7 kg net','4–10 kg','15 kg','shipping'])
checks['source_ID_model_and_baseline_immutable']=sha(ROOT/'components/evidence/component_register.json')=='ba65d17e6182ba6b89f30400d2f0236bc22a1478c29fb39be4d362a48d24fb61' and sha(cur['previous_workbook'])=='02532ec7664b39caa7b62755c8a45748d937045e801ce7fcd985a859faf62f6f'
failures=[k for k,v in checks.items() if not v]
out=dict(status='PASS' if not failures else 'FAIL',checked_utc=datetime.now(timezone.utc).isoformat(),check_count=len(checks),checks={k:'PASS' if v else 'FAIL' for k,v in checks.items()},baseline_workbook_sha256=BASE,leased_working_scopes=121,existing_display_recovery=1,reference_dispositions=2,changed_source_path_IDs=changedassets,raw_physical_and_sale_counts_unchanged=True,final_individual_count=None,all_actual_specifications_complete=False)
(HERE/'view-scope-readback-batch97.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert not failures,failures[:30]
print(json.dumps(dict(status='PASS',checks=len(checks),new_working_scopes=121,supplemental_photo_rows=164,unchanged_group_records=22,current_native_path_normalizations=len(changedassets))))
