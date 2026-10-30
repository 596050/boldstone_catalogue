from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
from urllib.parse import quote
import json,hashlib
from PIL import Image
b=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
j=b/'components/parallel-reviews/remaining-photo-sources-and-bordered-import-20261023T200049Z'
r=Path('/Users/tprice/Documents/boldstone/reports/dropbox-moonphase-bordered-arrangement-review-2026-10-23')
native=b/'components/reconciliation/bordered-moonphase-master-refresh-2026-10-23'
now=datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,d):
 p=j/name;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');return {'path':str(p),'sha256':sha(p)}
def ref(p):return {'path':str(p),'sha256':sha(p)}
ptr=json.loads((b/'current-master.json').read_text());regp=b/ptr['register'];reg=json.loads(regp.read_text());audit=json.loads(Path(reg['latest_image_coverage_audit']['path']).read_text())
opts={x['product_id']:x for x in reg['options']};cov={x['option_id']:x for x in audit['coverage']}
receipts=json.loads((r/'download-receipts.json').read_text()); originals=[]
for x in receipts:
 p=Path(x['local_path']);data=p.read_bytes();h=hashlib.sha256(data).hexdigest();block=b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304));dh=hashlib.sha256(block).hexdigest()
 assert len(data)==x['size'] and h==x['sha256'] and dh==x['content_hash']
 with Image.open(p) as im:im.load();dims=list(im.size)
 assert dims==x['dimensions']
 originals.append({'file_id':x['id'],'local_original':str(p),'size':len(data),'sha256':h,'dropbox_content_hash':dh,'dimensions':dims,'decode':'PASS','source_receipt_matches':True})
md={}
for x in json.loads((native/'fresh-native-evidence.json').read_text())['records']:
 d=x['result']['structuredContent'];v=d.get('file') or d.get('folder');md[x['id']]=v
pair_id='id:cnqzTNngPVsAAAAAAAylEw';parent_id='id:cnqzTNngPVsAAAAAAAydLQ';pmd=md[pair_id];fmd=md[parent_id];src=next(x for x in receipts if x['id']==pair_id)
assert pmd['size']==src['size'] and Path(pmd['path_display']).parent.as_posix()==fmd['path_display']
ls=json.loads((native/'fresh-parent-lists.json').read_text())['records'];pls=next(x['result']['structuredContent'] for x in ls if x['path'].lower().endswith('/moonphase 1 and moonphase 2 with borders white'))
assert pls['has_more'] is False and len(pls['entries'])==7
assert next(x for x in pls['entries'] if x['file_id']==pair_id)['file']['size']==src['size']
assert 'id:cnqzTNngPVsAAAAAAAt4DQ' not in [x['file_id'] for x in pls['entries']]
authority=json.loads((b/'components/parallel-reviews/remaining-insitu-review-20261023T190856Z/review-authority.json').read_text())
authority['current_owner_completion']=ref(j/'owner-instruction-evidence.json')
authority['current_exact_owner_text']=json.loads((j/'owner-instruction-evidence.json').read_text())['owner_text']
authority['specific_scope']='Two source-qualified bordered Moonphase pair-display roles selected by reviewer under current completion instruction and retained labelled-display policy. No personal per-image approval or scene authenticity certification inferred.'
aref=save('bordered-display-authority.json',authority)
preflight={'schema':'boldstone.bordered-display-source-preflight.v1','recorded_utc':now,'status':'PASS_CURRENT_SOURCE_AND_CACHED_ORIGINAL_INTEGRITY','account_root_guards':ref(j/'fresh-scope-control.json'),'offline_fake_tests':ref(j/'offline-fake-tests.json'),'fresh_native_metadata':ref(native/'fresh-native-evidence.json'),'complete_parent_listings':ref(native/'fresh-parent-lists.json'),'review_seal':ref(r/'review-seal.json'),'source_download_receipts':ref(r/'download-receipts.json'),'originals':originals,'current_selected_file':pmd,'actual_parent':fmd,'actual_parent_list_count':7,'actual_parent_list_exhausted':True,'all_family_298_originals_rehashed':False,'whole_originals_visually_compared':['id:cnqzTNngPVsAAAAAAAylEw','id:cnqzTNngPVsAAAAAAAylYg','id:cnqzTNngPVsAAAAAAAylZA','id:cnqzTNngPVsAAAAAAAt4DQ'],'native_or_platform_writes':0,'scene_authenticity_verified':False}
pref=save('bordered-display-source-preflight.json',preflight)
folderurl='https://www.dropbox.com/home'+quote(fmd['path_display'],safe='/');imageurl=folderurl+'?preview='+quote(src['name'],safe='')
reference={'file_id':pair_id,'folder_id':parent_id,'name':src['name'],'path':'ns:202238505/'+pmd['path_display'],'path_display':pmd['path_display'],'rev':pmd['rev'],'size':src['size'],'content_hash':src['content_hash'],'sha256':src['sha256'],'dimensions':src['dimensions'],'image_url':imageurl,'folder_url':folderurl,'review_label':'Brick-wall pair display — bordered White','native_reference_status':'CURRENT_MASTER_FILE_AND_ACTUAL_PARENT_VERIFIED','whole_original_only':True,'scene_authenticity_verified':False,'physical_cast_or_size_certified':False}
decisions=[]
for num,(oid,pos,primary) in enumerate([('BSI-65A93033A200','LEFT','id:cnqzTNngPVsAAAAAAAylYg'),('BSI-4515726BBC18','RIGHT','id:cnqzTNngPVsAAAAAAAylZA')],1):
 o=opts[oid];c=cov[oid];assert c['in_situ']['status']=='No verified image' and o['file_id']==primary and c['series']['reference']['file_id']==pair_id
 basis=('Whole unchanged original001.png shows both complete bordered White panels against brickwork, including small supports below. '+('The LEFT panel matches MP1 primary001: its coil and outer sweep rise toward the upper right.' if pos=='LEFT' else 'The RIGHT panel matches MP2 primary001: its broad upper coil surrounds the lower central spiral.')+' This exact pair already serves as its accepted series reference. Select this whole photograph also as a labelled brick-wall pair display; its creation origin, genuine client/permanent installation, actual hardware and physical cast/size remain unverified.')
 decisions.append({'decision_id':'REVIEWER-BORDERED-MOONPHASE-DISPLAY-20261023-'+str(num).zfill(2),'product_id':oid,'name':o['name'],'role':'In situ','status_before':'No verified image','status_after':'Available','decision_kind':'OWNER_AUTHORIZED_REVIEWER_SELECTION_QUALIFIED_DISPLAY_ONLY','explicit_owner_image_role_approval':False,'reviewer_selected_reference':True,'owner_directed_editorial_completion':True,'personal_owner_Use_image_answer':None,'reference':deepcopy(reference),'basis':basis,'display_qualification':'Brick-wall pair display — bordered White; '+pos+' panel','member_position':pos,'source_qualified_visual_binding':True,'scene_authenticity_verified':False,'wider_room_or_garden_view_verified':False,'physical_cast_or_size_certified':False,'existing_individual_reference':deepcopy(c['individual']['reference']),'individual_primary_file_id_to_preserve':primary,'series_policy_to_preserve':deepcopy(c['series']),'series_policy_preservation_scope':'Existing Available role, stable file ID ylEw and actual parent ydLQ remain; root may refresh renamed pair-folder paths from sealed native overlay.','private_source_original_path':src['local_path'],'pixels_edited':False,'baseline_option_semantic_sha256':hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True).encode()).hexdigest()})
packet={'schema':'boldstone.reviewer-qualified-display-decisions.v1','recorded_utc':now,'status':'READY_FOR_INDEPENDENT_REVIEW_AND_ROOT_IMPORT','authority':aref,'source_preflight':pref,'baseline_register':{'path':str(regp),'sha256':sha(regp),'workbook_sha256':ptr['workbook_sha256']},'decisions':decisions,'expected_scope_delta':{'qualified_in_situ_roles_closed':2,'in_situ_gaps_before':26,'in_situ_gaps_after':24,'active_in_situ_gaps_before':18,'active_in_situ_gaps_after':16,'held_in_situ_gaps_unchanged':8,'series_gaps_unchanged':17,'current_options_unchanged':187,'required_picture_actions_after':42,'new_individual_roles':0,'new_series_roles':0,'personal_Use_image_answers_added':0,'physical_verifications_added':0},'preserve':['All188retained option records and187active records','All individual primary IDs, working specifications, selling details and series role identities','All8held/deferred context cases, retired Sandstone and legacy FrozenFish identity','Exact former role-review notes retained as dated history'],'allowed_concurrent_rebase':'Root owns one combined local import. Only queued sealed bordered native path refresh may be rebased; source role identities and individual primaries remain unchanged.','scope_exclusions':['Native Dropbox/platform mutations','Artificial/composited/cropped photography','Physical measurement, fixing load, stock or authentic installation certification'],'canonical_or_workbook_writes_by_this_lane':0,'native_or_platform_writes':0}
pack=save('bordered-display-reference-decisions.json',packet)
seal=save('bordered-display-packet-seal.json',{'schema':'boldstone.bordered-display-packet-seal.v1','recorded_utc':now,'status':'SEALED_READY_FOR_ROOT_REVIEW','files':[aref,pref,pack],'source_originals_verified':10,'selected_current_source_ids':[pair_id],'qualified_roles':2,'personal_owner_approvals_added':0,'physical_verifications_added':0,'native_or_platform_writes':0})
print(json.dumps({'packet':pack,'seal':seal,'expected_context_gaps':24,'series_gaps':17,'required_actions':42}))
