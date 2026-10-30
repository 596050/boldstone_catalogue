from pathlib import Path
from datetime import datetime,timezone
import hashlib,json

W=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
PACKET=ROOT/'sculpture-catalogue/components/reconciliation/acanthus-native-availability-2026-10-25/workbook-cutoff-packet.json'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(PACKET);v=read(W/'validation.json');saved=read(W/'final-readback.json');visual=read(W/'visual-review.json')
assert v['sha256']==sha(p['output_workbook'])
assert v['status'].startswith('PASS_') and saved['status'].startswith('PASS_') and visual['status']=='PASS_VISUALLY_REVIEWED'
assert visual['workbook_sha256']==v['sha256']
for key,h in [('source_workbook','source_workbook_sha256'),('overlay_path','overlay_sha256'),('register_path','register_sha256')]:assert sha(p[key])==p[h]
evidence=[W/n for n in ['authoring-receipt.json','assembly-receipt.json','exact-baseline-delta.json','validation.json','final-readback.json','visual-review.json','formula-scan.ndjson','final-native-inspection.ndjson','build-v3.mjs','assemble-v3.py','verify-v3.py','seal-v3.py']]
evidence.extend(Path(x['path']) for x in saved['previews'])
out={'status':'SEALED_V3_READY_FOR_INDEPENDENT_PUBLISHER_REVIEW','recorded_utc':datetime.now(timezone.utc).isoformat(),'workbook':p['output_workbook'],'workbook_sha256':v['sha256'],'cutoff_packet':str(PACKET),'cutoff_packet_sha256':sha(PACKET),'overlay':p['overlay_path'],'overlay_sha256':p['overlay_sha256'],'baseline':p['source_workbook'],'baseline_sha256':p['source_workbook_sha256'],'review_event_cutoff':345,'sheets':23,'original_sheets_retained':22,'primary_wall_sculptures_rows':413,'metadata_cell_edits':9,'existing_hyperlink_redirects':2,'nonempty_baseline_cells_compared':v['nonempty_baseline_cells_compared'],'existing_hyperlinks_compared':v['existing_hyperlinks_compared'],'native_availability_deleted_files':5,'verified_surviving_files':3,'baseline_adjusted_file_count':6355,'whole_library_rescan':False,'canonical_publication_performed':False,'native_changes_performed':False,'app_or_review_database_changes_performed':False,'source_identity_specification_and_price_changes_performed':False,'exact_delta':{'path':str(W/'exact-baseline-delta.json'),'sha256':sha(W/'exact-baseline-delta.json')},'evidence':{str(x):sha(x) for x in evidence},'qualifications':['Five fixed-cutoff deletions only; raw source sheets remain historical captures.','Only Flower primary001is deleted; its old URL remains in the audit and current action opens the actual containing folder.','Flower003 and MoonWhite002/005 remain; no new master primary selection inferred.','The existing MoonWhite002primary and its clickable actions remain intact.','ISO source timestamps include a UTC: prefix to preserve exact source precision as text.','Native OOXML preservation adapter transfers Artifact-authored content and retains original native links, raw text timestamps, tables, styles and geometry.']}
(W/'sealed-handoff.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'status':out['status'],'workbook_sha256':out['workbook_sha256'],'handoff':str(W/'sealed-handoff.json'),'handoff_sha256':sha(W/'sealed-handoff.json'),'validation_sha256':sha(W/'validation.json'),'delta_sha256':out['exact_delta']['sha256']},indent=2))
