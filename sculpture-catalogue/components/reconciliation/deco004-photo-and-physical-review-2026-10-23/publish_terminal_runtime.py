"""Bind the verified read-only terminal filter fix without rewriting the workbook."""
import copy,hashlib,json,os,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.runtime-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
v=read(H/'terminal-runtime-verification.json');assert v['status']=='PASS'and sha(v['terminal_script'])==v['terminal_script_sha256']
r=read(H/'publication-receipt.json');p=read(B/'current-master.json');assert sha(B/'current-master.json')==r['current_master_pointer_sha256']
assert sha(B/p['workbook'])==r['workbook_sha256']and sha(B/p['register'])==r['register_sha256']
assert not(H/'publication-before-terminal-runtime-readback.json').exists()
shutil.copy2(H/'publication-receipt.json',H/'publication-before-terminal-runtime-readback.json')
write(H/'terminal-runtime-pointer.before.json',p)
new=copy.deepcopy(p);new['current_guided_image_review'].update(terminal_review_command_sha256=v['terminal_script_sha256'],terminal_runtime_verification=str((H/'terminal-runtime-verification.json').relative_to(B)),terminal_runtime_verification_sha256=sha(H/'terminal-runtime-verification.json'))
for control,digest in r['controls_sha256'].items():
 assert sha(control)==digest,control
 d=read(control);assert d['current_master_catalogue']==p;write(H/('runtime-before-'+Path(control).parent.name+'-'+Path(control).name),d);d['current_master_catalogue']=copy.deepcopy(new);d['current_guided_image_review']=copy.deepcopy(new['current_guided_image_review']);write(control,d)
write(B/'current-master.json',new)
assert read(B/'current-master.json')==new
for control in r['controls_sha256']:assert read(control)['current_master_catalogue']==new
r.update(current_master_pointer_sha256=sha(B/'current-master.json'),controls_sha256={path:sha(path)for path in r['controls_sha256']},terminal_runtime_followup={'status':'PASS_BOUND_TO_CURRENT_CONTROLS','verification':str(H/'terminal-runtime-verification.json'),'verification_sha256':sha(H/'terminal-runtime-verification.json'),'script_sha256':v['terminal_script_sha256'],'workbook_and_register_hashes_unchanged':True},last_readback_utc=datetime.now(timezone.utc).isoformat())
write(H/'publication-receipt.json',r)
out=B/'outputs'/H.name;state=read(out/'publication-state.json');state['publication_receipt_sha256']=sha(H/'publication-receipt.json');state['terminal_runtime_verified']=True;write(out/'publication-state.json',state)
print(json.dumps({'status':'PASS_RUNTIME_FIX_PUBLISHED_AND_READ_BACK','script_sha256':v['terminal_script_sha256'],'workbook_sha256':r['workbook_sha256'],'pointer_sha256':r['current_master_pointer_sha256']}))
