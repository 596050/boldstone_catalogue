"""Plan only the current identity labels, preserving native workbook structure."""
import copy
import importlib.util
import json
from pathlib import Path
import re

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
write = lambda p,x: Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
spec = importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
w = n.load(H/'inputs/master_workbook.before')
baseline = read(H/'inputs/master_register.before')
g = read(H/'canonical-master-register.json')
options = {o['product_id']:o for o in g['options']}
old_options = {o['product_id']:o for o in baseline['options']}
audit = read(H/'image-coverage-current.json')
plan = copy.deepcopy(read(B/'components/reconciliation/whole-gallery-navigation-master-2026-10-24/workbook-edit-plan.json'))
plan.update(cell_changes=[],formula_changes=[],value_blocks=[],formula_blocks=[],row_heights=[],table_appends=[],new_sheets=[],native_link_changes=[])
changes = {}
calculated = {}
def edit(sheet,cell,value):
    before = w['values'][sheet].get(cell,'')
    if before != value:
        target = calculated if cell in w['formulas'].get(sheet,{}) else changes
        target[(sheet,cell)] = {'sheet':sheet,'cell':cell,'before':before,'value':value}
def rows_for(sheet,oid):
    return sorted({re.search(r'\d+',cell)[0] for cell,value in w['values'][sheet].items() if value == oid},key=int)

legacy_id = 'BSI-04D6E8690F30'
legacy = options[legacy_id]
scope = 'Owner: FFL1 and FFS2 are the same relief design. Current face70×15cm. Historical source codes/options retained. No new mould, cast, primary-photo, exact platform variant or physical specification claim.'
edit('Master Catalogue','D91','BC-FFS-2')
edit('Master Catalogue','M91','Owner-confirmed existing FFS2 relief design; legacy source option retained')
edit('Master Catalogue','V91',scope)
for column,field in [('F','Weight'),('I','Individual price'),('J','Availability')]:
    edit('Master Catalogue',column+'91',legacy['master_fields'][field]['display'])
for row in rows_for('Specifications',legacy_id):
    field = w['values']['Specifications']['C'+row]
    edit('Specifications','D'+row,legacy['master_fields'][field]['display'])
    edit('Specifications','F'+row,legacy['master_fields'][field]['basis'])
edit('Components','D59',4)
edit('Components','E59','Owner confirms legacy FFL1 uses the existing FFS2 relief. Four retained option records, including the separate legacy source record; no extra design group or physical stock claim.')
edit('References and Gaps','C12','Owner-confirmed shared relief; separate source and physical limits retained')
edit('References and Gaps','D12',scope+' Working specifications retain their existing values and estimate labels. Historical100×22cm claims remain source evidence.')
edit('References and Gaps','E12','Retained option linked to BC-FFS-2; no extra component or working design group')
edit('Photo Coverage','C91','Shared design reference')
edit('Photo Coverage','D91','Shared design reference')
edit('Photo Coverage','L91',scope)
for row in rows_for('Missing Pictures',legacy_id):
    role = w['values']['Missing Pictures']['D'+row]
    edit('Missing Pictures','F'+row,'Identity relationship resolved as FFS2. Existing context deferral and optional-series scope remain unchanged.')
    edit('Missing Pictures','K'+row,scope)
    edit('Missing Pictures','L'+row,'No exact historical cast, size, physical specification or separate platform variant is certified by the design answer.')
    if role == 'Individual':
        edit('Missing Pictures','E'+row,'Resolved identity')
        edit('Missing Pictures','N'+row,'Resolved — owner same design')
edit('Identity Review','C10','Legacy FFL1 uses the FFS2 relief; current70×15cm face')
edit('Identity Review','D10','Same relief as Frozen Fish Two White (FFS2)')
edit('Identity Review','E10','Owner-confirmed same relief design')
edit('Identity Review','F10',scope)
edit('Identity Review','G10','Shared design image')
for row in rows_for('Selling Details',legacy_id):
    edit('Selling Details','C'+row,legacy['master_fields']['Individual price']['display'])
    edit('Selling Details','D'+row,legacy['master_fields']['Availability']['display'])
    edit('Selling Details','J'+row,legacy['master_fields']['Individual price']['basis'])
    edit('Selling Details','P'+row,'Design relationship resolved; exact platform offer and physical cast remain unverified')
for row in rows_for('Draft Listings',legacy_id):
    edit('Draft Listings','H'+row,'\n'.join(k+': '+v['display'] for k,v in legacy['master_fields'].items()))
    edit('Draft Listings','N'+row,scope+' No exact legacy native offer is assigned.')
    edit('Draft Listings','O'+row,'Check the existing FFS2-related offer/configuration before preparing any additional variant. Do not create a duplicate or transfer a SKU from design equivalence alone.')
    edit('Draft Listings','P'+row,'FFS2 photograph is a qualified shared-design reference. No separate legacy primary selected; context deferral unchanged.')
for sn,column in [('Listing Reconciliation','L'),('Listing Issues','D'),('Listing Resolution','Q')]:
    for row in rows_for(sn,legacy_id):
        edit(sn,column+row,'Owner confirms the FFL1/FFS2 relief relationship. Resolve exact native offer/configuration separately before any new variant; no repeat identity question or automatic duplicate listing.')

for oid,option in options.items():
    if not option.get('current_owner_pattern_resolution'):
        continue
    old = old_options[oid]
    pattern = option['owner_confirmed_pattern_name']
    for sn in w['values']:
        if sn in ['Source Specifications','Source Mapping','Fingerprint History']:
            continue
        for row in rows_for(sn,oid):
            for cell,value in w['values'][sn].items():
                if re.search(r'\d+',cell)[0] == row and value == old['name']:
                    edit(sn,cell,option['name'])
    row = rows_for('Master Catalogue',oid)[0]
    edit('Master Catalogue','M'+row,'Owner-confirmed pattern name; native variant remains unverified')
    edit('Master Catalogue','V'+row,'Owner confirms pattern name: '+pattern+'. Existing fields remain qualified estimates; native pattern/variant ID, size, lighting, physical construction and stock are not established by this naming answer.')
    for sn,col in [('Listing Reconciliation','L'),('Listing Issues','D'),('Listing Resolution','Q')]:
        for row in rows_for(sn,oid):
            edit(sn,col+row,option['current_listing_resolution']['next_action'])
    for row in rows_for('Draft Listings',oid):
        edit('Draft Listings','M'+row,'Owner pattern name confirmed; native variant/configuration unresolved')
        edit('Draft Listings','N'+row,'Owner-confirmed pattern name: '+pattern+'. No forced alias to one of the18 native swatches and no exact native variant assigned.')
        edit('Draft Listings','O'+row,'Check the exact existing native offer/configuration before any custom listing or publication. Do not repeat the answered naming question; the source snapshots do not prove live absence.')
    for case in audit['identity_review']:
        if oid not in case.get('related_option_ids',[]):
            continue
        for cell,value in w['values']['Identity Review'].items():
            if value == case['case_id']:
                row = re.search(r'\d+',cell)[0]
                edit('Identity Review','B'+row,option['name'])
                edit('Identity Review','D'+row,'Owner pattern name: '+pattern)
                edit('Identity Review','E'+row,'Owner-confirmed name; native variant mapping unverified')
                edit('Identity Review','F'+row,case['check'])

for link in plan['hyperlinks']:
    key = (link['sheet'],link['cell'])
    if key in changes:
        link['label'] = changes[key]['value']
plan['cell_changes'] = list(changes.values())
calculated[('Missing Pictures','D4')] = {'sheet':'Missing Pictures','cell':'D4','before':1,'value':0}
before_audit = read(H/'inputs/coverage.before')
resolved_wall_names = sum(old.get('state') == 'Unresolved' and current.get('state') != 'Unresolved'
    for old,current in zip(before_audit['identity_review'],audit['identity_review']))
calculated[('Identity Review','F4')] = {'sheet':'Identity Review','cell':'F4','before':3,'value':3-resolved_wall_names}
plan['calculated_value_changes'] = list(calculated.values())
plan['value_blocks'] = [{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]} for x in plan['cell_changes']]
plan['baseline_ranges'] = [['Master Catalogue','B90:D92','baseline-identity'],['Identity Review','B9:F10','baseline-question']]
plan['preview_ranges'] = [['Master Catalogue','B90:D92','current-identity'],['Identity Review','B9:F10','current-owner-answer']]
plan['supplemental_preview_ranges'] = []
for expected in plan['summary_expected']:
    if (expected['sheet'],expected['cell']) == ('Missing Pictures','D4'):
        expected['value'] = 0
for expected in calculated.values():
    if not any((x['sheet'],x['cell']) == (expected['sheet'],expected['cell']) for x in plan['summary_expected']):
        plan['summary_expected'].append({k:expected[k] for k in ['sheet','cell','value']})
write(H/'workbook-edit-plan.json',plan)
write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
print(json.dumps({'cell_changes':len(changes),'sheets':len(w['sheets']),'formulas':sum(map(len,w['formulas'].values())),
    'native_hyperlinks':len(plan['hyperlinks']),'native_target_changes':0},indent=2))
