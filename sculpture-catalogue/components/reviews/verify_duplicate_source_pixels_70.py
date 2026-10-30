"""Independently verify decoded pixels and unchanged owner/catalogue decisions."""
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime,timezone
from PIL import Image
from import_duplicate_source_pixels_70 import ROOT,HERE,PATHS,KEY,SOURCES,read,sha,write

old=read(HERE/'before-import.json');cur={key:read(path) for key,path in PATHS.items()};receipt=read(HERE/'import-receipt.json');proof=read(HERE/'duplicate-image-evidence.json');p,cp=cur['progress'],cur['walkthrough'];sources=copy.deepcopy(p['source_design_reviews']);verified=[]
for key in SOURCES:sources[key].pop('duplicate_source_image_evidence')
for item in proof['source_images']:
 with Image.open(ROOT/item['original_snapshot']) as im:
  pixels=im.convert('RGBA');verified.append((pixels.size,hashlib.sha256(pixels.tobytes()).hexdigest()))
checks={f'prior_user_{key}_unchanged':cur['user'][key]==value for key,value in old['user'].items()}
checks.update({
 'independent_RGBA_pixels_identical':verified[0]==verified[1] and verified[0][0]==(4096,4096) and verified[0][1]==proof['source_images'][0]['RGBA_pixel_sha256'],
 'different_current_stable_file_IDs_and_encoded_digests':len({x['file_id'] for x in proof['source_images']})==2 and len({x['folder_id'] for x in proof['source_images']})==2 and len({x['encoded_file_sha256'] for x in proof['source_images']})==2,
 'all_other_source_review_data_unchanged':sources==old['progress']['source_design_reviews'],
 'all_component_reviews_aliases_policies_and_counts_unchanged':all(p[key]==old['progress'][key] for key in ['reviews','catalogue_alias_reviews','catalogue_design_aliases','asset_assignment_overrides','catalogue_group_overrides','group_photo_review_policy','physical_manufacture_review_policy','current_component_photograph_gaps']),
 'both_owner_names_and_unaccepted_specs_preserved':all(p['source_design_reviews'][key]['canonical_source_name']==old['progress']['source_design_reviews'][key]['canonical_source_name'] and not p['source_design_reviews'][key]['owner_estimates_accepted'] and p['source_design_reviews'][key]['specifications']==old['progress']['source_design_reviews'][key]['specifications'] for key in SOURCES),
 'canonical_name_decision_pending_not_inferred':p['duplicate_source_image_reviews'][KEY]['canonical_name_decision_pending'] and not cp['pending_source_name_consolidations'][-1]['owner_answer_recorded'],
 'no_physical_count_or_design_equivalence_claim':not p['duplicate_source_image_reviews'][KEY]['physical_sculpture_or_stock_count_inferred'] and not proof['physical_component_equivalence_owner_confirmed'] and cur['component']['counts']==old['component']['counts'],
 'root_current_question_preserved':cp['current_question_id']=='MCP4-VERDIGRIS-RUST-FIXING-COUNT-01' and not cp['current_answer_recorded'] and all(cp[key]==value for key,value in old['walkthrough'].items() if key.startswith('current_')),
 'all_previous_owner_allocations_preserved':all(cp[key]==old['walkthrough'][key] for key in ['parallel_working_specification_reviews','parallel_source_reconciliation_reviews']),
 'root_component_mirror_exact':cur['root']['current_component_review']==cur['component'],
 'saved_shared_hashes_match':all(sha(PATHS[key])==value for key,value in receipt['shared_after_sha256'].items()),
 'frozen_sources_and_metadata_hashes_match':all(sha(ROOT/item['snapshot'])==item['sha256'] for item in read(HERE/'source-manifest.json')['files']),
 'protected_sources_and_workbook_unchanged':all(sha(path)==value for path,value in receipt['protected_sha256'].items()),
 'zero_new_owner_events_downloads_and_remote_writes':proof['new_owner_decisions']==proof['new_private_original_downloads']==proof['remote_mutations']==0,
})
guards={key:sha(path) for key,path in PATHS.items()};repeat=subprocess.run([sys.executable,str(ROOT/'components/reviews/import_duplicate_source_pixels_70.py')],capture_output=True,text=True,check=True);checks['idempotent_repeat_NO_WRITE']='ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE' in repeat.stdout and all(sha(PATHS[key])==value for key,value in guards.items())
assert all(checks.values()),[key for key,value in checks.items() if not value]
write(HERE/'independent-readback.json',{'status':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'check_count':len(checks),'checks':{key:'PASS' for key in checks},'import_receipt_sha256':sha(HERE/'import-receipt.json')})
event={'event_id':KEY+':EVIDENCE70','event':'EXACT_DECODED_IMAGE_DUPLICATE_EVIDENCE','batch':70,'owner_name_merge_inferred':False,'new_physical_counts':0,'readback_sha256':sha(HERE/'independent-readback.json')}
for path in [ROOT/'components/reviews/identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
 if not any(json.loads(line).get('event_id')==event['event_id'] for line in path.read_text().splitlines() if line.strip()):
  with path.open('a') as stream:stream.write(json.dumps(event)+'\n')
print(json.dumps({'batch':70,'status':'PASS','checks':len(checks),'readback_sha256':sha(HERE/'independent-readback.json')}))
