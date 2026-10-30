"""Prefer the sealed unified Wall sheet while retaining unchanged catalogue data."""
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
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.single-wall-tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
pointer=B/'current-master.json';assert sha(pointer)=='5aa45c6a598bfa123eeabd7ac2f1e64c087943d764a2eccaad0ab6d37d2398b9'
old=read(pointer);handoff=read(H/'handoff-reference.json');assert sha(handoff['path'])==handoff['sha256']
seal=read(handoff['path']);output=seal['output']
for item in [output,*seal['evidence']]:assert sha(item['path'])==item['sha256'],item['path']
assert seal['primary_sheet']=='Wall Sculptures'and sum(seal['row_types'].values())==seal['primary_rows']
assert seal['new_identity_approvals']==seal['canonical_spec_or_identity_writes']==seal['live_platform_writes']==0
assert seal['coverage']['catalogue_ids']==188 and seal['coverage']['current_file_ids']==6360 and seal['coverage']['folder_ids']==442
assert seal['coverage']['unassigned_file_ids']==625
baseline=seal['original_baseline_workbook']
assert sha(baseline['path'])==baseline['sha256']==old['current_comprehensive_workbook']['sha256']
assert sha(seal['previous_unified_workbook']['path'])==seal['previous_unified_workbook']['sha256']
assert seal['all_412_prior_rows_unchanged']and seal['all_prior_primary_links_unchanged']and seal['original_source_tabs_preserved']==21
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def inspect(path):
    with zipfile.ZipFile(path)as z:
        assert z.testzip()is None
        names=[x.get('name')for x in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',ns)]
        links=sum(len(E.fromstring(z.read(name)).findall('.//s:hyperlink',ns))for name in z.namelist()if name.startswith('xl/worksheets/sheet')and name.endswith('.xml'))
        return names,links
names,links=inspect(output['path']);before_names,_=inspect(baseline['path'])
assert len(names)==22 and names[0]=='Wall Sculptures'and names[1:]==before_names
assert links==seal['total_native_hyperlinks']
for key in ['register','workbook']:assert sha(B/old[key])==old[key+'_sha256']
controls=[B/'components/reviews/specification_review_progress.json',B/'components/checkpoint.json',B/'checkpoint.json']
for path in controls:assert read(path)['current_master_catalogue']==old
(H/'inputs').mkdir(exist_ok=True);snapshots={}
for path in [pointer,*controls]:
    dest=H/'inputs'/str(path.relative_to(B)).replace('/','__')
    if not dest.exists():shutil.copy2(path,dest)
    assert sha(path)==sha(dest);snapshots[path]=dest
notes=[
    'The primary sheet combines188 catalogue options with source/arrangement rows, photo groups and folders. Its413 rows are not a unique-sculpture count.',
    'The primary sheet includes80 reviewed Squarespace wall products plus one source whose wall scope is unconfirmed, covering224 native variants. It also covers38 Shopify wall products/variants.',
    'All208 Squarespace Physical-export products and136 Shopify-export products remain on the preserved source tabs; exclusions from the primary sheet are documented.',
    'All6360 current BOLDSTONE MASTER Wall files and442 folders are covered. The625 unassigned files remain in49 actual-parent photo groups; individual views do not establish additional unique sculptures.',
    seal['new_scope_review_row']['qualification'],
    'Existing source-SKU, variant, photograph, specification and context qualifications are retained. No new identity, mounting or physical verification is inferred.']
ref=copy.deepcopy(old['current_comprehensive_workbook'])
ref.update(status='CONSOLIDATED_EXPORT_WITH_PRIMARY_UNIFIED_WALL_REVIEW_SHEET',path=rel(output['path']),sha256=output['sha256'],sheets=22,
    primary_sheet='Wall Sculptures',primary_rows=seal['primary_rows'],row_types=seal['row_types'],wall_scoped_coverage=seal['coverage'],
    primary_sheet_scope_notes=notes,full_saved_source_product_scope=seal['source_scope'],
    native_hyperlinks=links,source_seal=rel(handoff['path']),source_seal_sha256=handoff['sha256'],
    unified_sheet_validation_checks_passed=seal['checks_passed'],previous_comprehensive_export=copy.deepcopy(old['current_comprehensive_workbook']),
    previous_unified_export=seal['previous_unified_workbook'],unconfirmed_wall_scope_record=seal['new_scope_review_row'],
    baseline_pointer_sha256=sha(snapshots[pointer]),baseline_pointer_snapshot=rel(snapshots[pointer]))
p=copy.deepcopy(old);p.update(recorded_utc=datetime.now(timezone.utc).isoformat(),current_comprehensive_workbook=ref,
    preferred_review_workbook=ref['path'],publication_receipt=rel(H/'publication-receipt.json'))
p['current_image_review_links'].update(all_catalogue_and_source_inventories_workbook=ref['path'],single_wall_sculptures_sheet_workbook=ref['path'])
p['latest_master_metadata_change']={'status':'PREFERRED_SINGLE_WALL_SHEET_EXPORT_REFERENCE_ONLY','preceding_receipt':old['publication_receipt'],
    'catalogue_register_core_workbook_maps_and_fields_unchanged':True}
allowed={'recorded_utc','current_comprehensive_workbook','preferred_review_workbook','publication_receipt','current_image_review_links','latest_master_metadata_change'}
assert all(p[k]==old[k]for k in old if k not in allowed)
updates={}
for path in controls:
    value=read(path);value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p))
    for key in ['current_comprehensive_workbook','preferred_review_workbook','current_image_review_links','latest_master_metadata_change']:value[key]=copy.deepcopy(p[key])
    updates[path]=value
write(H/'prepared-pointer.json',p)
if '--apply'not in sys.argv:print('PASS_PREPARED_SINGLE_WALL_SHEET_REFERENCE_GUARDS');raise SystemExit(0)
try:
    for path,snapshot in snapshots.items():assert sha(path)==sha(snapshot),path
    for path,value in updates.items():write(path,value)
    write(pointer,p)
    assert read(pointer)==p and sha(output['path'])==output['sha256']
    for path in controls:assert read(path)['current_master_catalogue']==p
    for key in ['register','workbook']:assert sha(B/p[key])==p[key+'_sha256']
    receipt={'status':'PASS_PREFERRED_SINGLE_WALL_SHEET_REFERENCE_REGISTERED','recorded_utc':p['recorded_utc'],
        'pointer_sha256':sha(pointer),'preceding_pointer_sha256':sha(snapshots[pointer]),
        'register_sha256':p['register_sha256'],'core_workbook_sha256':p['workbook_sha256'],
        'preferred_workbook':ref['path'],'preferred_workbook_sha256':ref['sha256'],'primary_sheet':'Wall Sculptures','primary_rows':ref['primary_rows'],
        'row_types':ref['row_types'],'total_native_hyperlinks':links,'controls_sha256':{str(x):sha(x)for x in controls},
        'metadata_pointer_keys_changed':sorted(allowed),'new_catalogue_identity_or_spec_changes':0,'platform_writes':0}
    write(H/'publication-receipt.json',receipt);print(json.dumps({k:v for k,v in receipt.items()if k!='controls_sha256'},indent=2))
except BaseException:
    for path,snapshot in snapshots.items():shutil.copy2(snapshot,path)
    raise
