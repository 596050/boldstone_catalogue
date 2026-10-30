"""Read back the saved comparison and compare every native field to the original XLSX."""
import hashlib,json,posixpath,zipfile
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET

project=Path(__file__).resolve().parents[1];ev=project/'evidence'
model=json.loads((ev/'platform_comparison_2026-10-16.json').read_text())
manifest=json.loads((ev/'platform_comparison_export.json').read_text())
original=project.parent/model['source_workbook'];output=Path(manifest['output'])
checks=[]
def require(value,label):
    assert value,label
    checks.append(label)
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def read_book(path,names):
    result={}
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(t.text or '' for t in si.findall('.//m:t',ns)) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets',ns):
            name=sheet.attrib['name']
            if name not in names:continue
            target=rels[sheet.attrib['{'+ns['r']+'}id']]
            member=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            root=ET.fromstring(z.read(member));rows={};errors=[]
            for row in root.findall('m:sheetData/m:row',ns):
                cells={}
                for cell in row.findall('m:c',ns):
                    t=cell.attrib.get('t');v=cell.find('m:v',ns);value=v.text if v is not None else ''
                    if t=='s':value=strings[int(value)]
                    elif t=='inlineStr':value=''.join(t.text or '' for t in cell.findall('.//m:t',ns))
                    if t=='e':errors.append((cell.attrib['r'],value))
                    letters=''.join(x for x in cell.attrib['r'] if x.isalpha());index=0
                    for char in letters:index=index*26+ord(char)-64
                    cells[index-1]=value or ''
                rows[int(row.attrib['r'])]=cells
            result[name]=dict(rows=rows,errors=errors)
    return result

source_names=['SS Wall Products','SS Wall Variants','SH Wall Products','SH Source Rows','SH Older Wall','SH Seed Wall']
source=read_book(original,source_names)
saved=read_book(output,list(manifest['sheets']))
require(hashlib.sha256(original.read_bytes()).hexdigest()==model['source_sha256'],'Original source workbook unchanged')
require(len(saved)==7,'All seven comparison worksheets exported')
require(not any(s['errors'] for s in saved.values()),'No saved Excel errors')
def original_value(sheet,row,field):
    headers=source[sheet]['rows'][5]
    col=next(k for k,v in headers.items() if v==field)
    return source[sheet]['rows'][int(row)].get(col,'')
def saved_value(sheet,row,col):return saved[sheet]['rows'].get(row,{}).get(col,'')

for name,info in manifest['sheets'].items():
    first=info['first'];expected=set(range(first,first+info['count']))
    rows={r for r,values in saved[name]['rows'].items() if r>=first and values.get(0,'')!=''}
    require(rows==expected,name+' row set is complete')
    require([saved_value(name,first-1,c) for c in range(len(info['headers']))]==info['headers'],name+' headers preserved')

for name,key,sheet,fields in [('Squarespace Records','ss_rows','SS Wall Variants',model['ss_schema']),('Shopify Records','sh_rows','SH Source Rows',model['sh_schema'])]:
    info=manifest['sheets'][name];prefix=info['prefix']
    for i,r in enumerate(model[key],info['first']):
        for c,field in enumerate(fields,prefix):
            expected=original_value(sheet,r['source_row'],field)
            require(saved_value(name,i,c)==expected,name+' '+r['row_key']+' / '+field)
    unique={(r['source_row'],r['csv_record']) for r in model[key]}
    require(len(unique)==len(model[key]),name+' native rows remain distinct')

info=manifest['sheets']['Historical Shopify']
for i,r in enumerate(model['historical'],info['first']):
    for c,field in enumerate(model['old_schema'],info['prefix']):require(saved_value('Historical Shopify',i,c)==original_value(r['source_sheet'],r['source_row'],field),'Historical '+r['record_key']+' / '+field)
    require(saved_value('Historical Shopify',i,2)==r['status'],'Historical relationship status '+r['record_key'])

matched_info=manifest['sheets']['Matched Products'];ssids=set();shhandles=set()
for i,r in enumerate(model['matches'],matched_info['first']):
    require(saved_value('Matched Products',i,1)==original_value('SS Wall Products',r['sq_source_row'],'SKU')==original_value('SH Wall Products',r['sh_source_row'],'Variant SKU'),'Exact native cross-platform SKU '+r['match_id'])
    require(saved_value('Matched Products',i,2)==original_value('SS Wall Products',r['sq_source_row'],'Title'),'Matched Squarespace title '+r['match_id'])
    require(saved_value('Matched Products',i,3)==original_value('SH Wall Products',r['sh_source_row'],'Title'),'Matched Shopify title '+r['match_id'])
    require(saved_value('Matched Products',i,4)==r['sq_id'] and saved_value('Matched Products',i,5)==r['sh_handle'],'Matched native identity '+r['match_id'])
    ssids.add(r['sq_id']);shhandles.add(r['sh_handle'])
require(len(ssids)==len(shhandles)==37,'37 unique main product pairs')
require(ssids.isdisjoint(r['sq_id'] for r in model['squarespace_only']),'Matched and unmatched Squarespace products are disjoint')
require(shhandles.isdisjoint(r['handle'] for r in model['shopify_only']),'Matched and unmatched Shopify products are disjoint')
require(len(ssids|{r['sq_id'] for r in model['squarespace_only']})==80,'All 80 Squarespace products classified')
require(len(shhandles|{r['handle'] for r in model['shopify_only']})==38,'All 38 main Shopify products classified')
for i,r in enumerate(model['squarespace_only'],manifest['sheets']['Squarespace Only']['first']):
    require(saved_value('Squarespace Only',i,0)==original_value('SS Wall Products',r['source_row'],'Title') and saved_value('Squarespace Only',i,1)==original_value('SS Wall Products',r['source_row'],'SKU') and saved_value('Squarespace Only',i,2)==r['sq_id'],'Squarespace unmatched identity '+r['sq_id'])
require([r['handle'] for r in model['shopify_only']]==['frozen-fish'],'Frozen Fish draft is the sole unmatched main Shopify record')
duplicate=[r for r in model['squarespace_only'] if r['sku']=='EBAY-188654649217']
require(len(duplicate)==2 and len({r['sq_id'] for r in duplicate})==2,'Two native products sharing a SKU remain separate')
expected_summary=[[80,37,43,223,37,186],[38,37,1,117,116,1]]
for row,expected in zip([6,7],expected_summary):
    require([saved_value('Matched Products',row,c) for c in range(1,7)]==[str(x) for x in expected],'Summary formula caches '+str(row))
require(model['counts']['all_native_rows']==349,'349 native rows across all versions retained')
require(model['counts']['historical_exact_sku_matches']==1 and model['counts']['historical_candidates']==8,'Archive exact match and eight candidates distinguished')
require(model['counts']['matched_title_agreements']==model['counts']['matched_description_agreements']==model['counts']['matched_price_agreements']==37,'Independent title, description and numeric-price comparison agrees for 37 main pairs')

mapping=json.loads((ev/'platform_dropbox_mapping_2026-10-16.json').read_text())
live=json.loads((ev/'platform_dropbox_live_metadata_2026-10-16.json').read_text())
heads={r['id']:r for r in live['entries']}
cache=json.loads((ev/'image_review_cache_index.json').read_text())
decisions={r['asset_id']:r for r in json.loads((ev/'established_image_decisions.json').read_text())}
info=manifest['sheets']['Dropbox Mapping'];columns={name:i for i,name in enumerate(info['headers'])}
require({r['match_id'] for r in mapping['records']}=={r['match_id'] for r in model['matches']},'Dropbox mapping covers exactly the 37 platform pairs')
for i,r in enumerate(mapping['records'],info['first']):
    for field,header in [('sku','Shared SKU'),('sq_id','Squarespace product ID'),('sh_handle','Shopify handle'),('status','Dropbox evidence level')]:
        require(saved_value('Dropbox Mapping',i,columns[header])==r[field],'Dropbox mapping '+r['match_id']+' '+field)
    for field,header in [('member_paths','Current member / arrangement path'),('member_folder_ids','Stable member folder ID'),('file_ids','Stable source file ID'),('family_paths','Current family-folder paths'),('family_ids','Stable family folder IDs'),('gallery_paths','Gallery-only folder reference'),('gallery_file_ids','Gallery-only source file ID')]:
        require(saved_value('Dropbox Mapping',i,columns[header])=='\n'.join(r[field]),'Dropbox mapping saved paths / IDs '+r['match_id']+' '+field)
    for fid,path in zip(r['family_ids'],r['family_paths']):require(heads[fid]['metadata_type']=='folder' and heads[fid]['path_display']==path,'Current family metadata '+fid)
    for fid,folder_id,path in zip(r['file_ids'],r['member_folder_ids'],r['member_paths']):
        require(heads[folder_id]['metadata_type']=='folder' and heads[folder_id]['path_display']==path,'Current member metadata '+folder_id)
        require(heads[fid]['path_display'].rsplit('/',1)[0].casefold()==path.casefold(),'Current source photo parent '+fid)
        require(cache[fid]['hash_verified'] and cache[fid]['sha256']==decisions[fid]['current_source_sha256'],'Current source photo hash matches visual review '+fid)
require([saved_value('Dropbox Mapping',row,col) for row,col in [(5,1),(5,3),(7,1),(7,3)]]==['37','13','20','4'],'Dropbox summary counts reconcile')

receipt=dict(status='PASS',verified_utc=datetime.now(timezone.utc).isoformat(),checks=len(checks),workbook=str(output),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),source_sha256=model['source_sha256'],counts=model['counts'],dropbox_mapping_counts=mapping['counts'],scope=model['scope'])
(ev/'platform_comparison_validation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
with (project/'review_journal.jsonl').open('a') as f:f.write(json.dumps(dict(time=receipt['verified_utc'],event='PLATFORM_COMPARISON_VALIDATED',workbook_sha256=receipt['sha256'],counts=model['counts']))+'\n')
print(json.dumps(receipt))
