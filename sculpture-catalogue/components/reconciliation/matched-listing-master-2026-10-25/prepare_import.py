"""Stage30 labelled working proposals and the sealed188-option listing plan."""
import copy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil

H=Path(__file__).resolve().parent;B=H.parents[2]
SRC=B/'components/parallel-reviews/matched-listing-finalization-20261025-B'
PREV=B/'components/reconciliation/coral-depth-wording-master-2026-10-25'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'artifact-authoring-receipt.json').exists()
ref=read(H/'listing-package-reference.json');assert sha(ref['path'])==ref['sha256']
seal=read(ref['path'])
for item in seal['files']:assert sha(item['path'])==item['sha256'],item['path']
packet=read(SRC/'specification-completion-packet.json');assert sha(SRC/'specification-completion-packet.json')=='2985e81096f760205aa3ce96906c1abd4e6255f070f98e70c2ea8a16702a7585'
assert read(H/'scope-review.json')['status']=='PASS_ROOT_REVIEW_EXACT30_LABELLED_WORKING_PROPOSALS'
p=read(B/'current-master.json');assert sha(B/'current-master.json')=='f97a541015a6e4bf0a19bdde8a489a954944fd8ff74859a21b4c1b99721a4b6a'
paths={'pointer':B/'current-master.json','master_register':B/p['register'],'master_workbook':B/p['workbook'],
    'coverage':B/p['latest_image_coverage_audit']['audit'],'actual_input':B/p['current_specification_verification']['actual_physical_measurement_input'],
    'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','checkpoint':B/'checkpoint.json'}
(H/'inputs').mkdir(exist_ok=True);manifest={}
for key,path in paths.items():
    snap=H/'inputs'/(key+'.before')
    if not snap.exists():shutil.copy2(path,snap)
    assert sha(path)==sha(snap),key
    manifest[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',manifest)
g=read(paths['master_register']);before=copy.deepcopy(g);options={o['product_id']:o for o in g['options']};changes=packet['changes']
assert len(changes)==len({(r['product_id'],r['field'])for r in changes})==30
for row in changes:
    o=options[row['product_id']];assert o['name']==row['name']and o['master_fields'][row['field']]==row['before']
    assert row['after']['physical_verification']==0 and not row['physical_verification_added']
    o['master_fields'][row['field']]=copy.deepcopy(row['after'])
treatment_path=SRC/'listing-treatment-register.json';treatments=read(treatment_path);assert len(treatments['options'])==188
for row in treatments['options']:assert row['accepted_working_fields']==options[row['product_id']]['master_fields']
summary={'status':'PREPARED30_WORKING_SPECIFICATION_PROPOSALS_AND188_LISTING_TREATMENTS','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'packet':str(SRC/'specification-completion-packet.json'),'packet_sha256':sha(SRC/'specification-completion-packet.json'),
    'owner_instruction':{'path':str(SRC/'owner-request-provenance.json'),'sha256':sha(SRC/'owner-request-provenance.json')},
    'source_listing_package':ref,'base_material_proposals':27,'face_size_estimates':3,'changed_field_objects':30,
    'active_fields_unchanged':1098,'retained_fields_unchanged':1104,'active_options':188,'retained_options':189,
    'new_physical_measurements':0,'existing_depth_estimates_preserved':True,'source_associations_and_photographs_unchanged':True,'native_or_platform_writes':0}
g['latest_working_specification_completion']=summary
g['current_listing_treatment_plan']={'status':'LOCAL_WORKING_TREATMENT_FOR_ALL188_NOT_AN_EXACT_NATIVE_MATCH_CERTIFICATE',
    'register':str(treatment_path),'register_sha256':sha(treatment_path),'package':ref,'summary':read(SRC/'summary.json'),
    'existing_source_edges_unchanged':True,'native_execution_allowed':False,'exact_native_binding_exceptions':['BSI-04D6E8690F30','BSI-EBD43DF0704F']}
assert all(g[k]==before[k]for k in before if k!='options')
write(H/'canonical-master-register.json',g);write(H/'import-summary.json',summary)
shutil.copy2(paths['coverage'],H/'image-coverage-current.json')
shutil.copy2(SRC/'specification-completion-packet.json',H/'specification-completion-packet.json')
shutil.copy2(B/'components/reconciliation/depth-estimates-master-2026-10-25/depth-estimate-packet.json',H/'depth-estimate-packet.json')
spec=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
w=n.load(paths['master_workbook']);plan=read(PREV/'workbook-edit-plan.json');old_summary=copy.deepcopy(plan['summary_expected'])
plan.update(cell_changes=[],calculated_value_changes=[],value_blocks=[],formula_changes=[],formula_blocks=[],row_heights=[],table_appends=[],new_sheets=[],native_link_changes=[],actual_parent_cells=[])
authored={};calculated={}
def rows(sheet,oid):return sorted({re.search(r'\d+',cell)[0]for cell,value in w['values'][sheet].items()if value==oid},key=int)
def edit(sheet,cell,value):
    old_value=w['values'][sheet].get(cell,'')
    if old_value!=value:
        target=calculated if cell in w['formulas'][sheet]else authored
        target[(sheet,cell)]={'sheet':sheet,'cell':cell,'before':old_value,'value':value}
for change in changes:
    oid=change['product_id'];field=change['field'];after=change['after'];o=options[oid]
    mr=rows('Master Catalogue',oid);assert len(mr)==1
    edit('Master Catalogue',('E'if field=='Dimensions / depth'else'G')+mr[0],after['display'])
    sr=[r for r in rows('Specifications',oid)if w['values']['Specifications']['C'+r]==field];assert len(sr)==1
    for col,key in [('D','display'),('E','state'),('F','basis')]:edit('Specifications',col+sr[0],after[key])
    for dr in rows('Draft Listings',oid):edit('Draft Listings','H'+dr,'\n'.join(k+': '+v['display']for k,v in o['master_fields'].items()))
plan['cell_changes']=list(authored.values());plan['calculated_value_changes']=list(calculated.values())
for item in plan['hyperlinks']:
    if(item['sheet'],item['cell'])in authored:item['label']=authored[(item['sheet'],item['cell'])]['value']
plan['value_blocks']=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in authored.values()]
expected={(x['sheet'],x['cell']):{'sheet':x['sheet'],'cell':x['cell'],'value':w['values'][x['sheet']][x['cell']]}for x in old_summary}
for x in calculated.values():expected[(x['sheet'],x['cell'])]={k:x[k]for k in ['sheet','cell','value']}
plan['summary_expected']=list(expected.values());plan['baseline_ranges']=[];plan['preview_ranges']=[];plan['supplemental_preview_ranges']=[]
for oid,label in [('BSI-3C849B547D50','azure'),('BSI-65A93033A200','bordered-moonphase'),('BSI-2246CBC9C94E','lava-moon'),('BSI-48D13D8D7E67','gleneagles')]:
    row=rows('Master Catalogue',oid)[0]
    plan['baseline_ranges'].append(['Master Catalogue','B'+row+':G'+row,'baseline-'+label]);plan['preview_ranges'].append(['Master Catalogue','B'+row+':G'+row,'current-'+label])
heights={}
for x in authored.values():
    sn=x['sheet'];row=int(re.search(r'\d+',x['cell'])[0]);info=w['sheets'][sn];column=x['cell'].rstrip('0123456789');col=0
    for char in column:col=col*26+ord(char)-64
    width=next((float(c.get('width','13'))for c in info['root'].find(n.q('cols'))if int(c.get('min'))<=col<=int(c.get('max'))),40)
    needed=min(409.5,max(32,sum(max(1,math.ceil(len(t)/max(8,width*.85)))for t in str(x['value']).split('\n'))*12+12))
    element=next(r for r in info['root'].find(n.q('sheetData'))if int(r.get('r'))==row);current=float(element.get('ht','15'))
    if needed>current:heights[(sn,row)]=max(heights.get((sn,row),current),needed)
plan['row_heights']=[{'sheet':s,'row':r,'height':v}for(s,r),v in heights.items()]
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
assert len(calculated)==30
print(json.dumps({'register_sha256':sha(H/'canonical-master-register.json'),'changed_fields':30,'authored_cells':len(authored),'calculated_cells':30,'row_heights':len(heights)},indent=2))
