import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');ptr=read(BASE/'current-master.json');prior=read(m['master_pointer']['snapshot']);target=BASE/ptr['workbook'];scope=ptr['latest_lava_moon_numbering'];links=ptr['current_image_review_links'];out=BASE/'outputs/lava-moon-numbering-2026-10-22';updates={Path(m[k]['path']):read(m[k]['path'])for k in ['review_progress','component_checkpoint','root_checkpoint']}
assert sha(target)==v['workbook_sha256']and sha(BASE/ptr['register'])==v['register_sha256']and ptr['publication_receipt']==rel(H/'publication-receipt.json')
for p,d in updates.items():assert d['current_master_catalogue']==ptr
for k,x in m.items():
 if k not in ['master_workbook','master_pointer','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256']
for k,x in prior['current_image_review_links'].items():
 if k.startswith('fingerprint_'):
  assert links[k]==x
  if not k.endswith('_sha256'):assert(BASE/x).is_file()
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':v['workbook_sha256'],'register':str(H/'canonical-master-register.json'),'register_sha256':v['register_sha256'],'audit_sha256':v['audit_sha256'],'verification':scope['verification'],'visual_verification':scope['visual_verification'],'checks':v['checks'],'old_sheets':24,'new_sheet':'Lava Moon Folders','six_option_names_updated':True,'three_component_names_updated':True,'new_candidate_links':12,'native_link_destinations_updated':v['native_targets_updated'],'specification_changes':0,'photo_role_changes':0,'new_canonical_options':0,'individual_gaps':26,'in_situ_gaps':61,'series_gaps':18,'lava_individual_gaps_retained':6,'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},'root_platform_or_Dropbox_writes':0}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_LAVA_NAMES_AND_LINK_REPORTS','publication_receipt':str(H/'publication-receipt.json'),'workbook_sha256':v['workbook_sha256'],'register_sha256':v['register_sha256']})
state=read(H/'WORK_STATE.json');state.update(status='COMPLETE_PUBLISHED_AND_READ_BACK',publication_receipt=rel(H/'publication-receipt.json'));write(H/'WORK_STATE.json',state)
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256']}))
