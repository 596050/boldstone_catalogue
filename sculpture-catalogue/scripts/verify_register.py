"""Validate inventory coverage, exact native-value preservation and saved XLSX output."""
import hashlib,json,posixpath,sqlite3,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET

project=Path(__file__).resolve().parents[1];ev=project/'evidence'
model=json.loads((ev/'catalogue_model.json').read_text())
source=json.loads((ev/'catalogue_source_tables_2026-10-15.json').read_text())
native=json.loads((ev/'native_records.json').read_text())
inventory=json.loads((ev/'wall_inventory_2026-10-16.json').read_text())
checkpoint=json.loads((project/'checkpoint.json').read_text())
workbook=project/'outputs/Boldstone_Sculpture_Specification_Register_2026-10-16.xlsx'
original=(project/checkpoint['source_workbook']).resolve()
checks=[]
def require(condition,label):
    assert condition,label
    checks.append(label)

require(hashlib.sha256(original.read_bytes()).hexdigest()==checkpoint['source_workbook_sha256'],'Original source workbook SHA-256 unchanged')
require(inventory['complete'],'Fresh Dropbox recursive listing exhausted')
require(len({r['file_id'] for r in inventory['entries']})==len(inventory['entries']),'Unique Dropbox inventory stable IDs')
current={r['file_id']:r for r in inventory['entries']}
groups={r['group_id']:r for r in model['groups']};assets={r['file_id']:r for r in model['assets']};offers={r['offer_key']:r for r in model['offers']}
require(len(groups)==347 and len(assets)==6656 and len(model['families'])==63,'All 63 families, 347 groups and 6,656 current assets represented')
require(set(assets)=={r['file_id'] for r in inventory['entries'] if r['object_type']=='file'},'Exact current file-set reconciliation')
require(sum(r['assets'] for r in model['groups'])==6656 and sum(r['groups'] for r in model['families'])==347,'Family/group/file totals reconcile')
require(all(r['group_id'] in groups and r['path'].rsplit('/',1)[0].casefold()==groups[r['group_id']]['path'].casefold() for r in model['assets']),'Every file has exactly one current immediate parent group under Dropbox case-insensitive paths')
require(len(offers)==127 and len(native)==349,'All version-specific native offers and rows retained')
require(all(r['offer_key'] in offers for r in native+model['facts']+model['links']),'All native rows, facts and relationships resolve to an offer')
require(len({r['link_id'] for r in model['links']})==len(model['links']),'Relationship IDs unique')
require(all(not r['asset_id'] or (r['asset_id'] in assets and current[r['asset_id']]['path'].rsplit('/',1)[0].casefold()==current[r['leaf_id']]['path'].casefold()) for r in model['links']),'Every image relation resolves to the current member folder')
require(all(r['leaf_id'] for r in model['links'] if r['accepted_image']),'No family-only link silently upgraded to accepted member link')

native_by_key={r['row_key']:r for r in native}
parts=defaultdict(list)
for r in model['native_fields']:parts[(r['row_key'],r['field'])].append(r)
expected={(r['row_key'],k):v for r in native for k,v in r['values'].items() if v!=''}
require(len(expected)==6028 and len(model['native_fields'])==6091,'All 6,028 nonempty native values retained in 6,091 ordered parts')
require(set(parts)==set(expected),'Exact native populated-field set preserved')
require(all(''.join(p['raw_value'] for p in sorted(parts[k],key=lambda p:p['part']))==v for k,v in expected.items()),'Every long native value reassembles without loss')
require(all(sorted(p['part'] for p in pp)==list(range(1,pp[0]['parts']+1)) for pp in parts.values()),'Native source chunk sequence complete')
# Compare against the original table rows rather than only the derived JSON.
sheet_lookup={name:{str(r['_row']):r for r in source[name]} for name in ['SS Wall Variants','SH Source Rows','SH Older Wall','SH Seed Wall']}
require(all(all(sheet_lookup[r['source_sheet']][str(r['source_row'])][field]==value for field,value in r['values'].items()) for r in native),'All native values, including blank schema fields, match the supplied workbook tables')
sku_ids=defaultdict(set)
for o in model['offers']:
    if o['platform']=='Squarespace' and o['sku']:sku_ids[o['sku']].add(o['product_id'])
require(len(sku_ids['EBAY-188654649217'])==2,'Known duplicate SKU retains two distinct Squarespace product IDs')

def dbhash(b):return hashlib.sha256(b''.join(hashlib.sha256(b[i:i+4194304]).digest() for i in range(0,len(b),4194304))).hexdigest()
receipts={}
for filename in ['batch01_media.json','additional_source_receipts.json']:
    for r in json.loads((ev/filename).read_text()):
        if r.get('hash_verified'):receipts[r['id']]=r
prior=json.loads((ev/'image_review_curated_review.json').read_text())
for r in prior:
    if r.get('source') and r['source'].get('current_download_verified'):receipts.setdefault(r['source']['id'],r['source'])
verified_needed={r['asset_id'] for r in model['links'] if r['asset_id'] and (r['accepted_image'] or r.get('image_correspondence'))}
require(verified_needed<=set(receipts),'All accepted and confirmed gallery source images have current binary receipts')
for fid in sorted(verified_needed):
    r=receipts[fid];b=Path(r['local_path']).read_bytes()
    require(dbhash(b)==r['content_hash'] and hashlib.sha256(b).hexdigest()==r['sha256'],'Current source bytes verified '+fid)
for filename,count in [('batch01_media.json',13),('batch02_media.json',76)]:
    rows=json.loads((ev/filename).read_text());require(len(rows)==count and all(r.get('hash_verified') for r in rows),filename+' complete and binary verified')
require(len(model['designs'])==5 and len(model['reviewed_sculptures'])==11,'First two families have five design records and eleven finish records')
require(sum(f['assets'] for f in model['families'] if f['review_state']!='QUEUED')==89,'Both reviewed families account for all 89 current files')
require(all(not r['offer_keys'] or r['dimensions_cm'] for r in model['reviewed_sculptures']),'Reviewed source-linked finish records expose their available source dimensions')
require(all(r['export_body_matches_live'] and r['live_native_id_confirmed'] for r in json.loads((ev/'live_acanthus_verification.json').read_text())),'All four live Acanthus descriptions and native identities agree with source export')

ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
with zipfile.ZipFile(workbook) as z:
    require(z.testzip() is None,'Saved XLSX ZIP integrity')
    strings=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheets={}
    for s in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets',ns):
        target=rels[s.attrib['{'+ns['r']+'}id']]
        filename=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        tree=ET.fromstring(z.read(filename));cells={}
        for c in tree.findall('.//m:sheetData/m:row/m:c',ns):
            v=c.find('m:v',ns);value=v.text if v is not None else ''
            if c.attrib.get('t')=='s':value=strings[int(value)]
            elif c.attrib.get('t')=='inlineStr':value=''.join(c.find('m:is',ns).itertext())
            cells[c.attrib['r']]=value
        sheets[s.attrib['name']]=dict(tree=tree,cells=cells)
    require(len(sheets)==12,'All twelve output worksheets saved')
    expected_rows={'Family Review':(13,len(model['families'])),'Sculpture Register':(7,len(model['groups'])),'Reviewed Sculptures':(7,len(model['reviewed_sculptures'])),'Offers':(7,len(model['offers'])),'Offer Links':(7,len(model['links'])),'Source Specs':(7,len(model['facts'])),'Native Source Fields':(7,len(model['native_fields'])),'Assets':(7,len(model['assets'])),'Decisions':(7,len(model['issues'])),'Reference Notes':(7,len(model['reference_notes']))}
    for name,(start,count) in expected_rows.items():
        rows={int(a[1:]) for a in sheets[name]['cells'] if a.startswith('A') and a[1:].isdigit() and int(a[1:])>=start}
        require(rows==set(range(start,start+count)),name+' saved row-set matches current model')
    for i,r in enumerate(model['native_fields'],7):
        cells=sheets['Native Source Fields']['cells']
        require(cells['I'+str(i)]==r['raw_value'],'Saved exact native value part '+str(i-6))
    require([sheets['Family Review']['cells'][a] for a in ['B4','D4','F4','H4','B6','D6']]==[str(model['counts'][k]) for k in ['families','groups','assets','native_offers','groups_with_confirmed_image_links','specification_claims']],'Saved summary formula caches reconcile')
    errors=[(name,c.attrib['r']) for name,d in sheets.items() for c in d['tree'].findall('.//m:sheetData/m:row/m:c',ns) if c.attrib.get('t')=='e']
    require(not errors,'No saved Excel formula errors')

con=sqlite3.connect(checkpoint['state_database'])
for name,count in [('families',63),('groups',347),('assets',6656),('offers',127),('links',len(model['links'])),('facts',len(model['facts'])),('native_rows',349),('issues',len(model['issues'])),('designs',5),('reviewed_sculptures',11)]:require(con.execute(f'SELECT count(*) FROM {name}').fetchone()[0]==count,'State database '+name+' count reconciles')
con.close()
receipt=dict(status='PASS',verified_utc=datetime.now(timezone.utc).isoformat(),checks=len(checks),check_categories='Inventory membership; native fields and schema; source-specific image binaries; source-linked reviewed finishes; live Acanthus text and identity; saved XLSX rows, exact source text, formula caches and errors; state database; original workbook unchanged',workbook=str(workbook),workbook_sha256=hashlib.sha256(workbook.read_bytes()).hexdigest(),source_sha256=checkpoint['source_workbook_sha256'],counts=model['counts'],scope_limitations=['Inventory membership is complete; unreviewed media groups retain queued status.','Image correspondence and source statements do not establish measured physical specifications.','Main, older and seed Shopify data are preserved exports, not fresh live Shopify.','This increment covers wall sculptures; other product categories have not been recursively inventoried.'])
(ev/'validation_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
checkpoint.update(output=str(workbook.relative_to(project)),validation='evidence/validation_receipt.json',validation_status='PASS',last_verified_utc=receipt['verified_utc'])
(project/'checkpoint.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2))
with (project/'review_journal.jsonl').open('a') as f:f.write(json.dumps(dict(time=receipt['verified_utc'],event='REGISTER_EXPORT_VALIDATED',workbook_sha256=receipt['workbook_sha256'],checks=len(checks)))+'\n')
print(json.dumps(dict(status='PASS',checks=len(checks),workbook=str(workbook),sha256=receipt['workbook_sha256'],counts=model['counts'])))
