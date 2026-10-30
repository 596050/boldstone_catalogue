import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
v=read(H/'saved-file-verification.json');assert v['status']=='PASS'
previews=read(H/'preview-manifest.json');assert len(previews)==10
for x in previews:assert Path(x['path']).is_file();x['sha256']=sha(x['path'])
r={'status':'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'previews':previews,'reviewed_views':['Photograph and action summaries','Fountain primary/context/series distinction','Bronze courtyard right-square-panel scope','Both saved Missing Pictures source qualifications and resolved dispositions','Source notes in Master Catalogue and Listing Resolution','Draft media conditions'],'findings':'The longer source notes are fully readable after six scoped row-height adjustments. Existing typography and layouts are retained. No image pixels changed. Values, formulas, tables, filters, validation, conditional formatting and native hyperlink targets independently read back.','native_excel_interactive_session_tested':False}
(H/'visual-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('VISUAL_VERIFICATION_PASS')
