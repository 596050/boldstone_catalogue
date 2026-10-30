"""Index completed source-photo reviews without changing catalogue product data."""
import copy,hashlib,html,json
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent;OUT=B/'outputs/source-photo-evidence-index-2026-10-24'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert not(H/'publication-receipt.json').exists()
assert sha(B/'current-master.json')=='2373ed2edd5bd9f6ad2f6e3fa16196ac4bcf169f158a2739ad0ff53225b65404'
old=read(B/'current-master.json');g=read(B/old['register']);options={x['product_id']:x for x in g['options']}
assets=read(B/old['current_asset_reference_map']['path']);OUT.mkdir(exist_ok=True)
specs=[
 ('Moon Crater2 and Dune Ripple2 finish comparisons',ROOT/'reports/source-photo-finish-review-20261024-root',['O008','O009'],['BSI-2E097B70CD7F','BSI-4536FDCA0DA9'],None,'Existing appearance associations supported; no physical or custom-build certification.'),
 ('Two unresolved Moon Crater source photographs',B/'components/parallel-reviews/o006-o007-source-photo-review-20261024-B',['O006','O007'],['BSI-46F6DB226213','BSI-EBD43DF0704F'],'7f40036e2122cd475c5ca18a2bbc0fe7b50baedf6176322377ebe976f1633cbd','O006 supports an appearance association; exact source-original bindings remain unresolved for both cases.'),
 ('Moon Crater4 Verdigris and Silver/Bronze sources',B/'components/parallel-reviews/mcp4-three-source-review-20261024-B',['O011','O003','O064'],['BSI-8298E205204F','BSI-1AF0A83FAA37'],'5f3660ae0d0503e60a8896b64b25a501636cd9efa568ae4eca7dd726ca32ec03','Nine saved source renditions correspond to six current photographs; source-original bytes, configurations and physical details are not certified.'),
 ('Dune Ripple Gold and Verdigris source comparisons',B/'components/parallel-reviews/o002-o004-source-photo-review-01a16dbc-20261024',['O002','O004'],['BSI-0922347CC6AE','BSI-59530C6155C2'],'2f273f727cdb58f188160aff148c480a929c77cd94f84dd8d01d62aae6088ff1','Existing associations retained. The historically named rear image is a face/side view and does not verify fitted hardware.'),
 ('Palm Form individual components and arrangements',ROOT/'reports/palm-form-component-review-20261024-root',['O027','O047','O053','O054','O055','O056'],['BSI-EC5966EA0C7A','BSI-CAB0D722062D','BSI-F61AE4921B6B'],None,'Five source-photo correspondences checked; three component records retain 18 qualified fields and their source depth/order differences.')]
packets=[];provider_files={}
for title,folder,refs,ids,expected,scope in specs:
 seal=folder/'sealed-handoff.json'
 if expected:assert sha(seal)==expected
 data=read(seal);files=data['files'];items=files.items()if isinstance(files,dict)else[(x['path'],x['sha256'])for x in files]
 for path,value in items:
  file=Path(path);file=file if file.is_absolute()else folder/file;expected_hash=value if isinstance(value,str)else value['sha256'];assert sha(file)==expected_hash,file;provider_files[str(file)]=expected_hash
 v=read(folder/'verification.json');assert v['status']=='PASS'
 if 'checks_total'in v:assert v['checks_passed']==v['checks_total']
 if 'total'in v:assert v['passed']==v['total']
 review=folder/'review.json';expected_hash=v.get('review_sha256',v.get('report_sha256'));assert not expected_hash or sha(review)==expected_hash
 for oid in ids:
  o=options[oid];assert oid in g['active_option_ids'];assert len(o['master_fields'])==6
  a=assets[o['file_id']];assert all(o[k]==a[k]for k in ['image_url','folder_url','folder_id'])
 packets.append({'title':title,'review':str(folder/'index.html'),'review_json':str(review),'review_sha256':sha(review),
  'seal':str(seal),'seal_sha256':sha(seal),'verification':str(folder/'verification.json'),'verification_sha256':sha(folder/'verification.json'),
  'offer_refs':refs,'option_ids':ids,'scope':scope})
 provider_files[str(seal)]=sha(seal)
ids=sorted({oid for x in packets for oid in x['option_ids']});refs=sorted({ref for x in packets for ref in x['offer_refs']},key=lambda x:int(x[1:]))
assert len(ids)==11 and len(refs)==15
components=[{**{k:options[oid][k]for k in ['product_id','name','file_id','folder_id','image_url','folder_url','canonical_component_id']},'master_fields':options[oid]['master_fields']}for oid in ids]
index={'status':'CURRENT_LINKED_SOURCE_PHOTO_REVIEW_EVIDENCE','recorded_utc':datetime.now(timezone.utc).isoformat(),
 'source_register_sha256':old['register_sha256'],'source_workbook_sha256':old['workbook_sha256'],'current_asset_map':old['current_asset_reference_map'],
 'review_packets':packets,'retained_source_offer_refs':refs,'existing_option_records':components,
 'counts':{'review_packets':5,'retained_source_offers':15,'existing_options':11,'full_qualified_working_fields':66,'new_platform_pairs':0,'new_physical_verifications':0,'new_product_records':0},
 'interpretation':'This index records photograph comparisons, retained source relationships and unresolved bindings. It covers 15 source offers and 11 existing catalogue options. It establishes no new platform pairs, product records or verified physical specifications.',
 'provider_files':provider_files}
write(H/'source-photo-review-index.json',index)
esc=lambda x:html.escape(str(x),quote=True)
cards=''.join('<article><h2><a href="'+esc(x['review'])+'">'+esc(x['title'])+'</a></h2><p>'+esc(x['scope'])+'</p><p>Retained source references: '+esc(', '.join(x['offer_refs']))+'</p></article>'for x in packets)
rows=''
for o in components:
 fields=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'<p class="qualification">'+esc(v['state'])+'</p></td></tr>'for k,v in o['master_fields'].items())
 rows+='<details id="'+esc(o['product_id'])+'"><summary>'+esc(o['name'])+'</summary><p><a href="'+esc(o['image_url'])+'">Dropbox image</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a></p><p><small>'+esc(o['file_id'])+' / '+esc(o['folder_id'])+'</small></p><table>'+fields+'</table></details>'
(OUT/'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Source photograph review evidence</title><style>body{font:17px Arial;line-height:1.5;max-width:1050px;margin:40px auto;padding:0 20px;color:#222}article,details{border-top:1px solid #bbb;padding:20px 0}summary{font-size:20px;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd}th{width:23%}.qualification{font-size:13px;color:#555}</style></head><body><h1>Source photograph review evidence</h1><p>Five completed reviews cover 15 retained source offers and 11 existing options. Open each review for compared photographs and their containing folders. Expand an option below for its six complete working specification fields.</p><p>'+esc(index['interpretation'])+'</p>'+cards+'<h2>Existing individual options</h2>'+rows+'</body></html>')
controls=[B/x for x in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']]
inputs={'pointer':B/'current-master.json','register':B/old['register'],'workbook':B/old['workbook'],
 'native_map':B/old['current_native_reference_map']['path'],'asset_map':B/old['current_asset_reference_map']['path'],
 'audit':Path(old['latest_image_coverage_audit']['path']),**{f'control_{i}':x for i,x in enumerate(controls)}}
(H/'inputs').mkdir(exist_ok=True);m={}
for key,path in inputs.items():
 snap=H/'inputs'/(key+'.before');snap.write_bytes(path.read_bytes());m[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m)
p=copy.deepcopy(old);p.update(recorded_utc=index['recorded_utc'],publication_receipt=str((H/'publication-receipt.json').relative_to(B)))
p['current_source_photo_review_index']={'path':str((H/'source-photo-review-index.json').relative_to(B)),'sha256':sha(H/'source-photo-review-index.json'),
 'review':str((OUT/'index.html').relative_to(B)),'review_sha256':sha(OUT/'index.html'),'counts':index['counts']}
p['latest_master_metadata_change']={'status':'COMPLETED_SOURCE_PHOTO_EVIDENCE_INDEXED_METADATA_ONLY','path':p['publication_receipt'],
 'preceding_publication_receipt':old['publication_receipt'],'catalogue_register_workbook_audit_and_native_asset_maps_unchanged':True}
write(H/'prepared-pointer.json',p);prepared={}
for i,dest in enumerate(controls):
 d=read(dest);assert d['current_master_catalogue']==old;d.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p),
  current_source_photo_review_index=copy.deepcopy(p['current_source_photo_review_index']),latest_master_metadata_change=copy.deepcopy(p['latest_master_metadata_change']))
 target=H/f'prepared-control-{i}.json';write(target,d);prepared[str(dest)]=str(target)
write(H/'prepared-control-paths.json',prepared)
assert all(sha(x['path'])==x['sha256']for x in m.values())
v={'status':'PASS','counts':index['counts'],'all_provider_seals_and_files_verified':True,'all66qualified_fields_match_current_register':True,
 'all11current_selected_image_folder_bindings_match_explicit_asset_map':True,'all_five_data_artifacts_unchanged':True}
write(H/'candidate-verification.json',v)
freeze=[Path(__file__),H/'publish_metadata.py',H/'source-photo-review-index.json',OUT/'index.html',H/'input-manifest.json',H/'prepared-pointer.json',H/'prepared-control-paths.json',H/'candidate-verification.json',*map(Path,prepared.values())]
write(H/'candidate-freeze.json',{'status':'FROZEN_SOURCE_PHOTO_EVIDENCE_INDEX_METADATA','recorded_utc':index['recorded_utc'],
 'candidate_register_sha256':old['register_sha256'],'candidate_workbook_sha256':old['workbook_sha256'],
 'frozen_artifacts':{str(x):sha(x)for x in freeze}})
print(json.dumps({**v,'candidate_freeze_sha256':sha(H/'candidate-freeze.json')}))
