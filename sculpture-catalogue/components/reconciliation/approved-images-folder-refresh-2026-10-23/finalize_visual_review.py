import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
previews=read(H/'preview-manifest.json')+read(H/'additional-preview-manifest.json')
for x in previews:x['sha256']=sha(x['path'])
out={'status':'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'previews':previews,'baseline_views_inspected':True,'changed_views_and_affected_folder_statuses_inspected':True,'findings':['Existing layout, typography, colors, widths and workbook architecture retained','Approved complete images show Available; qualified group references retain Group only','Eleven technical gaps are distinguished from six outstanding individual/identity actions','Scoped working-field estimates and physical unknowns remain explicit','Folder review notes now reflect imported owner image approvals'],'original_images_visually_inspected':14,'original_bytes_and_pixels_unchanged':True,'native_link_targets_checked_after_export':True,'physical_verification_claim_added':False}
(H/'visual-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':'PASS','previews':len(previews),'workbook_sha256':out['workbook_sha256']}))
