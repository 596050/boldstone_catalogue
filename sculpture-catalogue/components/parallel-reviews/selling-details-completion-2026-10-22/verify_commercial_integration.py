"""Read saved register/XLSX directly and check the scoped commercial overlay."""
import argparse
import hashlib
import json
import posixpath
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile

p = argparse.ArgumentParser()
p.add_argument('--register', required=True)
p.add_argument('--workbook', required=True)
p.add_argument('--receipt', required=True)
args = p.parse_args()
here = Path(__file__).resolve().parent
packet = json.loads((here/'price-completion-packet.json').read_text())
source = json.loads(Path(packet['source_register']['path']).read_text())
current = json.loads(Path(args.register).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
checks = 0
def check(ok, label):
    global checks
    checks += 1
    if not ok: raise AssertionError(label)

before = {o['product_id']:o for o in source['options']}
after = {o['product_id']:o for o in current['options']}
check(set(before) == set(after) and len(after) == 186, 'stable 186 option IDs')
check(len(current['components']) == 112, '112 component identities')
check(current['original_review_specification_assertions'] == source['original_review_specification_assertions'], 'original 1668 assertions unchanged')
fields = ['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']
history = {x['product_id']: x['prior_current_master_fields'] for x in current['historical_commercial_field_revisions'][-1]['options']}
for entry in packet['entries']:
    pid = entry['product_id']; old = before[pid]; new = after[pid]
    check(new['specifications'] == old['specifications'], pid + ' original specification evidence preserved')
    check(new['physical_specifications_verified'] == old['physical_specifications_verified'], pid + ' physical status unchanged')
    for k,v in entry['selling_details'].items():
        check(new['selling_details'].get(k) == v, pid + ' structured selling detail ' + k)
    if not entry.get('retain_current_commercial_fields_exactly'):
        check(history[pid] == entry['before_master_fields'], pid + ' complete prior commercial fields archived')
    for f in fields[:4]:
        check(new['master_fields'][f] == old['master_fields'][f], pid + ' unchanged ' + f)
    for f in fields[4:]:
        actual = new['master_fields'][f]
        check(actual['display'] == entry['after'][f]['display'], pid + ' current ' + f)
        check(actual['physical_verification'] == old['master_fields'][f]['physical_verification'], pid + ' physical flag ' + f)
        check(actual['working_recorded'] == old['master_fields'][f]['working_recorded'], pid + ' working acceptance ' + f)
        if entry.get('retain_current_commercial_fields_exactly'):
            check(actual == old['master_fields'][f], pid + ' exact prior specific owner field')

ns = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
rn = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
sheets = {}; formula_count = 0; native_links = 0; link_targets = {}; formula_cells = {}
with ZipFile(args.workbook) as z:
    strings = [''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    rels = {e.get('Id'):e.get('Target') for e in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    for sh in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',ns):
        target = rels[sh.get(rn+'id')]
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        xml = E.fromstring(z.read(path)); rows = {}
        native_links += len(xml.findall('s:hyperlinks/s:hyperlink',ns))
        relpath = posixpath.join(posixpath.dirname(path),'_rels',posixpath.basename(path)+'.rels')
        sr = {e.get('Id'):e.get('Target') for e in E.fromstring(z.read(relpath))} if relpath in z.namelist() else {}
        for link in xml.findall('s:hyperlinks/s:hyperlink',ns):
            rid = link.get(rn+'id')
            target = sr[rid] if rid in sr else ('#'+link.get('location')) if link.get('location') else None
            check(bool(target), 'no blank native hyperlink '+sh.get('name')+' '+link.get('ref'))
            link_targets[(sh.get('name'),link.get('ref'))] = target
        for row in xml.findall('s:sheetData/s:row',ns):
            cells = {}
            for c in row:
                v = c.find('s:v',ns); value = v.text if v is not None else ''
                if c.get('t') == 's': value = strings[int(value)]
                elif c.get('t') == 'inlineStr': value = ''.join(c.find('s:is',ns).itertext())
                check(c.get('t') != 'e', 'No Excel error: '+sh.get('name')+' '+c.get('r'))
                if c.find('s:f',ns) is not None:
                    formula_count += 1
                    formula_cells[(sh.get('name'),c.get('r'))] = {'formula':'='+c.find('s:f',ns).text,'value':value}
                cells[''.join(x for x in c.get('r') if x.isalpha())] = value
            rows[int(row.get('r'))] = cells
        sheets[sh.get('name')] = rows
expected = json.loads((Path(args.register).parent/'expected-edit.json').read_text())
for link in expected['hyperlinks']:
    check(link_targets.get((link['sheet'],link['cell'])) == link['target'], 'native hyperlink '+link['sheet']+' '+link['cell'])
for f in expected['formulas']:
    actual = formula_cells[(f['sheet'],f['cell'])]
    check(actual['formula'] == f['formula'], 'linked selling formula '+f['cell'])
    check(str(actual['value']) == str(f['expected']), 'cached selling formula '+f['cell'])
master = {r['A']:r for n,r in sheets['Master Catalogue'].items() if r.get('A') in after}
spec = {(r.get('A'),r.get('C')):r for n,r in sheets['Specifications'].items() if r.get('A') in after}
check(len(master) == 186 and len(spec) == 1116, 'native 186 options and 1116 specifications')
for pid, option in after.items():
    for col,f in zip(['E','F','G','H','I','J'],fields):
        desired = option['master_fields'][f]['display']
        check(master[pid][col] == desired, pid+' Master cached '+f)
        check(spec[(pid,f)]['D'] == desired, pid+' Specifications '+f)
    check(master[pid]['K'] == '6', pid+' six usable working fields')
audit_ref = current.get('latest_image_coverage_audit',{})
counts = audit_ref.get('counts',{})
check(counts['individual_statuses'] == {'Available':167,'Detail only':2,'Group only':16,'Unbound identity':1}, 'three accepted images close only three individual roles')
check(counts['in_situ_statuses']['No verified image'] == 61 and counts['series_statuses']['No verified image'] == 18, 'context image gaps unchanged')
approved_images = {'BSI-B42C439049D7':'id:cnqzTNngPVsAAAAAAA6VkQ','BSI-718DFFB7EC5D':'id:cnqzTNngPVsAAAAAAA6VjQ','BSI-54F871DCF4CA':'id:cnqzTNngPVsAAAAAAA6Vjg'}
for pid,fileid in approved_images.items():
    check(after[pid]['file_id'] == fileid, pid + ' owner accepted new listing image ID')
receipt = {'status':'PASS','checks':checks,'packet_sha256':sha(here/'price-completion-packet.json'),'register':str(Path(args.register).resolve()),'register_sha256':sha(args.register),'workbook':str(Path(args.workbook).resolve()),'workbook_sha256':sha(args.workbook),'options':186,'components':112,'commercial_displays_checked':372,'other_field_groups_unchanged':744,'original_specifications_and_assertions_retained':True,'specific_MCP4_owner_fields_exact':True,'sheets':len(sheets),'native_formulas':formula_count,'native_links':native_links,'image_counts_from_final_audit':counts,'scope':'Independent saved JSON and native XLSX readback; no remote or shared-master writes'}
Path(args.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='image_counts_from_final_audit'},indent=2))
