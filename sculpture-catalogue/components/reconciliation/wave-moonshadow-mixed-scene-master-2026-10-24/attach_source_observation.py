"""Add the sealed current Squarespace source snapshot without changing existing mappings."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
D=B/'components/parallel-reviews/source-observation-proposal-20261024';assert sha(D/'sealed-handoff.json')=='67be8d665cc990f30b825b38e78bbe2007381cc09fef4680df93bd83759dd23e'
seal=read(D/'sealed-handoff.json')
for x in seal['files']+seal['reused_evidence']:assert sha(x['path'])==x['sha256']
proposal=read(D/'source-observation-proposal.json');key=proposal['proposed_key'];value=proposal['proposed_value'];g=read(H/'canonical-master-register.json');assert key not in g and key=='current_authenticated_squarespace_inventory_observation'
assert proposal['base_register']['sha256']=='2205546ab8502b4723d1eb9597c6da4104f8df18e7addcfd1ad9d9a4df328c16'
assert value['counts']['retained_squarespace_source_tuples']==80 and value['counts']['source_field_observations']==720 and value['counts']['historical_shopify_pairs']==37
assert all(value['counts'][k]==0 for k in ['new_catalogue_identity_matches','new_exact_individual_configuration_verifications','new_physical_verifications','current_shopify_products_verified','proposed_component_sku_assignments','native_action_payloads'])
assert value['owner_interpretation_precedence']['decision_id']==g['source_offer_edges'][27]['current_owner_depiction_correction']['decision_id']
raw=value['squarespace_source_clock']['raw_export'];assert sha(raw['path'])==raw['sha256']and Path(raw['path']).stat().st_size==raw['bytes']
g[key]=copy.deepcopy(value);g['latest_authenticated_source_observation_import']={'status':'CAPTURED_SOURCE_OBSERVATIONS_IMPORTED_WITHOUT_MAPPING_OR_AUTHORITY_UPGRADE','recorded_utc':datetime.now(timezone.utc).isoformat(),'sealed_proposal':str(D/'sealed-handoff.json'),'sealed_proposal_sha256':sha(D/'sealed-handoff.json'),'source_product_sku_tuples':80,'source_field_observations':720,'historical_shopify_pairs':37,'current_shopify_inventory_verified':False,'new_identity_or_physical_configuration_matches':0,'existing_working_values_changed':0,'native_or_platform_writes':0}
write(H/'canonical-master-register.json',g)
m=read(H/'input-manifest.json');e=read(H/'evidence-manifest.json')
for k,f in [('source_observation_seal',D/'sealed-handoff.json'),('source_observation_proposal',D/'source-observation-proposal.json'),('authenticated_export',Path(raw['path']))]:
 snap=H/'inputs'/(k+'.before');shutil.copy2(f,snap);m[k]={'path':str(f),'snapshot':str(snap),'sha256':sha(f)};e[str(f)]={'sha256':sha(f)}
write(H/'input-manifest.json',m);write(H/'evidence-manifest.json',e)
s=read(H/'import-summary.json');s['source_product_sku_observations_added']=80;s['historical_shopify_pair_observations_added']=37;s['new_identity_or_physical_configuration_matches']=0;write(H/'import-summary.json',s)
print('Added80 sealed source-ID/SKU observations and37 historical Shopify comparisons; all existing roots and mappings preserved')
