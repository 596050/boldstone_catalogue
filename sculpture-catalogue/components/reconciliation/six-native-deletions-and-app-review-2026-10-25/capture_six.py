"""Extend the published five-file availability history by one confirmed deletion."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,sqlite3
from urllib.parse import quote
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
p=read(B/'current-master.json');assert sha(B/'current-master.json')=='8840bcc0389a0a37d85278b41f966a5d909cd59879ee3d77ca29278ab3bb76bb'
oldpath=B/p['current_native_availability']['path'];assert sha(oldpath)==p['current_native_availability']['sha256']
old=read(oldpath);g=read(B/p['register']);assert sha(B/p['register'])==p['register_sha256']
assets=read(B/p['current_asset_reference_map']['path']);fid='id:cnqzTNngPVsAAAAAAAt61Q';a=assets[fid]
spec=B.parent/'catalogue-review/reviews/specification-completion-20261025'
assert sha(spec/'sealed-handoff.json')=='60a2e5c6e5e9b608ff5378a579d47c3b05f4a7907913cc8436d982677bd54e0a'
state=read(spec/'before-live-state.json');job=next(r for r in state['deletion_jobs']if r['file_id']==fid)
payload=json.loads(job['payload']);result=json.loads(job['result'])
assert job['state']=='deleted' and result['verified_absent'] and result['delete_response_confirmed']
assert result['confirmed_file_id']==fid and payload['binding']['content_hash']==a['source_content_hash']and payload['binding']['bytes']==a['bytes']
batch=next(r for r in state['deletion_batches']if r['id']==payload['batch_id']);br=json.loads(batch['result'])
assert batch['state']=='deleted'and {'id':fid,'revision':payload['file']['revision']}in br['confirmed_files']
inspection=read(H/'native-inspection.json');entries=inspection['direct_children'];assert not entries['has_more']and not entries['cursor']
assert fid not in {r['file_id']for r in entries['entries']}
assert inspection['folder']['id']==a['folder_id']
assert next(r for r in inspection['metadata']if r['target']==fid)['isError']
current=next(r for r in inspection['metadata']if r.get('file',{}).get('id')=='id:cnqzTNngPVsAAAAAAAt_oA')
assert not current['isError']
assert not any(o.get('file_id')==fid or o.get('context_file_id')==fid for o in g['options'])
events=[{'id':r['id'],'at':r['at']}for r in state['events']if r['kind']=='deletion'and r['item_id']==fid]
native_event=max(r['id']for r in events);snapshot_event=max(r['id']for r in state['events'])
assert native_event==342 and snapshot_event==347
gal=Path(old['gallery_database']);c=sqlite3.connect('file:'+quote(str(gal))+'?mode=ro',uri=True)
assoc=[{'product_id':r[0],'association_rows':r[1]}for r in c.execute('SELECT product_id,COUNT(*) FROM associations WHERE file_id=? GROUP BY product_id',(fid,))];c.close()
newrow={'file_id':fid,'status':'OWNER_CONFIRMED_DELETED_NATIVE_ABSENCE_VERIFIED','name':a['name'],
    'historical_path':a['path'],'historical_image_url':a['image_url'],'folder_id':a['folder_id'],'folder_url':a['folder_url'],
    'revision_at_deletion':payload['file']['revision'],'bytes_at_deletion':payload['file']['bytes'],
    'content_hash_at_deletion':payload['file']['content_hash'],'operation_id':job['id'],'batch_id':payload['batch_id'],
    'reason':payload['reason'],'user_confirmation_utc':result['confirmation_at'],'deletion_readback_utc':result['checked_utc'],
    'independent_native_readback':{'file_id':fid,'state':'deleted','verified_absent':True,'checked_utc':inspection['recorded_utc'],
        'scope':'Exact-ID NOT_FOUND plus complete verified containing-folder listing; original user-confirmed API receipt retained.'},
    'audit_events':events,'source_master_example_option_ids':[],'source_master_context_option_ids':[],
    'same_folder_option_ids':['BSI-123AABD474C1'],'retained_association_impacts':assoc,
    'replacement_primary_selected':False,'historical_source_records_retained':True}
overlay=copy.deepcopy(old);overlay.update(status='SEALED_CUMULATIVE_SIX_NATIVE_DELETIONS',recorded_utc=datetime.now(timezone.utc).isoformat(),
    review_event_cutoff=snapshot_event,last_confirmed_native_event=native_event,baseline_pointer_sha256=sha(B/'current-master.json'),
    preceding_overlay={'path':str(oldpath),'sha256':sha(oldpath)},
    scope='Six exact owner-confirmed deletions included in app snapshot event347; last native deletion event342. This extends the first five-file review set to include an earlier Icarus deletion. Prior full inventory remains a retained snapshot; effective count subtracts these six only. No new master example, review-choice import, identity change or physical measurement.')
overlay['rows'].append(newrow);overlay['rows'].sort(key=lambda r:r['file_id'])
overlay['affected_folder_option_ids']=sorted(set(overlay['affected_folder_option_ids']+['BSI-123AABD474C1']))
overlay['remaining_verified_files'].append({'target':current['target'],'isError':False,'metadata_type':'file','metadata':current['file']})
overlay['verified_folder_listings'].append({'target':'ns:202238505//BOLDSTONE MASTER/Products/01 Wall Sculptures/Abstract Cave Paintings/Abstract Cave Paintings 1 White',**entries})
overlay['counts'].update(confirmed_deleted_native_files=6,affected_option_folders=3,
    effective_wall_files_after_this_overlay=6354,effective_wall_objects_after_this_overlay=6796)
overlay['source_evidence'].update({str(H/'native-inspection.json'):sha(H/'native-inspection.json'),str(spec/'before-live-state.json'):sha(spec/'before-live-state.json'),str(spec/'sealed-handoff.json'):sha(spec/'sealed-handoff.json')})
assert len(overlay['rows'])==6 and len({r['file_id']for r in overlay['rows']})==6
dump(H/'availability-overlay.json',overlay)
packet={'status':'READY_V4_SIX_FILE_AVAILABILITY_ONLY','overlay_path':str(H/'availability-overlay.json'),
    'overlay_sha256':sha(H/'availability-overlay.json'),'baseline_workbook':str(B/p['preferred_review_workbook']),
    'baseline_workbook_sha256':p['current_comprehensive_workbook']['sha256'],
    'output_workbook':str((B/p['preferred_review_workbook']).with_name('Boldstone_Wall_Sculptures_Unified_2026-10-25_v4.xlsx')),
    'review_event_cutoff':snapshot_event,'last_confirmed_native_event':native_event,'app_review_event_cutoff_separate':1830,
    'instructions':['Availability-only v4 from v3; preserve all22 source sheets/raw/specification/identity/numeric values and413primary rows.',
        'Rebuild existing Native Availability sheet for cumulative6deletions and4verified reference files. No additional sheet required.',
        'Qualify existing baseline6360 vs6354after six only; keep442folders, source capture counts, and old2Flower link redirects.',
        'Add gallery007deleted/master010retained notes only to Icarus row; no additional hyperlink target change or primary selection.',
        'Update only applicable cover/overview/guide cutoff/count text; supply exact before/after metadata delta and visual readback.',
        'No import of app1316fieldreviews or167nameformatting decisions into canonical/source/spec cells; those remain a separate reviewed overlay.',
        'No canonical, app, native or platform write. Further native changes remain outside this fixed cutoff.']}
assert sha(packet['baseline_workbook'])==packet['baseline_workbook_sha256']
dump(H/'workbook-cutoff-packet.json',packet)
print(json.dumps({'status':packet['status'],'overlay_sha256':packet['overlay_sha256'],'packet_sha256':sha(H/'workbook-cutoff-packet.json'),'counts':overlay['counts']},ensure_ascii=False,indent=2))
