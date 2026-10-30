"""Stage exactly the owner's14 requested working depth estimates."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import posixpath
import re
import shutil
from xml.etree import ElementTree as E

H = Path(__file__).resolve().parent
B = H.parents[2]
SOURCE = B/'components/parallel-reviews/owner-depth-estimates-20261025T005003Z-B'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p,x: Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not (H/'artifact-authoring-receipt.json').exists()
seal = read(SOURCE/'sealed-depth-estimates.json')
assert sha(SOURCE/'sealed-depth-estimates.json') == 'c2bb1241f8c2ea985f632107bfa0c39ba2db5a7bc994bf9833427e593f42a4f1'
for path,digest in seal['files'].items():
    file = Path(path) if Path(path).is_absolute() else SOURCE/path
    assert sha(file) == digest,path
packet = read(SOURCE/'depth-estimate-packet.json')
for key in ['base_pointer','base_register','base_workbook','owner_instruction','audit']:
    assert sha(packet[key]['path']) == packet[key]['sha256'],key
p = read(B/'current-master.json')
actual = B/p['current_specification_verification']['actual_physical_measurement_input']
paths = {'pointer':B/'current-master.json','master_register':B/p['register'],'master_workbook':B/p['workbook'],
    'coverage':B/p['latest_image_coverage_audit']['audit'],'actual_input':actual,
    'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json',
    'checkpoint':B/'checkpoint.json'}
(H/'inputs').mkdir(exist_ok=True)
manifest = {}
for key,path in paths.items():
    snapshot = H/'inputs'/(key+'.before')
    if not snapshot.exists():
        shutil.copy2(path,snapshot)
    assert sha(path) == sha(snapshot),key
    manifest[key] = {'path':str(path),'snapshot':str(snapshot),'sha256':sha(path)}
write(H/'input-manifest.json',manifest)
g = read(paths['master_register'])
before = copy.deepcopy(g)
options = {o['product_id']:o for o in g['options']}
rows = packet['rows']
assert len(rows) == len({r['product_id'] for r in rows}) == 14
for row in rows:
    option = options[row['product_id']]
    assert option['name'] == row['name'] and option['master_fields'][row['field']] == row['before']
    assert row['field'] == 'Dimensions / depth' and row['after']['physical_verification'] == 0
    assert row['estimate']['physical_measurement'] is False and row['estimate']['individual_owner_numeric_confirmation'] is False
    option['master_fields']['Dimensions / depth'] = copy.deepcopy(row['after'])
summary = {'status':'PREPARED14_OWNER_AUTHORIZED_DEPTH_ESTIMATES','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'decision_id':packet['decision_id'],'packet':str(SOURCE/'depth-estimate-packet.json'),'packet_sha256':sha(SOURCE/'depth-estimate-packet.json'),
    'seal':str(SOURCE/'sealed-depth-estimates.json'),'seal_sha256':sha(SOURCE/'sealed-depth-estimates.json'),
    'owner_instruction':packet['owner_instruction'],'depth_definition':packet['depth_definition'],
    'option_ids':[r['product_id'] for r in rows],'depth_fields_added':14,'other_field_objects_unchanged':1120,
    'active_options':188,'retained_options':189,'active_fields':1128,'retained_fields':1134,
    'all188_have_working_depth':True,'new_physical_verifications':0,'unknown_face_sizes_retained':packet['expected_after']['face_size_gaps_remaining'],
    'no_weight_material_fixing_price_availability_identity_or_photo_changes':True,'native_or_platform_writes':0}
g['latest_owner_depth_estimate_import'] = summary
assert g['summary'] == before['summary'] and g['original_review_specification_assertions'] == before['original_review_specification_assertions']
write(H/'canonical-master-register.json',g)
write(H/'import-summary.json',summary)
write(H/'depth-estimate-packet.json',packet)
shutil.copy2(paths['coverage'],H/'image-coverage-current.json')

spec = importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
w = n.load(H/'inputs/master_workbook.before')
old_plan = read(B/'components/reconciliation/owner-identity-decisions-master-2026-10-25/workbook-edit-plan.json')
plan = copy.deepcopy(old_plan)
plan.update(cell_changes=[],calculated_value_changes=[],value_blocks=[],formula_changes=[],formula_blocks=[],row_heights=[],
    table_appends=[],new_sheets=[],native_link_changes=[],actual_parent_cells=[])
authored,calculated = {},{}
def edit(sheet,cell,value):
    old = w['values'][sheet].get(cell,'')
    if old != value:
        target = calculated if cell in w['formulas'].get(sheet,{}) else authored
        target[(sheet,cell)] = {'sheet':sheet,'cell':cell,'before':old,'value':value}
def matching_rows(sheet,oid):
    return sorted({re.search(r'\d+',cell)[0] for cell,value in w['values'][sheet].items() if value == oid},key=int)
for row in rows:
    oid = row['product_id']
    option = options[oid]
    master_row = matching_rows('Master Catalogue',oid)
    assert len(master_row) == 1
    edit('Master Catalogue','E'+master_row[0],row['after']['display'])
    spec_rows = [r for r in matching_rows('Specifications',oid) if w['values']['Specifications']['C'+r] == 'Dimensions / depth']
    assert len(spec_rows) == 1
    r = spec_rows[0]
    for col,key in [('D','display'),('E','state'),('F','basis')]:
        edit('Specifications',col+r,row['after'][key])
    for draft_row in matching_rows('Draft Listings',oid):
        edit('Draft Listings','H'+draft_row,'\n'.join(field+': '+value['display'] for field,value in option['master_fields'].items()))

for item in plan['hyperlinks']:
    if (item['sheet'],item['cell']) in authored:
        item['label'] = authored[(item['sheet'],item['cell'])]['value']
plan['cell_changes'] = list(authored.values())
plan['calculated_value_changes'] = list(calculated.values())
plan['value_blocks'] = [{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]} for x in plan['cell_changes']]
plan['summary_expected'] = [x for x in old_plan['summary_expected'] if (x['sheet'],x['cell']) not in
    {(x['sheet'],x['cell']) for x in old_plan.get('calculated_value_changes',[])}]
for old in old_plan.get('calculated_value_changes',[]):
    plan['summary_expected'].append({'sheet':old['sheet'],'cell':old['cell'],'value':w['values'][old['sheet']][old['cell']]})
for item in calculated.values():
    plan['summary_expected'].append({key:item[key] for key in ['sheet','cell','value']})
plan['baseline_ranges'] = []
plan['preview_ranges'] = []
plan['supplemental_preview_ranges'] = []
for oid,label in [('BSI-3C849B547D50','azure'),('BSI-4515726BBC18','bordered-moonphase'),('BSI-2246CBC9C94E','lava-moon')]:
    r = matching_rows('Master Catalogue',oid)[0]
    plan['baseline_ranges'].append(['Master Catalogue','B'+r+':E'+r,'baseline-'+label])
    plan['preview_ranges'].append(['Master Catalogue','B'+r+':E'+r,'current-'+label])

# Increase only rows whose new wrapped current text requires more room.
height_changes = {}
for (sheet,cell),item in authored.items():
    if sheet not in ['Specifications','Draft Listings']:
        continue
    row = int(re.search(r'\d+',cell)[0])
    info = w['sheets'][sheet]
    column = cell.rstrip('0123456789')
    colnum = 0
    for char in column:
        colnum = colnum*26+ord(char)-64
    width = next((float(x.get('width','13')) for x in info['root'].find(n.q('cols')) if int(x.get('min')) <= colnum <= int(x.get('max'))),40)
    lines = sum(max(1,math.ceil(len(text)/max(8,width*.85))) for text in str(item['value']).split('\n'))
    needed = min(409.5,max(32,lines*12+12))
    element = next(x for x in info['root'].find(n.q('sheetData')) if int(x.get('r')) == row)
    current = float(element.get('ht','15'))
    if needed > current:
        height_changes[(sheet,row)] = max(height_changes.get((sheet,row),current),needed)
plan['row_heights'] = [{'sheet':sheet,'row':row,'height':height} for (sheet,row),height in height_changes.items()]
write(H/'workbook-edit-plan.json',plan)
write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
print(json.dumps({'status':summary['status'],'depth_fields':14,'authored_cells':len(authored),'calculated_cells':len(calculated),
    'planned_row_height_increases':len(height_changes),'all_other_field_objects_unchanged':1120},indent=2))
