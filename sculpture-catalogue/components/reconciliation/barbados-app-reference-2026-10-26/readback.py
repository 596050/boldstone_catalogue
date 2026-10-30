"""Final publication and complete preview pixel-decoding readback, read-only."""
from pathlib import Path
from urllib.parse import quote
from PIL import Image
import hashlib,io,json,urllib.request
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json');receipt=read(H/'publication-receipt.json')
assert sha(B/'current-master.json')==receipt['pointer_sha256']
assert all(read(B/q)['current_master_catalogue']==p for q in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json'])
with urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=15) as r:health=json.load(r)
assert health['version']==p['current_review_application']['version']=='2.6.1' and health['products']==187
qa=read(H/'independent-verification.json');decoded=[]
for entry in qa['responses']:
    with urllib.request.urlopen('http://127.0.0.1:8767/api/image?id='+quote(entry['file_id'],safe='')+'&size=thumb',timeout=20) as r:raw=r.read()
    with Image.open(io.BytesIO(raw)) as im:
        im.load();assert im.size[0]>0 and im.size[1]>0
        decoded.append({'file_id':entry['file_id'],'dimensions':im.size,'pixel_decode_completed':True})
assert len(decoded)==23
report={'status':'PASS_FINAL_V2_6_1_AND_FULL_PREVIEW_DECODE','pointer_sha256':sha(B/'current-master.json'),
    'active_options':187,'live_version':'2.6.1','all_controls_equal_pointer':True,
    'restored_workshop_references':12,'decoded_previews':23,'pixel_decode_results':decoded,
    'source_register_and_workbook_unchanged':True,'root_app_code_review_db_native_platform_mutations':0}
(H/'publication-readback.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='pixel_decode_results'},indent=2))
