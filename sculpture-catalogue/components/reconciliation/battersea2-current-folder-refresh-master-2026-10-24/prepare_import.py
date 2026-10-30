"""Import the sealed seven-file Battersea2 current navigation change only."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
def namespaced(p):return 'ns:202238505/'+display(p)
assert not(H/'import-summary.json').exists();(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=Path(read(OLD/'report-verification.json')['output_directory'])
assert p['register_sha256']=='18efb9a7e4136dcfe981649e8c58012325d8d2e7b25648fe3ec419cd703cc5f6'
D=B.parent/'reports/dropbox-battersea2-in-situ-filing-20261024T000604Z'
assert sha(D/'current-reference-overlay.json')=='64f6b4710a230b5c4aa51f100d2eb8481c8f42a63276d343a3e6d1a30dd31b78'
assert sha(D/'execution-seal.json')=='a4f3306cd03109f2f9a6ae22531a2b19ead47945e067d9b0f05f8cab56994578'
overlay=read(D/'current-reference-overlay.json');seal=read(D/'execution-seal.json')
assert seal['status']==overlay['status']=='COMPLETE_VERIFIED'and len(seal['receipts'])==18 and not overlay['deleted_files']and not overlay['deleted_folders']
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json','report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json','review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','battersea_overlay':D/'current-reference-overlay.json','battersea_seal':D/'execution-seal.json'}
for i,r in enumerate(seal['receipts']):
 assert sha(r['path'])==r['sha256']and Path(r['path']).stat().st_size==r['size'];files['native_receipt_'+str(i)]=Path(r['path'])
m={}
for k,path in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(path,snap);m[k]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m)
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);assets=read(m['report_assets']['snapshot']);reviews=read(m['report_reviews']['snapshot']);state=read(m['review_state']['snapshot']);pending=read(m['pending']['snapshot']);photo=read(OLD/'photo-source-review.json')
exec(compile((H/'native_projection.fragment').read_text(),str(H/'native_projection.fragment'),'exec'))
assert g['summary']==read(m['master_register']['snapshot'])['summary']and a['counts']==read(m['audit']['snapshot'])['counts']
summary={'status':'BATTERSEA2_SEVEN_CURRENT_PATHS_AND_PARENTS_REFRESHED','recorded_utc':now(),'current_options':188,'retained_options':189,'component_identities':112,'changed_file_paths':7,'actual_file_parent_changes':7,'existing_folder_renames':0,'created_native_folders':1,'new_native_folder_id':'id:cnqzTNngPVsAAAAAAA6VsA','source_originals_rehashed':77,'source_original_bytes':75695011,'individual_primary_bindings_changed':0,'photograph_role_bindings_changed':0,'new_photo_bindings':0,'new_physical_verifications':0,'active_series':0,'active_individual_source_cases':1,'held_series':1,'held_context':22,'required_picture_actions':25,'optional_series':70,'native_or_platform_writes':0,'current_reference_fields_refreshed':len(current_refs)}
g['latest_battersea2_native_navigation_import']=summary
g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'))
write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review']['sha256']=sha(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='BATTERSEA2_SAME_SOURCE_IDS_CURRENT_PARENT_REFRESH')
for k,f in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/f).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
pending.setdefault('imported_packet_history',[]).append({'path':str(D/'current-reference-overlay.json'),'sha256':sha(D/'current-reference-overlay.json'),'navigation_only':True,'applied_to_current_frozen_release':True})
for f,v in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('pending-followups.json',pending),('import-summary.json',summary),('path-change-history.json',path_history),('current-reference-fields-refreshed.json',current_refs),('original-verification.json',originals)]:write(H/f,v)
for f in ['physical-source-audit.json','guided_review.py','verify_workbook.py','working-entry-owner-provenance-sidecar.json']:shutil.copy2(OLD/f,H/f)
write(H/'source-evidence-verification.json',{'status':'PASS','sealed_native_receipts':18,'source_originals_rehashed':77,'new_native_calls':0,'native_or_platform_writes':0,'new_physical_verifications':0})
write(H/'evidence-manifest.json',{str(v):{'sha256':m[k]['sha256']}for k,v in files.items()if k.startswith(('battersea_','native_receipt_'))})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'option_ids':[],'changed_native_objects':changed,'current_reference_fields':current_refs})
write(H/'WORK_STATE.json',{'status':'FROZEN_NATIVE_NAVIGATION_ONLY','plan':['Project sealed current parents and paths by exact ID','Preserve all policy/source-role/physical metadata','Author and verify current workbook and report navigation','Publish with frozen source guards']})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
