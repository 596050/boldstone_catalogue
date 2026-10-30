"""Record exact decoded-image equivalence while preserving both owner-kept names."""
import copy
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
from import_moonphase_silver_working_specs_62 import ROOT,PATHS,read,sha,rel,write

HERE=ROOT/'components/reviews/parallel-import-2026-10-19-batch70'
KEY='PIXEL-IDENTICAL-G158022-G160001'
SOURCES=['FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022','FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001']

def main():
 docs={key:read(path) for key,path in PATHS.items()}
 if (HERE/'import-receipt.json').exists():
  assert docs['progress']['duplicate_source_image_reviews'][KEY]['same_decoded_pixels_verified']
  print(json.dumps({'batch':70,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}));return
 before,guards=copy.deepcopy(docs),{key:sha(path) for key,path in PATHS.items()};u,p,cp,c=(docs[key] for key in ['user','progress','walkthrough','component'])
 assert docs['root']['current_component_review']==c and cp['last_parallel_import']['batch']==69
 heads={item[item['metadata_type']]['id']:item[item['metadata_type']] for item in read(HERE/'current-reference-check.json')['metadata']};rows=[];files=[]
 for key in SOURCES:
  node=p['source_design_reviews'][key];head,folder=heads[node['source_asset_id']],heads[node['source_folder_id']];original=ROOT/node['root_original_verification']['original_snapshot']
  assert head['rev']==node['source_file_revision'] and head['size']==node['source_file_bytes'] and head['path_display']==node['source_path_display'] and head['path_display'].rsplit('/',1)[0]==folder['path_display']
  assert sha(original)==node['root_original_verification']['sha256'] and original.stat().st_size==head['size'] and node['identity_confirmed'] and not node['owner_estimates_accepted']
  with Image.open(original) as im:
   im.load();rgb=hashlib.sha256(im.convert('RGB').tobytes()).hexdigest();rgba=hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest();size=list(im.size);mode=im.mode
  rows.append({'source_design_key':key,'owner_kept_source_name':node['canonical_source_name'],'file_id':head['id'],'folder_id':folder['id'],'file_revision':head['rev'],'file_bytes':head['size'],'file_path':head['path_display'],'folder_path':folder['path_display'],'image_url':node['image_link'],'folder_url':node['folder_link'],'original_snapshot':rel(original),'encoded_file_sha256':sha(original),'decoded_image_mode':mode,'pixel_size':size,'RGB_pixel_sha256':rgb,'RGBA_pixel_sha256':rgba,'new_original_download':False})
  files.append({'source':str(original),'snapshot':rel(original),'sha256':sha(original),'existing_immutable_snapshot_reused':True})
 assert rows[0]['pixel_size']==rows[1]['pixel_size']==[4096,4096] and rows[0]['RGB_pixel_sha256']==rows[1]['RGB_pixel_sha256']=='ab02288a3ce4bee76ad30c96c8e0f78ff1794177d9368fe55cc07162724435ee'
 assert rows[0]['RGBA_pixel_sha256']==rows[1]['RGBA_pixel_sha256'] and rows[0]['encoded_file_sha256']!=rows[1]['encoded_file_sha256']
 protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']};now=datetime.now(timezone.utc).isoformat();record=rel(HERE/'duplicate-image-evidence.json')
 proof={'schema':'boldstone.exact-decoded-image-equivalence.v1','recorded_utc':now,'relationship_key':KEY,'source_images':rows,'same_decoded_pixels_verified':True,'comparison':'RGBA and RGB decoded pixels including alpha compared by SHA256 at equal4096x4096 size; encoded PNG file digests differ.','evidence_scope':'Same picture pixels in two current Dropbox files. Does not establish two physical sculptures, casts, moulds or sale units, or authenticate the depicted scene.','both_prior_owner_name_decisions_retained':True,'canonical_name_decision_pending':True,'physical_component_equivalence_owner_confirmed':False,'unaccepted_source_proposals_differ':{'Offset':{'overall_cm':[55,105,4],'estimated_kg':20,'proposal_GBP':1700},'Rough':{'overall_cm':[50,95,4],'estimated_kg':17,'proposal_GBP':1400},'both_unaccepted':True},'new_owner_decisions':0,'new_private_original_downloads':0,'remote_mutations':0}
 p.setdefault('duplicate_source_image_reviews',{})[KEY]={'evidence_record':record,'source_design_keys':SOURCES,'same_decoded_pixels_verified':True,'RGBA_pixel_sha256':rows[0]['RGBA_pixel_sha256'],'canonical_name_decision_pending':True,'physical_sculpture_or_stock_count_inferred':False}
 for index,key in enumerate(SOURCES):
  node=p['source_design_reviews'][key];other=rows[1-index]
  node['duplicate_source_image_evidence']={'evidence_record':record,'same_decoded_pixels_verified':True,'other_source_design_key':other['source_design_key'],'other_owner_kept_name':other['owner_kept_source_name'],'other_file_id':other['file_id'],'other_folder_id':other['folder_id'],'canonical_name_decision_pending':True,'unaccepted_proposal_conflict_pending':True,'separate_physical_sculpture_inferred':False}
 pending={'relationship_key':KEY,'evidence_record':record,'source_design_keys':SOURCES,'owner_answer_recorded':False,'status':'BOTH_NAMES_KEPT;EXACT_PICTURE_DUPLICATE;CANONICAL_NAME_REVIEW_PENDING','priority':'After current active A owner card; no concurrent replacement question'}
 cp.setdefault('pending_source_name_consolidations',[]).append(pending);c['pending_source_name_consolidations']=copy.deepcopy(cp['pending_source_name_consolidations'])
 summary={'batch':70,'recorded_utc':now,'receipt':rel(HERE/'import-receipt.json'),'scope_kind':'EXACT_DUPLICATE_PICTURE_EVIDENCE_ONLY;OWNER_NAMES_RETAINED','new_owner_decisions':0,'new_specification_approvals':0,'new_registered_BC_component_ids':[],'new_physical_stock_count':0,'root_new_private_original_downloads':0,'remote_mutations':0,'workbook_export_pending':True}
 cp['parallel_import_queue'].append({'scope_kind':summary['scope_kind'],'receipt':record,'approval_imported':False,'evidence_imported':True,'import_receipt':summary['receipt'],'status':'EXACT_PICTURE_DUPLICATE_RECORDED;BOTH_NAMES_AND_UNACCEPTED_ESTIMATES_RETAINED;NAME_RECONCILIATION_PENDING'})
 c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
 for target,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:target[key]=copy.deepcopy(summary)
 for key,doc in docs.items():
  if key!='user':doc['updated_utc']=now
 docs['root']['current_component_review']=copy.deepcopy(c)
 assert u==before['user'] and p['reviews']==before['progress']['reviews'] and all(cp[key]==value for key,value in before['walkthrough'].items() if key.startswith('current_'))
 assert all(sha(PATHS[key])==value for key,value in guards.items()) and all(sha(path)==value for path,value in protected.items())
 files.append({'source':str(HERE/'current-reference-check.json'),'snapshot':rel(HERE/'current-reference-check.json'),'sha256':sha(HERE/'current-reference-check.json')})
 write(HERE/'before-import.json',before);write(HERE/'duplicate-image-evidence.json',proof);write(HERE/'source-manifest.json',{'files':files})
 for key,path in PATHS.items():
  if key!='user':write(path,docs[key])
 write(HERE/'import-receipt.json',{'status':'APPLIED;INDEPENDENT_READBACK_REQUIRED','summary':summary,'protected_sha256':protected,'shared_after_sha256':{key:sha(path) for key,path in PATHS.items()}})
 print(json.dumps({'batch':70,'status':'EXACT_PIXEL_DUPLICATE_EVIDENCE_APPLIED','same_RGBA_pixels':True,'both_names_retained':True,'canonical_name_pending':True,'new_owner_or_physical_counts':0}))

if __name__=='__main__':main()
