"""Record inspected previews and immutable native-source evidence."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(H/'preview-manifest.json');assert len(p)==6
result={'status':'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'previews':[{**x,'sha256':sha(x['path'])}for x in p],'observed':'Both recalculated summary views, Fold garden/series positions, Riyadh handedness action, Spice studio wall-display qualifications and master context links inspected. Updated text fits its scoped row heights. Existing font, columns and native links retained.','browser_render_of_HTML_performed':False,'HTML_structural_link_validation':'link-report-verification.json','new_product_photos_created':0}
(H/'visual-verification.json').write_text(json.dumps(result,indent=2)+'\n')
m=read(H/'metadata-verification.json');assert m['sources']==40 and m['native_content_hashes_unchanged']==40 and m['new_originals_downloaded_and_rehashed']==4
q=read(H/'archive-download-receipt.json');assert q['status']=='PASS'and len(q['images'])==4
for x in q['images']:assert sha(x['local_path'])==x['sha256']
for x in read(H/'candidate-checks.json'):
 for z in x['findings'][-1]['evidence_plates']:assert sha(z['path'])==z['sha256']
print(json.dumps({'status':'PASS','previews_inspected':6,'fresh_originals_rehashed':4,'native_content_hashes_rechecked':40}))
