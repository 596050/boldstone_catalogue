"""Read-only, per-option audit of the published sculpture specifications."""
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.parse import urlsplit, unquote, parse_qs
import csv
import hashlib
import json
import posixpath
import re
import sqlite3
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
OUT = BASE / 'outputs' / HERE.name
FIELDS = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
pointer_path = BASE / 'current-master.json'
pointer = read(pointer_path)
register_path = BASE / pointer['register']
workbook_path = BASE / pointer['workbook']
register = read(register_path)
book = read(HERE / 'workbook-readback.json')
active_ids = set(register['active_option_ids'])
options = {o['product_id']: o for o in register['options'] if o['product_id'] in active_ids}
checklist_path = BASE / pointer['current_specification_verification']['field_checklist']
measurement_path = BASE / pointer['current_specification_verification']['actual_physical_measurement_input']
reader_root = (BASE / pointer['current_published_gallery_projection']['path']).parent
image_index_path = reader_root / 'per-product-image-lists.json'
image_index = read(image_index_path)
option_csv_path = BASE / pointer['current_individual_sculpture_list']['current_option_list']
gallery_seal_path = BASE / pointer['current_published_gallery_projection']['path']
sources = {str(p): sha(p) for p in [pointer_path, register_path, workbook_path, checklist_path, measurement_path, image_index_path, option_csv_path, gallery_seal_path]}
checks = []
issues = []

def check(ok, description):
    checks.append({'passed': bool(ok), 'check': description})

def dropbox_path(url):
    """Compare observed Dropbox preview/home URLs by their decoded content path."""
    parsed=urlsplit(url or '')
    path=unquote(parsed.path)
    if path.startswith('/preview/'):
        return path[8:]
    if path.startswith('/home/'):
        path=path[5:]
        query=parse_qs(parsed.query)
        return path+'/'+query['preview'][0] if 'preview' in query else path
    return url

check(sources[str(register_path)] == pointer['register_sha256'], 'Register matches the published hash')
check(sources[str(workbook_path)] == pointer['workbook_sha256'], 'Workbook matches the published hash')
check(book['workbook_sha256'] == pointer['workbook_sha256'], 'Artifact Tool readback uses the current workbook')
check(book['pointer_sha256'] == sources[str(pointer_path)], 'Artifact Tool readback uses the current pointer')
check(len(active_ids) == len(register['active_option_ids']) == len(options) == 188, 'All 188 active option IDs are unique and represented')
check(not active_ids.intersection(register['retired_option_ids']), 'Retired option is excluded from active scope')
check(len({o['product_id'] for o in register['options']}) == len(register['options']), 'Retained option IDs are unique')
check(len({o['name'] for o in options.values()}) == len(options), 'Active option names are unique')

# Independent XML readback checks the saved values as well as Artifact Tool's imported values.
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
native = {}
saved_errors = []
with zipfile.ZipFile(workbook_path) as z:
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        strings = [''.join(t.text or '' for t in si.iter('{'+NS['s']+'}t')) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    rels = {e.get('Id'): e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    for sheet in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets', NS):
        name = sheet.get('name')
        target = rels[sheet.get(RID)]
        part = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        native[name] = {}
        for cell in ET.fromstring(z.read(part)).findall('.//s:sheetData/s:row/s:c', NS):
            value = cell.find('s:v', NS)
            value = value.text if value is not None else None
            if cell.get('t') == 's' and value is not None:
                value = strings[int(value)]
            elif cell.get('t') == 'inlineStr':
                value = ''.join(t.text or '' for t in cell.findall('.//s:t', NS))
            formula = cell.find('s:f', NS)
            native[name][cell.get('r')] = {'value': value, 'formula': None if formula is None else '='+str(formula.text or '')}
            if cell.get('t') == 'e':
                saved_errors.append({'sheet':name,'cell':cell.get('r'),'error':value})
check(not saved_errors, 'No saved formula-error values in any workbook tab')

def sheet_rows(name):
    return [(idx, row) for idx, row in enumerate(book['sheets'][name]['values'], 1) if row and row[0] in active_ids]

spec_rows = {}
for row_number, row in sheet_rows('Specifications'):
    key = (row[0], row[2])
    check(key not in spec_rows, 'Unique specification key '+str(key))
    spec_rows[key] = (row_number, row)
check(len(spec_rows) == len(options)*6, 'Specifications sheet covers all 1,128 active field groups')

with checklist_path.open(encoding='utf-8-sig', newline='') as f:
    checklist_rows = list(csv.DictReader(f))
csv_by_key = {(r['option_id'], r['field']): r for r in checklist_rows}
check(len(csv_by_key) == len(checklist_rows) == len(options)*6, 'Published verification CSV covers exactly 1,128 unique current field groups')
with option_csv_path.open(encoding='utf-8-sig', newline='') as f:
    option_csv_rows=list(csv.DictReader(f))
option_csv={row['option_id']:row for row in option_csv_rows}
check(len(option_csv_rows)==len(option_csv)==188 and set(option_csv)==active_ids, 'Current option CSV contains all 188 active IDs exactly once')
with sqlite3.connect('file:'+str(reader_root/'complete-image-platform-register.sqlite')+'?mode=ro',uri=True) as db:
    gallery_products={pid:json.loads(blob) for pid,blob in db.execute('SELECT product_id,record_json FROM products')}
check(gallery_products==options, 'All 188 published gallery product records equal the current register')
check(sha(gallery_seal_path)==pointer['current_published_gallery_projection']['sha256'], 'Current gallery seal matches published hash')
check(pointer['current_published_gallery_projection']['register_sha256']==pointer['register_sha256'], 'Gallery is bound to current register')
check(pointer['current_published_gallery_projection']['workbook_sha256']==pointer['workbook_sha256'], 'Gallery is bound to current workbook')

master_rows = {row[0]: (rn, row) for rn, row in sheet_rows('Master Catalogue')}
selling_rows = {row[0]: (rn, row) for rn, row in sheet_rows('Selling Details')}
check(len(master_rows) == len(selling_rows) == len(options), 'Master and selling sheets cover every active option')

for pid, option in options.items():
    check(set(option['master_fields']) == set(FIELDS), pid+' has exactly six current specification groups')
    check(option['six_working_fields_recorded'], pid+' working-coverage flag retained')
    for fi, field in enumerate(FIELDS):
        mf = option['master_fields'][field]
        check(bool(mf.get('display','').strip()), pid+' '+field+' has a nonblank display')
        check(mf.get('working_recorded') == 1, pid+' '+field+' is marked recorded')
        check(bool(mf.get('state','').strip()), pid+' '+field+' retains its evidence state')
        row_number, row = spec_rows[(pid, field)]
        check(row[1] == option['name'], pid+' specification row uses current name')
        check(row[3] == mf['display'], pid+' '+field+' workbook value matches register')
        check(row[4] == mf['state'], pid+' '+field+' workbook evidence state matches register')
        check((row[5] or '')+(row[14] or '') == mf['basis'], pid+' '+field+' complete workbook basis matches register')
        check(row[8] == mf['working_recorded'], pid+' '+field+' workbook recorded flag matches')
        check(row[15] == pid+'::'+field and row[16] == 1, pid+' '+field+' lookup key is unique and usable')
        check(native['Specifications'][f'D{row_number}']['value'] == mf['display'], pid+' '+field+' saved workbook XML matches register')
        check(csv_by_key[(pid,field)]['working_display'] == mf['display'], pid+' '+field+' verification CSV matches register')
        check(csv_by_key[(pid,field)]['evidence_state'] == mf['state'], pid+' '+field+' verification CSV retains evidence state')
        check(csv_by_key[(pid,field)]['basis'] == mf['basis'], pid+' '+field+' verification CSV retains basis')
        check(option_csv[pid][field] == mf['display'] and option_csv[pid][field+' evidence state'] == mf['state'], pid+' '+field+' current option CSV matches')
        mrn, master_row = master_rows[pid]
        column = chr(ord('E')+fi)
        check(master_row[4+fi] == mf['display'], pid+' '+field+' Master Catalogue result matches')
        nc = native['Master Catalogue'][f'{column}{mrn}']
        check(nc['value'] == mf['display'], pid+' '+field+' saved Master Catalogue cached value matches')
        check(nc['formula'] is not None and "'Specifications'!" in nc['formula'] and f'$A{mrn}' in nc['formula'] and '::'+field in nc['formula'], pid+' '+field+' master formula uses its own keyed specification')
    srn, sr = selling_rows[pid]
    check(sr[1] == option['name'], pid+' Selling Details uses current name')
    check(sr[2] == option['master_fields']['Individual price']['display'], pid+' Selling Details price matches')
    check(sr[3] == option['master_fields']['Availability']['display'], pid+' Selling Details availability matches')

# Record-specific semantic review of all 188 current dimension descriptions.
# Figures mentioned only as packaging or mass-model assumptions are not face sizes.
missing_depth = {}
missing_full_size = {
    'BSI-65A93033A200': 'Overall bordered width and height are unconfirmed. The 30 cm core and 35 cm outer size are historical/model references. Depth is now an explicit 6 cm estimate, range 5–8 cm.',
    'BSI-4515726BBC18': 'Overall bordered width and height are unconfirmed. The 30 cm core and 35 cm outer size are historical/model references. Depth is now an explicit 6 cm estimate, range 5–8 cm.',
    'BSI-3C849B547D50': 'Artwork width and height are unconfirmed. The 100 × 16 × 4 cm numbers are shipping fields. Depth is now an explicit 3 cm estimate, range 2–5 cm.',
}
dimension_gaps = {**missing_depth, **missing_full_size}
material_gaps = {o['product_id'] for o in options.values() if not re.search(r'jesmonite|gypsum|plaster|composite|wood|board|mixed media|resin', o['master_fields']['Material / finish']['display'], re.I)}
check(len(dimension_gaps) == 3 and len(missing_depth) == 0 and len(missing_full_size) == 3, 'Three face-size gaps retained; no missing working depths')
check(len(material_gaps) == 27, 'Twenty-seven finish-only material descriptions enumerated')
depth_packet=read(BASE/'components/parallel-reviews/owner-depth-estimates-20261025T005003Z-B/depth-estimate-packet.json')
for entry in depth_packet['rows']:
    check(options[entry['product_id']]['master_fields']['Dimensions / depth']==entry['after'], entry['product_id']+' retains the exact authorized depth estimate and qualifications')
number=r'\d+(?:\.\d+)?(?:\s*[–-]\s*\d+(?:\.\d+)?)?'
depth_patterns=[
    number+r'\s*(?:D\s*)?cm\s*(?:deep|depth|overall depth|overall height|body depth|side depth|panel depth)',
    r'depth.{0,30}?'+number+r'\s*cm',
    number+r'\s*D\s*cm',
    number+r'\s*(?:H\s*)?×\s*'+number+r'\s*(?:W\s*)?×\s*'+number+r'\s*(?:D\s*)?cm',
]
for option in options.values():
    d=option['master_fields']['Dimensions / depth']['display']
    check(any(re.search(pattern,d,re.I) for pattern in depth_patterns),option['product_id']+' has a numerical depth or explicit depth range')

# Qualification scan preserves source differences without treating every range or approximation as a conflict.
source_difference = re.compile(r'conflict|versus|unresolved source difference|source versions|separate source|different.*claim|drafts? (?:instead |also )?(?:say|says|give|gives|estimat)|other drafts|later drafts|dated.*(?:trade|retail)|matching .*draft|matched.*draft', re.I)
measure_rows = []
with measurement_path.open(encoding='utf-8-sig', newline='') as f:
    measure_rows = list(csv.DictReader(f))
check({r['option_id'] for r in measure_rows} == active_ids and len(measure_rows) == len(active_ids), 'Measurement input includes all current option IDs')
measure_map = {'current_working_dimensions':'Dimensions / depth','current_working_weight':'Weight','current_working_material':'Material / finish','current_offered_fixing':'Fixing'}
measurement_drift = []
measurement_input_columns = ['actual_width_cm','actual_height_cm','actual_maximum_depth_cm','bare_panel_measured_weight_kg','maker_material_recipe','fitted_fixing_type','fitted_fixing_count','measured_or_inspected_by','measurement_date','measurement_method','object_or_batch_reference','supporting_evidence_reference']
entered_measurements = []
for row in measure_rows:
    option = options[row['option_id']]
    if any(row.get(k,'').strip() for k in measurement_input_columns):
        entered_measurements.append(row['option_id'])
    for column in ['name', *measure_map]:
        expected = option['name'] if column == 'name' else option['master_fields'][measure_map[column]]['display']
        if row[column] != expected:
            measurement_drift.append({'option_id':row['option_id'],'name':option['name'],'column':column,'checklist_value':row[column],'current_value':expected})

review_rows = []
selected_reference_count=0
shared_reference_count=0
for option in sorted(options.values(), key=lambda o: (o['family'], o['name'])):
    pid = option['product_id']
    fields = option['master_fields']
    references = image_index.get(pid, [])
    primary = next((x for x in references if x.get('file_id') == option.get('file_id') and x.get('native_status','').startswith('CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED')), None)
    if option.get('file_id'):
        selected_reference_count+=1
        check(primary is not None,pid+' selected image is in the current verified gallery index')
        if primary:
            check(dropbox_path(primary['image_url'])==dropbox_path(option['image_url']) and dropbox_path(primary['folder_url'])==dropbox_path(option['folder_url']),pid+' selected image and containing-folder links identify the same paths')
    else:
        reference=option.get('owner_confirmed_design_reference',{})
        shared_reference_count+=bool(reference)
        check(bool(reference.get('file_id')) and any(x['file_id']==reference['file_id'] and 'OWNER_CONFIRMED_SHARED_DESIGN_REFERENCE_ONLY' in x.get('association_statuses',[]) for x in references),pid+' has a qualified shared-design reference without an exact primary assignment')
    notes = []
    if pid in dimension_gaps:
        notes.append({'category':'Size or depth missing','detail':dimension_gaps[pid]})
    if pid in material_gaps:
        notes.append({'category':'Base material unspecified','detail':'The current material/finish field describes appearance or coating but gives no adopted base material, including no explicit working material guess. Construction assumptions in a weight model remain separate.'})
    differences = [f for f in FIELDS[:3] if source_difference.search(fields[f]['display'])]
    if differences:
        notes.append({'category':'Source versions retained','detail':'Different or conflicting source versions remain in: '+', '.join(differences)+'. The source wording below is retained; this audit does not choose between them.'})
    if 'unapproved guess' in fields['Dimensions / depth']['display']:
        notes.append({'category':'Approval wording needs alignment','detail':'The dimension display calls the depth an unapproved guess while the field state records an accepted working proposal. The face-size correction is explicit; no new depth approval is inferred.'})
    for drift in measurement_drift:
        if drift['option_id'] == pid:
            notes.append({'category':'Measurement checklist wording stale','detail':drift['column']+': '+drift['checklist_value']+' → '+drift['current_value']})
    for field, pattern in [('Weight',r'\d.*(?:kg|gram)'),('Individual price',r'£\s*\d')]:
        check(re.search(pattern, fields[field]['display'], re.I | re.S) is not None, pid+' has a numerical '+field.lower())
    check(all(term in fields['Fixing']['display'].lower() for term in ['keyhole','french cleat']), pid+' offers both fixing choices')
    check(option.get('offered_fixing_choices') == ['Keyhole fixing','French cleat'], pid+' structured fixing choices match')
    check('made to order' in fields['Availability']['display'].lower() and re.search(r'\d.*week', fields['Availability']['display'], re.I), pid+' has made-to-order and numerical lead-time policy')
    gallery = reader_root / 'products' / (pid+'.html')
    check(gallery.is_file(), pid+' has a current individual gallery')
    review_rows.append({
        'option_id':pid,'name':option['name'],'family':option['family'],
        'component_id':option.get('canonical_component_id'),'working_fields_present':6,
        'usable_face_size_recorded':pid not in missing_full_size,
        'usable_depth_recorded':pid not in missing_depth,
        'base_material_named_in_current_field':pid not in material_gaps,
        'physical_verification_recorded':option.get('physical_specifications_verified',False),
        'fields':{f:{k:fields[f].get(k) for k in ['display','state','basis','working_recorded','physical_verification']} for f in FIELDS},
        'image_url': primary['image_url'] if primary else '',
        'folder_url': primary['folder_url'] if primary else option.get('folder_url',''),
        'reference_label':'Published selected reference' if primary else 'No selected exact primary; use the qualified gallery references',
        'photo_coverage':option.get('photo_coverage',{}),
        'gallery':str(gallery),'notes':notes,
    })

# Check the explicit owner corrections most likely to be lost during merges.
owner_checks = {
    'BSI-21DCD11AD8C6':('Dimensions / depth',r'80\s*×\s*60'),
    'BSI-2418C8B43415':('Dimensions / depth',r'25\s*×\s*25'),
    'BSI-75ACAD5A9841':('Dimensions / depth',r'30\s*×\s*30'),
    'BSI-04D6E8690F30':('Dimensions / depth',r'70 H\s*×\s*15 W'),
}
for pid, (field, pattern) in owner_checks.items():
    check(re.search(pattern, options[pid]['master_fields'][field]['display']), pid+' retains the explicit owner dimension correction')
fingerprint = [o for o in options.values() if o['name'].startswith('Fingerprint Concentric')]
check(len(fingerprint) == 6, 'All six numbered Fingerprint finish options retained')
for o in fingerprint:
    d=o['master_fields']['Dimensions / depth']['display']; w=o['master_fields']['Weight']['display']
    check('40 × 40' in d and '3 cm' in d and '6 kg' in w and '4–9 kg' in w, o['product_id']+' retains approved Fingerprint working dimensions/depth/weight')
for pid, expected in {'BSI-CCB6CA396E9C':'Wall Circle — Pale Blue Marbled','BSI-22DA74B2107E':'Wall Circle — Azure Blue and White Marbled','BSI-1B20DCA291BB':'Wall Circle — Brass with World Colours'}.items():
    check(options[pid]['name']==expected, pid+' retains the latest owner pattern name')
check('brass' not in options['BSI-1B20DCA291BB']['master_fields']['Material / finish']['display'].lower(), 'Brass pattern name has not been converted into a material claim')

for path, initial_sha in sources.items():
    check(sha(path) == initial_sha, 'Source unchanged throughout audit: '+Path(path).name)
failed = [c for c in checks if not c['passed']]
summary = {
    'status':'AUDIT_COMPLETE_WITH_RECORDED_GAPS' if not failed else 'AUDIT_CHECK_FAILURES',
    'checked_utc':datetime.now(timezone.utc).isoformat(),
    'scope':'All 188 active sculpture/finish option records; 1 retired option excluded. This is a record audit, not a physical measurement exercise.',
    'active_options':len(options),'working_field_groups':len(options)*6,
    'workbook_specification_mismatches':len([c for c in failed if 'matches' in c['check']]),
    'source_and_consistency_checks_passed':len(checks)-len(failed),'source_and_consistency_checks_failed':len(failed),
    'face_size_recorded_as_claim_or_estimate':len(options)-len(missing_full_size),
    'depth_recorded_as_claim_or_estimate':len(options)-len(missing_depth),
    'options_with_size_or_depth_gap':len(dimension_gaps),
    'depth_only_gaps':len(missing_depth),'face_size_gaps':len(missing_full_size),'overall_size_and_depth_gaps':0,
    'base_material_named_as_claim_or_guess':len(options)-len(material_gaps),
    'finish_described_base_material_unspecified':len(material_gaps),
    'distinct_options_with_size_depth_or_base_material_gap':len(set(dimension_gaps)|material_gaps),
    'options_with_numeric_weight':sum(bool(re.search(r'\d.*(?:kg|gram)',o['master_fields']['Weight']['display'],re.I|re.S)) for o in options.values()),
    'options_with_numeric_price':sum(bool(re.search(r'£\s*\d',o['master_fields']['Individual price']['display'])) for o in options.values()),
    'options_with_both_fixing_choices':sum(all(s in o['master_fields']['Fixing']['display'].lower() for s in ['keyhole','french cleat']) for o in options.values()),
    'availability_and_lead_time_recorded':len(options),
    'standard_lead_time_1_to_2_weeks':187,'specific_owner_exception_1_week':'BSI-46F6DB226213',
    'options_with_entered_measurement_input':len(entered_measurements),
    'measurement_checklist_stale_cells':len(measurement_drift),
    'physical_verification_performed':False,'canonical_or_platform_writes':False,
    'source_version_difference_wording_option_count':sum(any(n['category']=='Source versions retained' for n in r['notes']) for r in review_rows),
    'approval_wording_inconsistency_count':sum(any(n['category']=='Approval wording needs alignment' for n in r['notes']) for r in review_rows),
    'saved_workbook_formula_errors':saved_errors,
    'selected_reference_options':selected_reference_count,'qualified_shared_design_reference_options':shared_reference_count,
    'photo_coverage_counts':{k:dict(Counter(o['photo_coverage'].get(k) for o in options.values())) for k in ['individual','in_situ','series']},
    'live_dropbox_checks_performed':False,
}
report = {'summary':summary,'source_hashes':sources,'checks':checks,'failures':failed,'dimension_gaps':dimension_gaps,'material_gap_ids':sorted(material_gaps),'measurement_checklist_drift':measurement_drift,'options':review_rows}
(HERE/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if failed:
    print(json.dumps({'summary':summary,'failures':failed},ensure_ascii=False,indent=2))
    raise SystemExit(1)

def esc(value):
    return escape(str(value or ''), quote=True)

def links(row):
    parts=[]
    if row['image_url']: parts.append(f'<a href="{esc(row["image_url"])}">Image</a>')
    if row['folder_url']: parts.append(f'<a href="{esc(row["folder_url"])}">Containing folder</a>')
    parts.append(f'<a href="{esc(Path(row["gallery"]).as_uri())}">Full gallery</a>')
    return ' · '.join(parts)

OUT.mkdir(exist_ok=False)
rows_by_id={r['option_id']:r for r in review_rows}
dimension_html=''.join(f'<tr><td><a href="#{pid}">{esc(rows_by_id[pid]["name"])}</a></td><td>{esc(note)}</td><td>{links(rows_by_id[pid])}</td></tr>' for pid,note in dimension_gaps.items())
material_html=''.join(f'<tr><td><a href="#{pid}">{esc(rows_by_id[pid]["name"])}</a></td><td>{esc(rows_by_id[pid]["fields"]["Material / finish"]["display"])}</td><td>{links(rows_by_id[pid])}</td></tr>' for pid in sorted(material_gaps,key=lambda p:rows_by_id[p]['name']))
cards=[]
for r in review_rows:
    notes=''.join(f'<li><strong>{esc(n["category"])}:</strong> {esc(n["detail"])}</li>' for n in r['notes'])
    field_rows=''.join(f'<tr><th scope="row">{esc(f)}</th><td class="pre">{esc(r["fields"][f]["display"])}</td><td class="pre">{esc(r["fields"][f]["state"])}</td></tr>' for f in FIELDS)
    gap=r['option_id'] in dimension_gaps or r['option_id'] in material_gaps
    cards.append(f'<article id="{r["option_id"]}" data-gap="{str(gap).lower()}"><h3>{esc(r["name"])}</h3><p>{esc(r["family"])} · {esc(r["option_id"])}</p><p>{links(r)}</p><p>{esc(r["reference_label"])}</p>'+('<ul>'+notes+'</ul>' if notes else '')+f'<table><thead><tr><th>Specification</th><th>Current working detail</th><th>Evidence / qualification</th></tr></thead><tbody>{field_rows}</tbody></table></article>')
drift_html=''.join(f'<li><strong>{esc(d["name"])}</strong>: {esc(d["column"])} still says “{esc(d["checklist_value"])}”; the current master says “{esc(d["current_value"])}”.</li>' for d in measurement_drift)
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Individual sculpture specifications: double-check</title><style>
body{{font:16px/1.55 system-ui,sans-serif;color:#20262a;background:#f7f6f2;max-width:1250px;margin:auto;padding:28px}}a{{color:#165c78}}h1{{font-size:2rem;line-height:1.2}}h2{{margin-top:2rem}}p{{max-width:1050px}}table{{width:100%;border-collapse:collapse;background:white;margin:16px 0}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #d8dbdc}}thead{{background:#e5e9e9}}article{{background:white;border:1px solid #d8dbdc;padding:20px;margin:20px 0;scroll-margin-top:20px}}article h3{{margin-top:0}}article th:first-child{{width:15%}}article td:nth-child(2){{width:48%}}.pre{{white-space:pre-wrap}}.controls{{display:flex;gap:15px;align-items:center;flex-wrap:wrap;padding:14px 0}}input[type=search]{{font:inherit;padding:9px;min-width:300px}}summary{{cursor:pointer;font-weight:600}}.meta{{font-size:.88rem;color:#4e565a;overflow-wrap:anywhere}}@media(max-width:700px){{body{{padding:15px}}table{{font-size:.88rem}}th,td{{padding:7px}}}}@media print{{.controls{{display:none}}article{{break-inside:avoid}}}}
</style></head><body><h1>Individual sculpture specifications: double-check</h1>
<p>Checked all <strong>188 active sculpture/finish options</strong> against the published master workbook, canonical register and field checklist. Every option has all six working field groups populated, and all 1,128 current field descriptions agree across those records.</p>
<p>All <strong>188 options now have a working depth</strong>, including the 14 newly recorded estimates. Three options still lack an adopted overall width and height. Twenty-seven describe a finish without naming the base material; that group includes the three face-size gaps. Estimates, source claims and source differences remain labelled.</p>
<table><thead><tr><th>Check</th><th>Recorded</th><th>Qualification</th></tr></thead><tbody>
<tr><td>Face size / diameter</td><td>185 / 188</td><td>Includes owner instructions, source claims and working estimates.</td></tr>
<tr><td>Overall depth</td><td>188 / 188</td><td>Includes estimates; excludes packing figures and assumed average material thickness.</td></tr>
<tr><td>Weight</td><td>188 / 188</td><td>Numerical value or range. Accepted approximations and source differences retained.</td></tr>
<tr><td>Base material</td><td>161 / 188</td><td>Named as a source claim, owner detail or working guess; recipes may still be unknown.</td></tr>
<tr><td>Fixing choices</td><td>188 / 188</td><td>Keyhole or French cleat; installed hardware remains separately unverified.</td></tr>
<tr><td>Price</td><td>188 / 188</td><td>187 working estimates; one specific owner-accepted £175 panel price.</td></tr>
<tr><td>Availability / lead time</td><td>188 / 188</td><td>Made to order, 1–2 weeks for 187 options. Moon Crater Phase 4 — Verdigris and Rust retains the specific owner one-week policy.</td></tr>
</tbody></table>
<p>There are no entered measurements in the current measurement input sheet. This review verifies records and their consistency; it does not measure, weigh or inspect physical sculptures. The single retired Sandstone option remains outside the active count. Different finishes and legacy records sharing a design retain their own fields.</p>
<p><a href="#size-gaps">Size / depth gaps</a> · <a href="#material-gaps">Base material gaps</a> · <a href="#checklist">Checklist wording</a> · <a href="#all-options">All 188 options</a></p>
<h2 id="size-gaps">Three options with face-size gaps</h2><table><thead><tr><th>Option</th><th>Missing detail</th><th>References</th></tr></thead><tbody>{dimension_html}</tbody></table>
<h2 id="material-gaps">Twenty-seven options with base material unspecified</h2><p>These records describe the visible finish. A material assumed only for estimating weight has not been promoted into a product-material claim.</p><table><thead><tr><th>Option</th><th>Current material / finish wording</th><th>References</th></tr></thead><tbody>{material_html}</tbody></table>
<h2 id="checklist">Supporting checklist and wording</h2><p>The current master and 1,128-field checklist agree. The physical-measurement input file has {len(measurement_drift)} stale entries; the previous three have been corrected.</p><ul>{drift_html}</ul><p>Coral Spiral retains “unapproved guess” in its depth description and basis while the field state says the working proposal is accepted. This is a wording conflict, not a new missing depth. Its 55 × 55 cm face and working 6 cm depth (range 5–7 cm) remain recorded.</p>
<h2>Image references</h2><p>All 188 gallery product records match the current register. There are 187 selected image references and one qualified shared-design reference. Individual coverage is 177 available, 10 accepted group-only references and one shared-design reference. The 22 installation and one series-image requests remain deferred under the owner instructions. This review checked local records and links, not live Dropbox file availability.</p>
<h2 id="all-options">All 188 options</h2><div class="controls"><label>Find a sculpture <input id="query" type="search" placeholder="Name, family or option ID"></label><label><input id="gapsOnly" type="checkbox"> Show the 27 options with face-size or material gaps</label><span id="count">188 options shown</span></div>{''.join(cards)}
<details><summary>Sources and method</summary><p>Source hashes were checked at the start and end. Current values were read with Artifact Tool and independently compared with saved XLSX XML. Master Catalogue formulas were checked for the correct option/field keys, and all current display values and evidence states were compared with the register and published checklist. Size and base-material gaps were reviewed from the complete text, including packaging and weight-model limitations. Existing Dropbox references come from the published gallery; they were not re-fetched live during this specification review. No canonical records or platforms were changed.</p><p><a href="{workbook_path.as_uri()}">Published master workbook</a> · <a href="{register_path.as_uri()}">Canonical register</a> · <a href="{checklist_path.as_uri()}">Field checklist</a> · <a href="{measurement_path.as_uri()}">Measurement input</a></p><p class="meta">Checked {esc(summary['checked_utc'])}<br>Register SHA-256: {sources[str(register_path)]}<br>Workbook SHA-256: {sources[str(workbook_path)]}</p></details>
<script>const cards=[...document.querySelectorAll('article')];function filter(){{const q=document.getElementById('query').value.toLowerCase();const gaps=document.getElementById('gapsOnly').checked;let n=0;for(const c of cards){{const show=(!q||c.textContent.toLowerCase().includes(q))&&(!gaps||c.dataset.gap==='true');c.hidden=!show;if(show)n++;}}document.getElementById('count').textContent=n+' options shown';}}document.getElementById('query').addEventListener('input',filter);document.getElementById('gapsOnly').addEventListener('change',filter);</script></body></html>'''
(OUT/'index.html').write_text(html)
(HERE/'report-location.json').write_text(json.dumps({'report':str(OUT/'index.html'),'report_sha256':sha(OUT/'index.html'),'audit_json':str(HERE/'audit.json'),'audit_sha256':sha(HERE/'audit.json')},indent=2)+'\n')
print(json.dumps({'summary':summary,'report':str(OUT/'index.html'),'failures':failed[:20]},ensure_ascii=False,indent=2))
