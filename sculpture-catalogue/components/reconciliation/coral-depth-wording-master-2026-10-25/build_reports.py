"""Build current option and explicitly estimated depth views."""
import csv
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

H = Path(__file__).resolve().parent
B = H.parents[2]
OUT = B/'outputs'/H.name
OUT.mkdir(exist_ok=True)
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda s: html.escape(str(s),quote=True)
g = read(H/'canonical-master-register.json')
old_pointer = read(H/'inputs/pointer.before')
summary = read(H/'import-summary.json')
active = set(g['active_option_ids'])
options = {o['product_id']:o for o in g['options']}
pages = []
csvs = []
def local(path):
    return os.path.relpath(Path(path),OUT)
def link(url,label):
    return '<a href="'+esc(url)+'">'+esc(label)+'</a>'
def nav():
    gallery = old_pointer['current_published_gallery_projection']['readers']
    return '<nav>'+link('index.html','Current sculptures and specifications')+' · '+link('depth-estimates.html','Fourteen depth estimates')+' · '+link('remaining-photograph-requests.html','Photograph holds')+' · '+link(local(gallery['product-images.html']),'Earlier complete image-gallery snapshot')+'</nav>'
def page(name,title,body):
    text = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>body{font:17px/1.5 Arial,sans-serif;max-width:1100px;margin:35px auto;padding:0 20px;color:#202020}article{border-top:1px solid #bbb;margin-top:32px;padding-top:15px}table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{width:25%}.note{background:#f1f5f7;padding:15px}small{overflow-wrap:anywhere}a{color:#154c7a}details{margin:10px 0}input{padding:10px;width:95%;font:inherit}</style></head><body><h1>'+esc(title)+'</h1>'+nav()+body+'</body></html>'
    path = OUT/name
    path.write_text(text)
    pages.append(path)
def reference(option):
    if option.get('image_url'):
        return option,'Accepted group listing reference' if option['photo_coverage']['individual'] == 'Group only' else 'Individual reference'
    return option.get('owner_confirmed_design_reference',{}),'Shared relief-design reference'
def image_links(option):
    ref,label = reference(option)
    if not ref.get('image_url'):
        return '<p>No selected individual photograph.</p>'
    return '<p>'+link(ref['image_url'],label)+' · '+link(ref['folder_url'],'Containing Dropbox folder')+'</p><p><small>File '+esc(ref['file_id'])+' · folder '+esc(ref['folder_id'])+'</small></p>'
def fields(option):
    return '<table>'+''.join('<tr><th>'+esc(name)+'</th><td>'+esc(value['display'])+'<br><small>'+esc(value['state'])+'</small></td></tr>' for name,value in option['master_fields'].items())+'</table>'

intro = '<p class="note">188 active option records;189 retained rows;112 identified component records and110 working design groups. All188 options now have a working depth, including14 labelled depth estimates. These are not physical measurements. Azure and the two bordered Moonphase face sizes remain unconfirmed.</p>'
intro += '<p>'+link('depth-estimates.html','Review all14 estimated depths with pictures and containing folders')+' · '+link('Current_Individual_Options_188.csv','All188 current options')+' · '+link('Specification_Verification_Checklist_1128_Fields.csv','1128 qualified specification fields')+'</p><p>The earlier complete gallery is source evidence; current cards below show the updated working depths. Image membership does not establish exact measurements or platform variants.</p>'
cards = []
for option in g['options']:
    oid = option['product_id']
    body = '<article id="'+esc(oid)+'" data-search="'+esc((option['name']+' '+option['family']+' '+oid).lower())+'"><h2>'+esc(option['name'])+'</h2>'
    if oid not in active:
        body += '<p>Retired; retained for history.</p>'
    body += image_links(option)+'<p>'+esc(option['identity_basis'])+'</p>'
    if option.get('current_owner_pattern_resolution'):
        body += '<p class="note">Owner-confirmed pattern: '+esc(option['owner_confirmed_pattern_name'])+'. Exact native variant/configuration remains unverified.</p>'
    if option.get('current_owner_identity_resolution'):
        body += '<p class="note">FFL1 and FFS2 share the relief design. This image is a shared design reference; no separate legacy primary photograph or exact historical cast is selected.</p>'
    body += '<details id="fields-'+esc(oid)+'"><summary>Six working specifications and evidence states</summary>'+fields(option)+'</details>'
    body += '<p><small>Option '+esc(oid)+' · component '+esc(option.get('canonical_component_id') or 'Unassigned visual/source scope')+'</small></p></article>'
    cards.append(body)
page('index.html','Boldstone current sculpture catalogue',intro+'<p><input id="filter" placeholder="Filter by sculpture, family or option ID" aria-label="Filter sculptures"></p>'+''.join(cards)+'<script>document.getElementById("filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("article[data-search]").forEach(x=>x.hidden=!x.dataset.search.includes(q))})</script>')

packet = read(H/'depth-estimate-packet.json')
cards=[]
for row in packet['rows']:
    option=options[row['product_id']];estimate=row['estimate']
    cards.append('<article id="'+esc(option['product_id'])+'"><h2>'+esc(option['name'])+'</h2>'+image_links(option)+'<p><strong>Working depth '+esc(estimate['nominal_cm'])+' cm; range '+esc(estimate['range_cm'][0])+'–'+esc(estimate['range_cm'][1])+' cm.</strong> Estimated; not measured.</p><p>'+esc(row['after']['display'])+'</p><p>'+esc(estimate['basis'])+'</p>'+link('index.html#'+option['product_id'],'Current option and all six fields')+'</article>')
page('depth-estimates.html','Fourteen owner-authorized depth estimates','<p>'+esc(packet['depth_definition'])+'</p><p>Numerical values are assistant estimates under the owner request; no actual measurement or individual numerical owner confirmation is asserted. No weights, material, fixing, price, availability or image roles change.</p>'+''.join(cards))
holds = '<p class="note">No active capture request is added. The22 missing installation references and one required series reference remain deferred. FFL1’s relief identity is resolved; its shared design reference does not certify a separate historical cast.</p><p>'+link('individual-images.html','Frozen Fish design reference')+' · '+link('in-situ-images.html','22 held installation cases')+' · '+link('series-images.html','One held series case')+'</p>'
page('remaining-photograph-requests.html','Photograph requests and retained holds',holds)
page('individual-images.html','Frozen Fish identity closure and shared design reference',image_links(options['BSI-04D6E8690F30'])+'<p>The owner confirmed FFL1 and FFS2 are the same relief design. Current face70×15cm. No new individual capture request or separate primary photograph is inferred.</p>')
for role,name,title in [('in_situ','in-situ-images.html','Held installation photographs'),('series','series-images.html','Held series photograph')]:
    rows = []
    for option in g['options']:
        if option['product_id'] in active and option['photo_coverage'][role] == 'No verified image':
            rows.append('<article id="'+esc(option['product_id'])+'"><h2>'+esc(option['name'])+'</h2>'+image_links(option)+'<p>Existing owner deferral retained. No new capture request.</p></article>')
    assert len(rows) == (22 if role == 'in_situ' else 1)
    page(name,title,'<p>Existing owner holds remain in force.</p>'+''.join(rows))
page('specifications-to-verify.html','Physical specifications to verify','<p>All188 active options retain six working fields. Actual measurements, bare-panel weights, material/formulation and fitted fixing remain qualified until separately evidenced. Fourteen depths remain explicit owner-authorized working estimates. Coral Spiral acceptance wording is aligned with its existing state. Existing face-size unknowns, other fields and actual measurement status remain qualified.</p><p>'+link('Specification_Verification_Checklist_1128_Fields.csv','Full1128-field checklist')+'</p>'+''.join('<p>'+link('index.html#fields-'+o['product_id'],o['name'])+'</p>' for o in g['options'] if o['product_id'] in active))

columns = ['option_id','name','family','component_id','individual_reference_scope','primary_file_id','primary_folder_id','reference_file_id','reference_folder_id','image_url','folder_url']
field_names = list(next(iter(options.values()))['master_fields'])
columns += [x for field in field_names for x in [field,field+' evidence state']]
path = OUT/'Current_Individual_Options_188.csv'
with path.open('w',newline='') as stream:
    writer = csv.DictWriter(stream,fieldnames=columns)
    writer.writeheader()
    for option in g['options']:
        if option['product_id'] not in active:
            continue
        ref,label = reference(option)
        row = {'option_id':option['product_id'],'name':option['name'],'family':option['family'],
            'component_id':option.get('canonical_component_id'),'individual_reference_scope':label,
            'primary_file_id':option.get('file_id'),'primary_folder_id':option.get('folder_id'),
            'reference_file_id':ref.get('file_id'),'reference_folder_id':ref.get('folder_id'),
            'image_url':ref.get('image_url'),'folder_url':ref.get('folder_url')}
        for field,value in option['master_fields'].items():
            row[field] = value['display']
            row[field+' evidence state'] = value['state']
        writer.writerow(row)
csvs.append(path)
def write_csv(name,headers,rows):
    path = OUT/name
    with path.open('w',newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    csvs.append(path)
groups = g['current_working_design_group_projection']['groups']
assert len(groups) == 110
write_csv('Current_Working_Design_Groups_110.csv',['working_design_group_id','retained_component_ids','active_option_ids','grouping_basis'],
    [[x['working_design_group_id'],';'.join(x['retained_component_ids']),';'.join(x['active_option_ids']),x['grouping_basis']] for x in groups])
headers = ['option_id','name','role','status','reference_file_id','reference_folder_id','image_url','folder_url','qualification']
held = {}
for role,label in [('in_situ','In situ'),('series','Series')]:
    rows = []
    for option in g['options']:
        if option['product_id'] in active and option['photo_coverage'][role] == 'No verified image':
            ref,scope = reference(option)
            rows.append([option['product_id'],option['name'],label,'Owner deferred',ref.get('file_id'),ref.get('folder_id'),ref.get('image_url'),ref.get('folder_url'),scope+'; not a verified '+label+' photograph. Existing owner hold unchanged.'])
    held[role] = rows
write_csv('Missing_Pictures_Required.csv',headers,held['in_situ']+held['series'])
write_csv('Missing_In_Situ_Images.csv',headers,held['in_situ'])
write_csv('Missing_Series_Images.csv',headers,held['series'])
write_csv('Held_In_Situ_Cases_22.csv',headers,held['in_situ'])
write_csv('Held_Series_Cases_1.csv',headers,held['series'])
for name in ['Missing_Individual_Images.csv','Existing_Images_to_Check.csv','Active_In_Situ_Photographs_Required_0.csv','Active_Series_Photographs_Required_0.csv']:
    write_csv(name,headers,[])
optional = []
for option in g['options']:
    if option['product_id'] in active and option['photo_coverage']['series'] == 'Optional / no fixed set':
        ref,scope = reference(option)
        optional.append([option['product_id'],option['name'],'Series','Optional',ref.get('file_id'),ref.get('folder_id'),ref.get('image_url'),ref.get('folder_url'),scope+'; no compulsory series photograph.'])
assert len(optional) == 70 and len(held['in_situ']) == 22 and len(held['series']) == 1
write_csv('Optional_Series_Images.csv',headers,optional)
path = OUT/'Specification_Verification_Checklist_1128_Fields.csv'
with path.open('w',newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(['option_id','name','field','working_display','evidence_state','basis','physical_verification'])
    for option in g['options']:
        if option['product_id'] in active:
            for field,value in option['master_fields'].items():
                writer.writerow([option['product_id'],option['name'],field,value['display'],value['state'],value['basis'],value['physical_verification']])
csvs.append(path)
(OUT/'current-count-summary.json').write_text(json.dumps({'summary':g['summary'],'latest_wording_correction':summary},ensure_ascii=False,indent=2)+'\n')

write_csv('Depth_Estimates_14.csv',['option_id','name','estimated_body_depth_cm','working_range_min_cm','working_range_max_cm','estimate_status','image_url','folder_url'],
    [[row['product_id'],row['name'],row['estimate']['nominal_cm'],*row['estimate']['range_cm'],'Estimate; not measured',row['image_url'],row['folder_url']] for row in packet['rows']])
with (H/'inputs/actual_input.before').open(encoding='utf-8-sig',newline='') as stream:
    source = csv.DictReader(stream)
    input_headers = source.fieldnames
    actual_rows = list(source)
actual_keys = ['actual_width_cm','actual_height_cm','actual_maximum_depth_cm','bare_panel_measured_weight_kg',
    'maker_material_recipe','fitted_fixing_type','fitted_fixing_count','measurement_date','measurement_method',
    'object_or_batch_reference','supporting_evidence_reference']
original_actual = {row['option_id']:{key:row[key] for key in actual_keys} for row in actual_rows}
for row in actual_rows:
    option = options[row['option_id']]
    row['name'] = option['name']
    for column,field in [('current_working_dimensions','Dimensions / depth'),('current_working_weight','Weight'),
        ('current_working_material','Material / finish'),('current_offered_fixing','Fixing')]:
        row[column] = option['master_fields'][field]['display']
    assert {key:row[key] for key in actual_keys} == original_actual[row['option_id']]
for row in packet['rows']:
    actual = original_actual[row['product_id']]
    assert all(not actual[key].strip() for key in ['actual_width_cm','actual_height_cm','actual_maximum_depth_cm']),row['product_id']
actual_path = OUT/'Physical_Verification_Input_188_Options.csv'
with actual_path.open('w',encoding='utf-8-sig',newline='') as stream:
    writer = csv.DictWriter(stream,fieldnames=input_headers)
    writer.writeheader()
    writer.writerows(actual_rows)
assert len(actual_rows) == 188
csvs.append(actual_path)
(H/'actual-input-verification.json').write_text(json.dumps({'status':'PASS_ACTUAL_INPUTS_PRESERVED',
    'rows':188,'target_face_and_depth_measurement_cells_remain_blank':42,
    'all_original_actual_measurement_fields_preserved':True,'source_sha256':sha(H/'inputs/actual_input.before'),
    'current_path':str(actual_path),'current_sha256':sha(actual_path),'new_actual_measurements':0},indent=2)+'\n')

findings=read(B/'components/parallel-reviews/specification-double-check-after-depth-20261025T013835Z-B/findings.json')
audit_cards=[]
face_ids={x['option_id'] for x in findings['missing_working_specifications']['face_size_options']}
for number,item in enumerate(findings['missing_working_specifications']['base_material_options'],1):
    o=options[item['option_id']]
    body='<article id="'+esc(o['product_id'])+'"><h2>'+str(number)+'. '+esc(o['name'])+'</h2>'+image_links(o)
    body+='<p>Base material is unspecified. The finish description does not establish the underlying material.</p>'
    if o['product_id'] in face_ids:body+='<p>Face width and height also remain unconfirmed. The current depth is a labelled estimate.</p>'
    body+=fields(o)+'</article>'
    audit_cards.append(body)
assert len(audit_cards)==27 and len(face_ids)==3
coral=options['BSI-0C2CB099DDEB']
page('coral-depth-wording.html','Coral Spiral working-depth wording',image_links(coral)+'<p>The existing accepted estimate state is retained. The old “unapproved” text is corrected. Face55×55cm, estimated depth6cm and range5–7cm are unchanged. No individual numerical confirmation or physical measurement is inferred.</p>'+fields(coral))
page('specification-audit.html','Remaining face-size and base-material checks','<p>The independent review covered all188 active options and1128 working fields. It found no record/workbook/CSV mismatch. All188 have a working depth, numeric weight, numeric price, fixing choices and availability. These entries retain their evidence qualifications.</p><p>Coral Spiral’s acceptance wording has been aligned with its existing state. Twenty-seven options still lack a named base material; three of those also lack confirmed face dimensions. Photograph holds remain22 installation and1 series case.</p><p>'+link('coral-depth-wording.html','Coral wording correction')+' · '+link(local(B/'outputs/specification-double-check-after-depth-20261025T013835Z-B/index.html'),'Frozen independent audit before the wording correction')+'</p>'+''.join(audit_cards))

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
    def handle_starttag(self,tag,attrs):
        d = dict(attrs)
        if d.get('id'):
            self.ids.add(d['id'])
        if tag == 'a' and d.get('href'):
            self.links.append(d['href'])
failures = []
cache = {}
for path in pages:
    parser = Parser()
    parser.feed(path.read_text())
    for url in parser.links:
        parsed = urlparse(url)
        if parsed.scheme:
            continue
        target = (path.parent/unquote(parsed.path)).resolve() if parsed.path else path
        if not target.is_file():
            failures.append(str(target))
        elif parsed.fragment and target.suffix == '.html':
            if target not in cache:
                other = Parser()
                other.feed(target.read_text())
                cache[target] = other.ids
            if unquote(parsed.fragment) not in cache[target]:
                failures.append(str(target)+'#'+parsed.fragment)
receipt = {'status':'FAIL' if failures else 'PASS_CURRENT_CORAL_WORDING_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),
    'pages':[{'path':str(p),'sha256':sha(p)} for p in pages],'csv_files':[{'path':str(p),'sha256':sha(p)} for p in csvs],
    'current_count_summary':{'path':str(OUT/'current-count-summary.json'),'sha256':sha(OUT/'current-count-summary.json')},
    'active_options':188,'retained_rows':189,'qualified_active_fields':1128,'depth_estimate_fields':14,
    'context_holds':22,'series_holds':1,'wording_field_objects':1,'new_physical_verifications':0,'failures':failures}
(H/'report-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['pages','csv_files']},indent=2))
assert not failures
