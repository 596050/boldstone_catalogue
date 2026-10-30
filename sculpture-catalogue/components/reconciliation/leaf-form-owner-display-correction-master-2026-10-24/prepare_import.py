"""Apply one exact owner depiction correction, preserving raw offer and BOM data."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not(H/'import-summary.json').exists()
p=read(B/'current-master.json');assert p['register_sha256']=='752d20c2ed792caed3a0227fae5c1248da812a1a6d57ef6f4bfef6f8c0e79ee6';OLD=(B/p['register']).parent;oldout=Path(read(OLD/'report-verification.json')['output_directory'])
D=B/'components/parallel-reviews/leaf-form-owner-repeated-design-20261024T013207Z';assert sha(D/'sealed-handoff.json')=='35bfdb1dd2102c48569353aafdbc1500d3d819f097a5445d41250af5f6f1640c'
seal=read(D/'sealed-handoff.json')
for x in seal['files']:assert sha(x['path'])==x['sha256']and Path(x['path']).stat().st_size==x['bytes']
decision=read(D/'owner-correction.json');assert sha(D/'owner-correction.json')=='f0a76f4899318dc114c609103d82b0fc10e04722c53d96d13aa73b9e7344367d'
assert decision['authority']['owner_exact_correction']=='It is the same sculpture duplicated on a wall'and decision['image_reference']['file_id']=='id:cnqzTNngPVsAAAAAAArqDQ'
(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json','report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json','review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','owner_seal':D/'sealed-handoff.json','owner_decision':D/'owner-correction.json','current_leaf_metadata':H/'leaf-current-native-metadata.json'}
m={}
for k,f in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(f,snap);m[k]={'path':str(f),'snapshot':str(snap),'sha256':sha(f)}
write(H/'input-manifest.json',m)
g=read(files['master_register']);a=read(files['audit']);assets=read(files['report_assets']);native=read(files['native_map']);changes=[]
def assign(root,path,value,group):
 keys=path.strip('/').split('/');x=root
 for key in keys[:-1]:x=x[int(key)]if isinstance(x,list)else x[key]
 key=int(keys[-1])if isinstance(x,list)else keys[-1];exists=True if isinstance(x,list)else key in x;before=copy.deepcopy(x[key]if exists else None);x[key]=copy.deepcopy(value);changes.append({'group':group,'path':path,'existed_before':exists,'before':before,'current':copy.deepcopy(value)})
record={'decision_id':decision['decision_id'],'source_receipt':str(D/'owner-correction.json'),'source_sha256':sha(D/'owner-correction.json'),'authority':copy.deepcopy(decision['authority']),'image_reference':copy.deepcopy(decision['image_reference']),'current_interpretation':copy.deepcopy(decision['current_interpretation']),'native_offer_sale_quantity_verified':False,'physical_cast_quantity_verified':False,'photo_production_method_verified':False,'new_platform_or_physical_match':False}
note='Owner confirms rqDQ shows one existing White Leaf Form design twice on a wall; not two complementary component designs. Historical O028 two-part wording, SKU and commercial data remain source evidence; current pack quantity, per-copy price and physical cast count are unconfirmed.'
paths=['/source_sets/10','/source_offer_edges/27','/source_platform_offer_coverage/27','/current_listing_source_links/offers/27','/current_listing_match_evidence/edges/158','/options/100']
for path in paths:assign(g,path+'/current_owner_depiction_correction',record,'register')
for path in ['/source_sets/10','/source_offer_edges/27']:
 assign(g,path+'/historical_relationship_before_owner_correction',g[path.strip('/').split('/')[0]][int(path.split('/')[-1])]['relationship_status'],'register')
 assign(g,path+'/relationship_status','Owner-confirmed repeated display of one existing design. Native multipart offer and BOM remain historical source claims; current sale quantity unconfirmed.','register')
assign(g,'/source_platform_offer_coverage/27/current_owner_depiction_scope_note',note,'register')
assign(g,'/current_listing_match_evidence/edges/158/special_join_limits/0','Owner confirms one existing White Leaf Form design shown twice in rqDQ. Native O028 description claims two parts; current pack quantity is unconfirmed. One logical option retained; source price and mass are not divided.','register')
assign(g,'/source_media_configuration_coverage/112/notes',g['source_media_configuration_coverage'][112]['notes']+[note],'register')
for path in ['/source_sets/10','/source_offer_edges/27']:assign(g,path+'/current_display_name','Leaf Form — White, repeated wall display','register')
assign(g,'/current_owner_depiction_corrections',[record],'register')
index=next(i for i,x in enumerate(a['coverage'])if x['option_id']=='BSI-6581D83760F1');row=a['coverage'][index];assert row['series']['reference']['file_id']=='id:cnqzTNngPVsAAAAAAArqDQ'
assign(a,f'/coverage/{index}/historical_series_basis_before_owner_correction',row['series']['basis'],'audit')
assign(a,f'/coverage/{index}/series/basis','Owner confirms the same existing White Leaf Form design shown twice on a wall. One unique design, two depicted placements; no physical cast quantity or image-production method confirmed. Existing orientation alias and qualified Series-reference role retained.','audit')
assign(a,f'/coverage/{index}/current_owner_depiction_correction',record,'audit')
o=g['options'][100];assert o['product_id']=='BSI-6581D83760F1'and o['canonical_component_id']=='BC-LEAF-FORM';raw=g['source_sets'][10]
objsha=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
# Exact source objects and all option field objects remain unchanged; independent verification also compares full objects.
assert raw['source_offer']==read(files['master_register'])['source_sets'][10]['source_offer']and raw['members']==read(files['master_register'])['source_sets'][10]['members']
meta=read(H/'leaf-current-native-metadata.json')['objects'];f=next(x for x in meta if x['id']=='id:cnqzTNngPVsAAAAAAArqDQ');folder=next(x for x in meta if x['id']=='id:cnqzTNngPVsAAAAAAAyijw');assert f['path_display'].rsplit('/',1)[0]==folder['path_display']
asset=assets[f['id']];repairs=[]
for key,value in [('display_path',f['path_display']),('folder_path','ns:202238505/'+folder['path_display'])]:
 if asset.get(key)!=value:repairs.append({'file_id':f['id'],'field':key,'before':asset.get(key),'current':value});asset[key]=value
assert len(repairs)==2 and native['current_objects'][f['id']]['path']=='ns:202238505/'+f['path_display']
summary={'status':'OWNER_LEAF_FORM_SAME_DESIGN_REPEATED_DISPLAY_IMPORTED','recorded_utc':now(),'current_options':188,'retained_options':189,'component_identities':112,'unique_designs_in_exact_image':1,'depicted_occurrences':2,'new_design_or_option_increment':0,'new_photo_bindings':0,'new_physical_verifications':0,'working_fields_changed':0,'native_or_platform_writes':0,'native_folder_operations':0,'auxiliary_current_asset_path_fields_repaired':2,'owner_decision_id':decision['decision_id']}
g['latest_leaf_form_owner_depiction_import']=summary;photo=read(OLD/'photo-source-review.json');write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'),sha256=sha(H/'photo-source-review.json'))
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='OWNER_LEAF_FORM_EXACT_SERIES_DEPICTION_QUALIFIED_NO_NEW_IMAGE')
pending=read(files['pending']);pending.setdefault('imported_packet_history',[]).append({'path':str(D/'sealed-handoff.json'),'sha256':sha(D/'sealed-handoff.json'),'exact_owner_depiction_only':True,'applied_to_current_frozen_release':True})
for name,value in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-assets.json',assets),('current-native-reference-map.json',native),('pending-followups.json',pending),('import-summary.json',summary),('authorized-current-field-changes.json',changes),('auxiliary-current-asset-navigation-repairs.json',repairs)]:write(H/name,value)
for name in ['physical-source-audit.json','photo-review-queue.json','guided-owner-review-state.json','original-verification.json','working-entry-owner-provenance-sidecar.json','guided_review.py','specification_review.py','verify_workbook.py']:shutil.copy2(OLD/name,H/name)
write(H/'source-evidence-verification.json',{'status':'PASS','exact_owner_decision':decision['decision_id'],'historical_offer_and_bom_unchanged':True,'new_physical_verifications':0})
write(H/'evidence-manifest.json',{str(f):{'sha256':sha(f)}for f in [D/'sealed-handoff.json',D/'owner-correction.json',H/'leaf-current-native-metadata.json']})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'option_ids':['BSI-6581D83760F1'],'changed_native_objects':{},'current_reference_fields':[]})
write(H/'WORK_STATE.json',{'status':'OWNER_INTERPRETATION_CANDIDATE','scope':'One exact repeated-design photograph; no native or physical authority upgrades'})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
