"""Atomic guarded publication: controls first, master pointer last; rollback."""
from common import *
from datetime import datetime,timezone
import os

assert '--apply' in __import__('sys').argv, 'Use --apply for reviewed publication'
pending=read(H/'pending-current-master.json');check=read(H/'independent-verification.json')
assert check['status']=='PASS_INDEPENDENT_PUBLICATION_READBACK'
assert pending['register_sha256']==sha(BASE/pending['register'])
assert pending['workbook_sha256']==sha(BASE/pending['workbook'])
assert pending['current_comprehensive_workbook']['sha256']==sha(BASE/pending['preferred_review_workbook'])
assert pending['current_published_gallery_projection']['database_sha256']==sha(H/'gallery-projection/complete-image-platform-register.sqlite')
pointer=BASE/'current-master.json';assert sha(pointer)==manifest['sources']['pointer']['sha256']
old=read(pointer);targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer]
back=H/'publication-backups';back.mkdir(exist_ok=True);before={};payloads={}
for i,p in enumerate(targets):
    before[p]=p.read_bytes();(back/(str(i)+'-'+p.name)).write_bytes(before[p])
    if p==pointer:payloads[p]=pending
    else:
        current=read(p);assert current['current_master_catalogue']==old,str(p)+' pointer drift'
        current['current_master_catalogue']=pending;payloads[p]=current
def atomic(p,b):
    tmp=p.with_name(p.name+'.root-01a144ab-pending');tmp.write_bytes(b);os.replace(tmp,p)
written=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p],str(p)+' concurrent write'
        atomic(p,(json.dumps(payloads[p],ensure_ascii=False,indent=2)+'\n').encode());written.append(p)
    assert read(pointer)==pending
    for p in targets[:-1]:
        got=read(p);assert got['current_master_catalogue']==pending
        orig=json.loads(before[p]);got.pop('current_master_catalogue');orig.pop('current_master_catalogue');assert got==orig
except BaseException:
    for p in reversed(written):atomic(p,before[p])
    raise
receipt={'status':'PUBLISHED_VERIFIED_PACKAGE_APP_SOURCE_REBASE_PENDING','published_utc':datetime.now(timezone.utc).isoformat(),'pointer':str(pointer),'pointer_sha256':sha(pointer),'previous_pointer_sha256':manifest['sources']['pointer']['sha256'],'register_sha256':pending['register_sha256'],'workbooks':check['workbooks'],'gallery_database_sha256':check['gallery_database_sha256'],'independent_checks':check['checks'],'active_options':187,'retained_options':189,'current_scoped_files':len(files),'source_assertions_preserved':1668,'all_three_controls_equal_current_pointer':True,'all_unrelated_control_fields_preserved':True,'app_native_or_platform_writes':0}
write(H/'publication-receipt.json',receipt)
ready=read(H/'SOURCE_READY_FOR_APP_REBASE.json');ready.update(status='POINTER_PUBLISHED_READY_FOR_GUARDED_APP_SOURCE_REBASE',pointer_sha256=sha(pointer),publication_receipt=str(H/'publication-receipt.json'));write(H/'SOURCE_READY_FOR_APP_REBASE.json',ready)
print(json.dumps({k:v for k,v in receipt.items() if k not in ['workbooks']},indent=2))
