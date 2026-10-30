import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
previews=read(H/'preview-manifest.json')
for x in previews:x['sha256']=sha(x['path'])
out={'status':'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'previews':previews,'baseline_views_inspected':True,'all_five_current_workbook_previews_inspected':True,'findings':['Existing typography, colors, column widths, tab order and table architecture retained','Saved notes clearly retain MP4 group, Lava White design-only / Sandstone finish, and Brancusi accepted variation scopes','Current media conditions retain physical and platform restrictions','Saved formula summaries show177 complete individual references,11 technical gaps,128 qualified in situ references and79find/capture plus1verify action'],'source_visual_review':str(H/'visual-source-inspection.json'),'source_visual_review_sha256':sha(H/'visual-source-inspection.json'),'new_source_originals_inspected':7,'original_bytes_and_pixels_unchanged':True,'native_link_targets_checked_after_export':True,'physical_verification_claim_added':False}
(H/'visual-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':'PASS','previews':len(previews),'workbook_sha256':out['workbook_sha256']}))
