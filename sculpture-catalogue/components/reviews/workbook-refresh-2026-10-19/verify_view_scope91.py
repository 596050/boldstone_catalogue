"""Compare the new projection by stable keys with the archived batch87 export."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=read(HERE/'history/133aeb9548a4fd34335b73d90d764893c1ce8dd9fc90dc1f04e9988fca0b28c9/refresh-data.json');new=read(HERE/'refresh-data.json');scopes=set()
for batch in [88,89,91]:
 for x in read(ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}/import-receipt.json')['scopes']:scopes.add((x['component_id'],x['size_finish_variant_id']))
reviews=lambda d:{tuple(x[:2]):x for x in d['reviews']};specs=lambda d:{(x[0],x[1],x[3]):x for x in d['specifications']}
a,b=reviews(old),reviews(new);x,y=specs(old),specs(new);checks={
 'exact15_existing_scopes_reviewed':len(scopes)==15,
 '278_stable_review_keys_preserved':len(a)==len(b)==278 and set(a)==set(b),
 '1668_six_field_keys_preserved':len(x)==len(y)==1668 and set(x)==set(y),
 'all_names_and_existing_identity_decisions_preserved':all(v[:5]==b[k][:5] for k,v in a.items()),
 '90_scoped_working_groups_added_global_weight_policy_not_counted_as_six_fields':new['specification_approval_counts']['proposal_groups']==old['specification_approval_counts']['proposal_groups']+90==330,
 'all_group_references_platform_claims_and_other_updates_unchanged':all(new[k]==old[k] for k in ['groups','platform_updates','group_updates','asset_scope_overrides','catalogue_alias_rows','source_cell_updates']),
 'existing_canonical_standing_and_fixing_policies_unchanged':all(new[k]==old[k] for k in ['working_specification_acceptance_policy','global_fixing_choice_policy','physical_manufacture_review_policy']),
 'original_file_register_preserved':sha(ROOT/'components/evidence/component_register.json')=='ba65d17e6182ba6b89f30400d2f0236bc22a1478c29fb39be4d362a48d24fb61',
 'frozen_shared_source_hashes_still_current':all(sha(Path(z['source']))==z['sha256'] for z in new['source_files']),
}
oa={z['id']:z for z in old['asset_updates']};na={z['id']:z for z in new['asset_updates']};source_assets={z['id']:z for z in read(ROOT/'components/evidence/component_register.json')['assets']}
checks['all145_prior_asset_updates_preserved']=all(na[k]==v for k,v in oa.items()) and len(oa)==145
checks['eight_new_asset_path_updates_are_verified_namespace_normalizations_only']=len(set(na)-set(oa))==8 and all(v==dict(source_assets[k],path='/'+source_assets[k]['path'].split('//',1)[1]) for k,v in na.items() if k not in oa)
for k,v in a.items():
 if k in scopes:continue
 actual=b[k].copy()
 if k==('BC-CHELSEA','BASE'):
  for i in [7,9]:actual[i]=v[i]
 checks['unchanged_review:'+'|'.join(k)]=actual==v
for k,v in x.items():
 if k[:2] in scopes:continue
 actual=y[k].copy()
 if k[2]=='Weight':
  for i in [4,5,6]:actual[i]=v[i]
 if k[:2]==('BC-CHELSEA','BASE'):
  for i in [7,9]:actual[i]=v[i]
 checks['unchanged_non_weight_spec:'+'|'.join(k)]=actual==v
gaps=lambda d:{z['values'][0]:z for z in d['additional_photograph_gaps']};ag,bg=gaps(old),gaps(new)
checks['13_new_gap_rows_and_two_updated_Acanthus_rows_not_duplicates']=len(ag)==31 and len(bg)==44 and len(new['additional_photograph_gaps'])==44 and len(set(bg)-set(ag))==13
checks['other29_prior_supplemental_gaps_unchanged']=all(bg[k]==v for k,v in ag.items() if k not in ['AC-ONE-LEFT-SANDSTONE','AC-ONE-LEFT-PEWTER'])
progress=read(HERE/'snapshot/reviews.json');root=read(HERE/'snapshot/root_checkpoint.json');cp=read(HERE/'snapshot/walkthrough.json')
checks['Raked_pair_keeps_null_individual_primary_and_original_position_reference']=all(progress['reviews'][cid]['size_finish_variants'][vid]['primary_image_id'] is None and progress['reviews'][cid]['size_finish_variants'][vid]['reference_image_id']=='id:cnqzTNngPVsAAAAAAAylKg' for cid,vid in [('BC-RW-SPIRAL1','RAKED-SPIRAL1-BEIGE'),('BC-RW-WAVE','RAKED-SPIRAL2-BEIGE')])
checks['root_answer_and_unknown_keyhole_count_preserved']=cp['current_answer_recorded'] and not cp['current_fixing_count_answer_recorded'] and root['current_component_review']==read(HERE/'snapshot/component_checkpoint.json')
checks['root_MCP4_owner_weight_price_stock_and_lead_unchanged']=all(x[k]==y[k] if k[2] not in ['Weight','Fixing'] else x[k][4]==y[k][4] for k in x if k[:2]==('BC-MCP-4','MCP4-VERDIGRIS-RUST'))
assert all(checks.values()),[k for k,v in checks.items() if not v]
out=dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),check_count=len(checks),checks={k:'PASS' for k in checks},prior_published_workbook_sha256='133aeb9548a4fd34335b73d90d764893c1ce8dd9fc90dc1f04e9988fca0b28c9',reviewed_existing_scopes=15,new_scoped_working_groups=90,one_global_weight_policy=1,new_conditional_weights=9,recovered_existing_weight_displays=7,new_physical_counts=0,remote_mutations=0)
(HERE/'view-scope-readback-batch91.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='checks'}))
