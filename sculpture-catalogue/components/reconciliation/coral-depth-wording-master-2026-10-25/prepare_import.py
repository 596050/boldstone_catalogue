"""Stage only the Coral acceptance-wording correction found by the188 audit."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil

H=Path(__file__).resolve().parent;B=H.parents[2]
PREV=B/'components/reconciliation/depth-estimates-master-2026-10-25'
AUDIT=B/'components/parallel-reviews/specification-double-check-after-depth-20261025T013835Z-B'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'artifact-authoring-receipt.json').exists()
assert sha(B/'current-master.json')=='b9baf40e95d1474e69e4bd43f5f204970a4eda7c930a86b456e5f62861288681'
assert sha(AUDIT/'sealed-audit.json')=='41be0668b88e77bb9291042a4f9e50aefed730912614e6aa583fcf50f0485932'
for path,digest in read(AUDIT/'sealed-audit.json')['files'].items():assert sha(path)==digest,path
p=read(B/'current-master.json')
paths={'pointer':B/'current-master.json','master_register':B/p['register'],'master_workbook':B/p['workbook'],
    'coverage':B/p['latest_image_coverage_audit']['audit'],'actual_input':B/p['current_specification_verification']['actual_physical_measurement_input'],
    'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','checkpoint':B/'checkpoint.json'}
(H/'inputs').mkdir(exist_ok=True)
manifest={}
for key,path in paths.items():
    target=H/'inputs'/(key+'.before')
    if not target.exists():shutil.copy2(path,target)
    assert sha(path)==sha(target),key
    manifest[key]={'path':str(path),'snapshot':str(target),'sha256':sha(path)}
write(H/'input-manifest.json',manifest)
g=read(paths['master_register']);before=copy.deepcopy(g);oid='BSI-0C2CB099DDEB'
option=next(o for o in g['options']if o['product_id']==oid)
old=copy.deepcopy(option['master_fields']['Dimensions / depth']);after=copy.deepcopy(old)
assert old['display'].count('unapproved guess')==1 and 'accepted' in old['state']
after['display']=old['display'].replace('unapproved guess','accepted working estimate, not physically verified')
after['basis']=old['basis'].replace('the earlier 6 cm (5–7 cm) proposal remains unchanged and unapproved.',
    'the earlier 6 cm (5–7 cm) proposal is retained as an accepted working estimate under the standing owner instruction; no individual numeric confirmation or physical measurement is recorded.')
assert after['basis']!=old['basis']
assert {k:v for k,v in after.items()if k not in ['display','basis']}=={k:v for k,v in old.items()if k not in ['display','basis']}
option['master_fields']['Dimensions / depth']=after
packet={'decision_id':'CORAL-ACCEPTED-DEPTH-WORDING-2026-10-25','scope':'Clerical alignment with the existing accepted standing-instruction state; no new numeric approval or physical measurement.',
    'audit':{'path':str(AUDIT/'sealed-audit.json'),'sha256':sha(AUDIT/'sealed-audit.json')},
    'rows':[{'product_id':oid,'name':option['name'],'field':'Dimensions / depth','before':old,'after':after,
        **{k:option[k]for k in ['file_id','folder_id','image_url','folder_url']}}]}
write(H/'wording-correction-packet.json',packet)
summary={'status':'PREPARED_ONE_CORAL_ACCEPTANCE_WORDING_CORRECTION','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'packet':str(H/'wording-correction-packet.json'),'packet_sha256':sha(H/'wording-correction-packet.json'),'audit':packet['audit'],
    'option_id':oid,'changed_field_objects':1,'other_field_objects_unchanged':1133,'numeric_value_changes':0,'new_physical_measurements':0,
    'image_identity_source_or_commercial_changes':0,'native_or_platform_writes':0}
g['latest_coral_depth_wording_correction']=summary
write(H/'canonical-master-register.json',g);write(H/'import-summary.json',summary)
shutil.copy2(paths['coverage'],H/'image-coverage-current.json')
shutil.copy2(PREV/'depth-estimate-packet.json',H/'depth-estimate-packet.json')
spec=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
w=n.load(paths['master_workbook']);plan=read(PREV/'workbook-edit-plan.json')
plan.update(cell_changes=[],calculated_value_changes=[],value_blocks=[],formula_changes=[],formula_blocks=[],row_heights=[],table_appends=[],new_sheets=[],native_link_changes=[],actual_parent_cells=[])
def rows(sheet):return sorted({re.search(r'\d+',cell)[0]for cell,value in w['values'][sheet].items()if value==oid},key=int)
def edit(sheet,cell,value):
    old_value=w['values'][sheet].get(cell,'')
    if old_value!=value:
        key='calculated_value_changes'if cell in w['formulas'][sheet]else'cell_changes'
        plan[key].append({'sheet':sheet,'cell':cell,'before':old_value,'value':value})
master_row=rows('Master Catalogue');assert len(master_row)==1
edit('Master Catalogue','E'+master_row[0],after['display'])
spec_row=[r for r in rows('Specifications')if w['values']['Specifications']['C'+r]=='Dimensions / depth'];assert len(spec_row)==1
edit('Specifications','D'+spec_row[0],after['display']);edit('Specifications','F'+spec_row[0],after['basis'])
for row in rows('Draft Listings'):edit('Draft Listings','H'+row,'\n'.join(k+': '+v['display']for k,v in option['master_fields'].items()))
for item in plan['hyperlinks']:
    match=next((x for x in plan['cell_changes']if(x['sheet'],x['cell'])==(item['sheet'],item['cell'])),None)
    if match:item['label']=match['value']
plan['value_blocks']=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in plan['cell_changes']]
plan['summary_expected']=[{**x,'value':w['values'][x['sheet']][x['cell']]}for x in plan['summary_expected']]
plan['summary_expected'] += [{k:x[k]for k in ['sheet','cell','value']}for x in plan['calculated_value_changes']]
plan['baseline_ranges']=[['Master Catalogue','B'+master_row[0]+':E'+master_row[0],'baseline-coral']]
plan['preview_ranges']=[['Master Catalogue','B'+master_row[0]+':E'+master_row[0],'current-coral']]
plan['supplemental_preview_ranges']=[]
heights={}
for x in plan['cell_changes']:
    sn=x['sheet'];row=int(re.search(r'\d+',x['cell'])[0]);info=w['sheets'][sn];column=x['cell'].rstrip('0123456789');col=0
    for char in column:col=col*26+ord(char)-64
    width=next((float(c.get('width','13'))for c in info['root'].find(n.q('cols'))if int(c.get('min'))<=col<=int(c.get('max'))),40)
    lines=sum(max(1,math.ceil(len(t)/max(8,width*.85)))for t in str(x['value']).split('\n'))
    needed=min(409.5,max(32,lines*12+12));element=next(r for r in info['root'].find(n.q('sheetData'))if int(r.get('r'))==row)
    current=float(element.get('ht','15'))
    if needed>current:heights[(sn,row)]=max(heights.get((sn,row),current),needed)
plan['row_heights']=[{'sheet':s,'row':r,'height':v}for(s,r),v in heights.items()]
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
assert len(plan['cell_changes'])==3 and len(plan['calculated_value_changes'])==1
print(json.dumps({'field_objects':1,'authored_cells':3,'calculated_cells':1,'row_heights':len(heights),'register_sha256':sha(H/'canonical-master-register.json')},indent=2))
