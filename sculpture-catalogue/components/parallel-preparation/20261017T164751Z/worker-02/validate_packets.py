from pathlib import Path
import json, hashlib
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parent
A=json.load(open(ROOT/'assignment.json'));P=json.load(open(ROOT/'packets.json'));C=json.load(open(ROOT.parent/'COORDINATION.json'))
required_entry={'component_id','proposed_name','family','identity_evidence','source_refs','primary_example','alternate_examples','context_images','series_images','specifications','source_conflicts','missing_evidence','platform_mapping','review_ready','handoff_notes'}
required_spec={'display','proposal','evidence_state','basis_refs','requires_owner_check','limits'}
spec_keys={'dimensions','weight','material_finish','fixing','individual_price','availability'}
viewed={}
for fn in ['image_index.json','extra_image_index.json','detail_image_index.json']:
 for r in json.load(open(ROOT/fn)):
  if r.get('file_id'):viewed[r['file_id']]=r['preview_path']
assets={a['id']:a for a in A['assets']}
assert P['worker_number']==2
assert len(P['entries'])==len(A['component_ids'])==34
assert [e['component_id'] for e in P['entries']]==A['component_ids']
assert len(set(e['component_id'] for e in P['entries']))==34
assert 'BC-CONCAVE' not in A['component_ids'] and 'BC-WALL-CIRCLE' not in A['component_ids']
assert hashlib.sha256((ROOT/'assignment.json').read_bytes()).hexdigest()==P['source_assignment_sha256']
image_references=0
for e in P['entries']:
 assert required_entry<=set(e),e['component_id']
 assert set(e['specifications'])==spec_keys
 for k,s in e['specifications'].items():
  assert required_spec<=set(s),(e['component_id'],k)
  assert s['requires_owner_check'] is True
  assert all(s.get(x) for x in ['display','proposal','evidence_state','limits'])
  assert isinstance(s['basis_refs'],list)
  if not s['basis_refs']:assert s['evidence_state'].startswith('MISSING_SOURCE')
 assert e['platform_mapping']['new_match_claimed'] is False
 for ir in [e['primary_example']]+e['alternate_examples']+e['context_images']+e['series_images']:
  assert {'file_id','folder_id','preview_path','shows_complete_single_component','selection_reason'}<=set(ir)
  if ir['file_id'] is None:
   assert ir['preview_path'] is None and ir['folder_id'] is None and ir['shows_complete_single_component'] is False
  else:
   image_references+=1
   assert ir['file_id'] in viewed,(e['component_id'],ir['file_id'],'not in viewed sheet index')
   assert ir['file_id'] in assets
   assert ir['folder_id']==assets[ir['file_id']]['folder_id']
   assert ir['preview_path']==assets[ir['file_id']]['thumb'] and Path(ir['preview_path']).is_file()
 for ir in e['context_images']+e['series_images']:assert not ir['shows_complete_single_component']
 assert e['review_ready']==bool(e['primary_example']['file_id'])
# Verify only the immutable sources relevant to this worker, not concurrently owned interactive files.
source_integrity=[]
for item in C['source_snapshots']:
 if Path(item['snapshot']).name=='component_register.json':
  data=Path(item['snapshot']).read_bytes(); actual=hashlib.sha256(data).hexdigest();assert actual==item['sha256']
  source_integrity.append({'path':item['snapshot'],'sha256':actual,'bytes':len(data),'result':'PASS_IMMUTABLE_SNAPSHOT_IDENTITY'})
assert P['counts']['all_six_specifications']==34
assert P['counts']['primary_complete_single_component']==23
assert P['counts']['without_isolated_primary']==11
assert P['counts']['live_dropbox_reads']==0 and P['counts']['remote_mutations']==0
result={'worker_number':2,'validated_utc':datetime.now(timezone.utc).isoformat(),'result':'PASS_LOCAL_PACKET_AUDIT','packet_path':str(ROOT/'packets.json'),'packet_sha256':hashlib.sha256((ROOT/'packets.json').read_bytes()).hexdigest(),'entries':34,'complete_single_object_primaries':23,'null_primaries':11,'specifications':204,'referenced_images_checked':image_references,'unique_viewed_asset_ids':len(viewed),'source_integrity':source_integrity,'checks':['exact assigned ID/order coverage','required entry/specification schema','all204 specifications require owner check','cached example IDs, parent-folder associations and existing preview paths','all selected examples occur in visually inspected sheet indexes','collection/context records never stand in as complete individual primaries','null primaries retain explicit missing-image evidence','review_ready limited to owner discussion','no new exact platform matches asserted','assignment hash identity','immutable component snapshot hash identity'],'manual_visual_decisions':['23 chosen primaries were inspected via tools.view_image; complete outer object boundaries visible','G244 MP1/MP5 individual assets were assessed against labelled maker diagrams despite mixed group role','Knightsbridge process/context views show a freestanding fountain block; no isolated product primary claimed','Mooncrater primary is a full basin view; no wall fixing assumed','LeafForm row34 and MSW row83 explicit mould-reuse statements control numbered-position interpretation'],'not_checked':['live Dropbox metadata/content/links; centrally owned','current platform/account state','physical mass/dimensions/material/fixings/stock','load ratings or water-contact performance'],'write_scope':'worker-02 only','shared_catalogue_writes':0,'remote_mutations':0}
(ROOT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['result','packet_sha256','entries','complete_single_object_primaries','null_primaries','specifications','referenced_images_checked','unique_viewed_asset_ids']},indent=2))
