"""Register the verified consolidated workbook without changing catalogue data."""
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile
from xml.etree import ElementTree as E

H=Path(__file__).resolve().parent;B=H.parents[2]
SRC=B/'components/parallel-reviews/all-source-workbook-20261025-B'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.comprehensive-tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
pointer=B/'current-master.json';assert sha(pointer)=='a508cb9a0b0257e57abacc1c6ed06999e3da947d219c5568d44e41db6a8a38e6'
old=read(pointer);seal_path=SRC/'sealed-handoff.json';assert sha(seal_path)=='4f9647ecb5bd9188871df4806fdad1e29c382e58d54a50f4be7ae8e57ed76865'
seal=read(seal_path);book=seal['deliverable']
for item in [book,*seal['receipts'],*seal['builders']]:assert sha(item['path'])==item['sha256'],item['path']
for item in read(SRC/'input-manifest.json')['inputs']:assert sha(item['path'])==item['sha256'],item['path']
assert seal['validation_checks_passed']==896989 and seal['new_identity_approvals']==seal['canonical_writes']==seal['platform_writes']==0
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(book['path'])as z:
    assert z.testzip()is None
    names=[x.get('name')for x in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',ns)]
    assert len(names)==21
    links=sum(len(E.fromstring(z.read(name)).findall('.//s:hyperlink',ns))for name in z.namelist()if name.startswith('xl/worksheets/sheet')and name.endswith('.xml'))
    assert links==43121
for key in ['register','workbook']:assert sha(B/old[key])==old[key+'_sha256']
controls=[B/'components/reviews/specification_review_progress.json',B/'components/checkpoint.json',B/'checkpoint.json']
for path in controls:assert read(path)['current_master_catalogue']==old
(H/'inputs').mkdir(exist_ok=True);snapshots={}
for path in [pointer,*controls]:
    dest=H/'inputs'/str(path.relative_to(B)).replace('/','__')
    if not dest.exists():shutil.copy2(path,dest)
    assert sha(path)==sha(dest);snapshots[path]=dest
ref={'status':'CONSOLIDATED_REVIEW_EXPORT_BOUND_TO_SPECIFIED_CANONICAL_AND_SOURCE_HASHES',
    'path':rel(book['path']),'sha256':book['sha256'],'sheets':21,'native_hyperlinks':43121,
    'canonical_register':old['register'],'canonical_register_sha256':old['register_sha256'],
    'canonical_data_workbook':old['workbook'],'canonical_data_workbook_sha256':old['workbook_sha256'],
    'source_seal':rel(seal_path),'source_seal_sha256':sha(seal_path),'counts':seal['counts'],'scope':seal['scope'],
    'source_association_scope':seal['source_associations'],'validation_checks_passed':seal['validation_checks_passed'],
    'baseline_pointer_sha256':sha(snapshots[pointer]),'baseline_pointer_snapshot':rel(snapshots[pointer]),
    'estimates_and_unresolved_records_retained':True,'new_identity_approvals':0,'new_physical_verifications':0,'platform_writes':0}
p=copy.deepcopy(old);p.update(recorded_utc=datetime.now(timezone.utc).isoformat(),current_comprehensive_workbook=ref,
    preferred_review_workbook=ref['path'],publication_receipt=rel(H/'publication-receipt.json'))
p['current_image_review_links']['all_catalogue_and_source_inventories_workbook']=ref['path']
p['latest_master_metadata_change']={'status':'COMPREHENSIVE_WORKBOOK_REFERENCE_ONLY','preceding_receipt':old['publication_receipt'],
    'catalogue_register_core_workbook_maps_and_fields_unchanged':True}
allowed={'recorded_utc','current_comprehensive_workbook','preferred_review_workbook','publication_receipt','current_image_review_links','latest_master_metadata_change'}
assert all(p[k]==old[k]for k in old if k not in allowed)
updates={}
for path in controls:
    value=read(path);value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p))
    for key in ['current_comprehensive_workbook','preferred_review_workbook','current_image_review_links','latest_master_metadata_change']:value[key]=copy.deepcopy(p[key])
    updates[path]=value
write(H/'prepared-pointer.json',p)
if '--apply'not in sys.argv:print('PASS_PREPARED_COMPREHENSIVE_EXPORT_REFERENCE_GUARDS');raise SystemExit(0)
try:
    for path,snapshot in snapshots.items():assert sha(path)==sha(snapshot),path
    for path,value in updates.items():write(path,value)
    write(pointer,p)
    for path in controls:assert read(path)['current_master_catalogue']==p
    assert read(pointer)==p and sha(book['path'])==book['sha256']
    for key in ['register','workbook']:assert sha(B/p[key])==p[key+'_sha256']
    receipt={'status':'PASS_COMPREHENSIVE_WORKBOOK_REFERENCE_REGISTERED','recorded_utc':p['recorded_utc'],
        'pointer_sha256':sha(pointer),'preceding_pointer_sha256':sha(snapshots[pointer]),
        'register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],
        'comprehensive_workbook':ref,'controls_sha256':{str(x):sha(x)for x in controls},
        'metadata_pointer_keys_changed':sorted(allowed),'new_data_or_native_or_platform_writes':0}
    write(H/'publication-receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items()if k not in ['comprehensive_workbook','controls_sha256']},indent=2))
except BaseException:
    for path,snapshot in snapshots.items():shutil.copy2(snapshot,path)
    raise
