"""Read-only checks of saved XLSX, lineage, scope and catalogue controls."""
import hashlib,json,re,zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as E
root=Path(__file__).resolve().parents[1];ev=root/'evidence'
d=json.loads((ev/'component_register.json').read_text());m=json.loads((ev/'component_workbook_manifest.json').read_text());inventory=json.loads((ev/'current_inventory.json').read_text());checks=0
refresh_path=ev/'dropbox-refresh-2026-10-17/bone_spiral_live_listing.json'
if d.get('updated_utc') and refresh_path.exists():
    refresh=json.loads(refresh_path.read_text());prefix='ns:202238505//BOLDSTONE MASTER/Products/01 Wall Sculptures/Bone Spiral/'
    inventory['entries']=[e for e in inventory['entries'] if not e['path'].startswith(prefix)] + [entry for child in refresh['children'] for entry in [child['folder'],*child['entries']]]
am_path=ev/'dropbox-refresh-2026-10-17/ammonite_live_listing.json'
if d.get('size_variants') and am_path.exists():
    am_refresh=json.loads(am_path.read_text());prefix='ns:202238505//BOLDSTONE MASTER/Products/01 Wall Sculptures/Ammonite/'
    inventory['entries']=[e for e in inventory['entries'] if not e['path'].startswith(prefix)] + [entry for child in am_refresh['children'] for entry in [child['folder'],*child['entries']]]
def check(condition,message):
    global checks
    assert condition,message
    checks+=1
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
z=zipfile.ZipFile(m['output']);shared=[]
if 'xl/sharedStrings.xml'in z.namelist():
    for si in E.fromstring(z.read('xl/sharedStrings.xml')):shared.append(''.join(t.text or ''for t in si.findall('.//s:t',ns)))
rels={n.attrib['Id']:n.attrib['Target'] for n in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))};book=E.fromstring(z.read('xl/workbook.xml'));sheets={}
for sh in book.findall('s:sheets/s:sheet',ns):
    target=rels[sh.attrib['{'+ns['r']+'}id']];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
    xml=E.fromstring(z.read(target));values={}
    for c in xml.findall('.//s:sheetData/s:row/s:c',ns):
        typ=c.get('t');v=c.find('s:v',ns)
        if typ=='s':value=shared[int(v.text)] if v is not None else ''
        elif typ=='inlineStr':value=''.join(t.text or ''for t in c.findall('.//s:t',ns))
        elif v is None:value=''
        elif typ in ['str','e']:value=v.text or ''
        else:
            try:value=float(v.text)
            except (ValueError,TypeError):value=v.text or ''
        check(typ!='e',f'Excel error {sh.attrib["name"]}!{c.get("r")}: {value}')
        values[c.attrib['r']]=value
    sheets[sh.attrib['name']]=values
check(len(sheets)==14,'Unexpected sheet count')
def col(n):
    s='';n+=1
    while n:n,a=divmod(n-1,26);s=chr(65+a)+s
    return s
for name,t in m['sheets'].items():
    if name=='Summary':continue
    values=sheets[name]
    for c,label in enumerate(t['headers']):check(values.get(col(c)+str(t['first']-1),'')==label,f'{name} header {c}')
    for rowno,row in enumerate(t['values'],t['first']):
        for c,want in enumerate(row):
            got=values.get(col(c)+str(rowno),'');check(got==want or (got in ['',None] and want in ['',None]),f'{name}!{col(c)}{rowno}: {got!r} != {want!r}')
for metric in m['sheets']['Summary']['metrics']:check(sheets['Summary'].get('B'+str(metric['row']))==metric['expected'],'Summary '+metric['label'])
fileids={a['id'] for a in d['assets']};groupids={g['id'] for g in d['groups']};compids={c['component_id'] for c in d['components']};offerrefs={p['offer_ref'] for p in d['platform_records']}
check(len(fileids)==d['counts']['files'],'Duplicate / missing asset IDs');check(len(groupids)==d['counts']['groups'],'Duplicate / missing group IDs');check(len(compids)==125,'Duplicate / missing component IDs')
check(fileids=={r['file_id']for r in inventory['entries']if r['object_type']=='file'},'Fresh inventory file set differs')
check(groupids<= {r['file_id']for r in inventory['entries']if r['object_type']=='folder'},'Folder absent from inventory')
for a in d['assets']:check(a['folder_id']in groupids,'Asset parent missing '+a['id']);check(bool(a['content_hash']),'Missing hash '+a['id'])
for g in d['groups']:
    check(g['files']==sum(a['folder_id']==g['id']for a in d['assets']),'Group file count '+g['id'])
    for fid in g['selected']:check(fid in fileids,'Representative ID absent')
    for cid in g['component_ids']:check(cid in compids,'Unknown group component')
    check(bool(g['component_ids']) or not g['files'] or any(u['folder_id']==g['id']for u in d['unresolved']),'Unmapped group omitted from unresolved queue '+g['name'])
for b in d['bom']:
    check(b['component_id']in compids and b['offer_ref']in offerrefs,'Broken BOM foreign key')
    for fid in b.get('example_file_ids','').splitlines():check(fid in fileids,'BOM file absent')
    for gid in b.get('folder_ids','').splitlines():check(gid in groupids,'BOM folder absent')
for coll,key in [('claims','claim_id'),('inferences',None),('unresolved_positions','position_id')]:
    rows=d[coll]
    if key:check(len({r[key]for r in rows})==len(rows),'Duplicate '+coll+' identifiers')
    for r in rows:
        if 'component_id'in r:check(r['component_id']in compids,'Unknown component in '+coll)
for p in d['platform_records']:
    if p.get('image_file_id'):check(p['image_file_id']in fileids and p['image_folder_id']in groupids,'Platform photograph lineage')
check(len([p for p in d['platform_records']if p.get('sh_handle') and p.get('sq_id')])==37,'37 platform pairs not preserved')
check(len({p['sq_id']for p in d['platform_records']if p.get('sq_id')})==80,'80 Squarespace IDs not preserved')
duplicate=[p for p in d['platform_records']if p.get('sku')=='EBAY-188654649217'];check(len(duplicate)==2 and len({p['sq_id']for p in duplicate})==2,'Distinct duplicated-SKU offers merged')
check(any(p['offer_ref']=='O015' and 'conflict'in p['image_state'] for p in d['platform_records']),'Concave / Water Catcher identity conflict hidden')
check(sum(c['identity_status']=='Documented or visually distinct design'for c in d['components'])==95,'Standard design count')
check(sum(c['identity_status'].startswith(('Visual','Bespoke'))for c in d['components'])==28,'Proposal count')
check(sum(not c['standalone_offer_refs']and not c['identity_status'].startswith(('Source-only','Concept'))for c in d['components'])==84,'Standalone gaps count')
check(len(d['aliases'])==10,'Rotation / numbering controls')
bone=[b for b in d['bom']if b['offer_ref']=='O034'];check([b['component_dimensions_source_cm']for b in bone]==['55 × 30 × 7','55 × 55 × 7'],'Bone Spiral unequal widths lost')
check(not any(b.get('component_weight')not in ['Not divided from set weight','Unknown',None]for b in d['bom']if not b.get('variant_id','').startswith('AM-')),'Set weight was allocated as component measurement')
source_path=Path('/Users/tprice/Documents/boldstone/Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx');check(hashlib.sha256(source_path.read_bytes()).hexdigest()==d['source_sha256'],'Original workbook changed')
if d.get('updated_utc'):
    before=json.loads((ev/'pre-bone-refresh-2026-10-17/component_register.json').read_text())
    for key in ['components','configurations','groups','assets','bom','inferences']:
        def untouched(x):return x.get('family')not in ['Bone Spiral','Ammonite'] and not x.get('component_id','').startswith(('BC-BONE-','BC-AM-')) and not (d.get('review_specification_drafts') and x.get('component_id')=='BC-AC-ONE') and x.get('folder_id')not in {'id:cnqzTNngPVsAAAAAAAyh_g','id:cnqzTNngPVsAAAAAAAyh_A'}
        check([x for x in d[key]if untouched(x)] == [x for x in before[key]if untouched(x)],'Unrelated model records changed: '+key)
    check([r for r in d['claims']if not r['claim_id'].startswith(('AMREFRESH-','AMPANEL-'))]==before['claims'],'Original source claims were changed')
    check(len(d['claims'])==d['counts']['specification_claims'],'Specification claim count')
    for key in ['aliases','unresolved','unresolved_positions','mixed_bindings','historical','document_sources']:
        check(d[key]==before[key], 'Unrelated evidence changed: '+key)
    check([p for p in d['platform_records'] if p['offer_ref']!='O034']==[p for p in before['platform_records'] if p['offer_ref']!='O034'],'Unrelated platform records changed')
    old_bone={c['component_id']:c for c in before['components'] if c['component_id']in ['BC-BONE-1','BC-BONE-2']}
    for c in d['components']:
        if c['component_id'] not in old_bone:continue
        for field in ['dimensions_available','weight_available','material_available','fixing_available','offer_refs','standalone_offer_refs','physical_specs_verified']:
            check(c[field]==old_bone[c['component_id']][field],'Bone Spiral source specification altered: '+field)
    live={entry['file_id']:entry for child in refresh['children'] for entry in [child['folder'],*child['entries']]}
    for a in d['assets']:
        if a['family']=='Bone Spiral':
            check(a['path']==live[a['id']]['path'],'Stale Bone Spiral file path')
    new_media=json.loads((ev/'dropbox-refresh-2026-10-17/bone_spiral_new_media.json').read_text())
    for a in new_media['files']:
        content=Path(a['local_path']).read_bytes()
        check(hashlib.sha256(content).hexdigest()==a['sha256'],'New source bytes changed')
        check(hashlib.sha256(b''.join(hashlib.sha256(content[i:i+4194304]).digest() for i in range(0,len(content),4194304))).hexdigest()==a['content_hash'],'Dropbox byte identity mismatch')
    check(len([a for a in d['assets'] if a['family']=='Bone Spiral'])==153,'Bone Spiral asset reconciliation')
    bone_classifications=[x for x in d['file_classifications']if any(c.startswith('BC-BONE-')for c in x['component_ids'])]
    check(len(bone_classifications)==78,'Bone Spiral file-specific observations')
    check(sum(x['visible_design_positions']==3 for x in bone_classifications)==12,'Garden arrangement multiplicity')
    check(sum(x['visible_design_positions']==2 and x['component_ids']==['BC-BONE-2'] for x in bone_classifications)==4,'Two-wide-panel arrangement multiplicity')
    check(len([c for c in d['components'] if c['family']=='Bone Spiral'])==2,'Repeated BS2 positions became new component records')
if d.get('size_variants'):
    baseline=json.loads((ev/'pre-ammonite-refresh-2026-10-17/component_register.json').read_text())
    check(len(d['size_variants'])==4 and {v['variant_id']for v in d['size_variants']}=={'AM-S1','AM-S2','AM-L1','AM-L2'},'Four Ammonite panel/size variants')
    check(len([c for c in d['components']if c['family']=='Ammonite'])==2,'Size variants became extra design records')
    live={e['file_id']:e for child in am_refresh['children']for e in [child['folder'],*child['entries']]}
    check(len([a for a in d['assets']if a['family']=='Ammonite'])==269,'Ammonite asset reconciliation')
    for a in d['assets']:
        if a['family']=='Ammonite':check(a['path']==live[a['id']]['path'],'Stale Ammonite path')
    for v in d['size_variants']:
        check(v['primary_file_id']in fileids and v['primary_folder_id']in groupids,'Variant stable IDs')
        check(next(a for a in d['assets']if a['id']==v['primary_file_id'])['folder_id']==v['primary_folder_id'],'Variant parent folder')
        check(not v['physical_specs_verified'] and v['individual_price']is None and v['availability']is None,'Variant inherited unapproved physical/price/stock values')
        bom=next(b for b in d['bom']if b.get('variant_id')==v['variant_id'])
        original=next(b for b in baseline['bom']if b['bom_id']==bom['bom_id'])
        for field in ['sq_id','sh_handle','sku','component_dimensions_source_cm','set_overall_cm','set_weight_kg','set_price']:
            check(bom[field]==original[field],'Native arrangement field changed: '+field)
        check(bom['folder_ids'].splitlines()[0]==v['primary_folder_id'],'BOM solo folder priority')
        check(('20 kg'in bom['component_weight']) if v['size_class']=='Large' else ('5.5 kg'in bom['component_weight']and '6.5 kg'in bom['component_weight']),'Each-component source estimates are size-specific')
        check(bom['offer_ref']==('O018'if v['size_class']=='Large'else 'O048'),'Large/small native offer crosswalk')
        for field in ['panel_dimensions','panel_material','panel_fixing','panel_suitability','panel_lead_time','panel_care_packaging','panel_sources','panel_gaps','panel_photos']:
            check(bool(bom.get(field)),'Panel specification field omitted: '+v['variant_id']+'/'+field)
        if v['size_class']=='Large':
            check('20–22 kg' in v['weight_available'],'Historical Size B weight missing from individual panel record')
            check('two LARGE' in v['fixing_available'],'Large panel received the small-panel fixing instruction')
        else:
            check('5–7 cm side depth' in v['dimensions_available'],'Historical small side depth omitted')
            check('one small stainless-steel' in v['fixing_available'],'Small panel fixing evidence omitted')
    for a in json.loads((ev/'dropbox-refresh-2026-10-17/ammonite_new_media.json').read_text())['files']:
        content=Path(a['local_path']).read_bytes();check(hashlib.sha256(content).hexdigest()==a['sha256'],'New Ammonite source bytes changed')
        check(hashlib.sha256(b''.join(hashlib.sha256(content[i:i+4194304]).digest()for i in range(0,len(content),4194304))).hexdigest()==a['content_hash'],'New Ammonite Dropbox content hash')
    check(len([r for r in d['claims']if r['claim_id'].startswith('AMREFRESH-')])==24,'New size-specific draft source claims')
    maker=next(r['values']for r in json.loads((ev/'evidence_index.json').read_text())['manufacturing_rows']if r['row']==93)
    new_claims=[r for r in d['claims']if r['claim_id'].startswith('AMPANEL-')]
    check(len(new_claims)==4,'Large-size construction/numbering source claims')
    for claim in new_claims:
        key=claim['source_ref'].split('row93/',1)[1]
        check(claim['value']==maker[key].strip(),'Maker Size B source wording changed')
if d.get('review_specification_drafts'):
    prior=json.loads((ev/'pre-acanthus-one-leaf-left-2026-10-17/component_register.json').read_text())
    for key in ['claims','platform_records','groups','assets','bom','file_classifications','aliases','unresolved','unresolved_positions','mixed_bindings','historical','document_sources','size_variants']:
        check(d[key]==prior[key],'One Leaf draft changed unrelated/source data: '+key)
    for key in ['components','configurations','inferences']:
        check([r for r in d[key]if r.get('component_id')!='BC-AC-ONE']==[r for r in prior[key]if r.get('component_id')!='BC-AC-ONE'],'One Leaf review changed another component: '+key)
    before=next(c for c in prior['components']if c['component_id']=='BC-AC-ONE')
    after=next(c for c in d['components']if c['component_id']=='BC-AC-ONE')
    check(after['name']=='Acanthus One Leaf Left','User name not applied')
    for key,value in before.items():
        if key!='name':check(after[key]==value,'Guessed value promoted into actual/source component field: '+key)
    draft=d['review_specification_drafts']['BC-AC-ONE']
    check(not draft['physical_specs_verified'] and not draft['proposals_approved'],'Estimates treated as verified or approved')
    proposals=[r for r in d['inferences']if r.get('proposal_id','').startswith('ACONELEFT-')]
    check(len(proposals)==7,'All seven requested guesses must be reviewable')
    check(len(d['inferences'])==len(prior['inferences'])+7==d['counts']['inference_records'],'Inference count does not reconcile')
    for row in proposals:
        check(row['status']=='DRAFT ESTIMATE / AWAITING USER CHECK','Guess not explicitly labelled')
        check(row['example_file_ids']=='id:cnqzTNngPVsAAAAAAAt-VQ','Guess attached to a collection rather than the reviewed solo image')
    platform=next(p['value']for p in draft['proposals']if p['proposal_id']=='ACONELEFT-PLATFORM')
    check(all(platform[k]is None for k in ['existing_squarespace_product_id','existing_shopify_handle','shared_sku']),'Invented existing platform identifier')
    availability=next(p['value']for p in draft['proposals']if p['proposal_id']=='ACONELEFT-AVAILABILITY')
    check(availability['physical_stock_quantity']is None and availability['lead_time']is None,'Invented stock quantity or lead time')
result=dict(status='PASS',checks=checks,output=m['output'],output_sha256=hashlib.sha256(Path(m['output']).read_bytes()).hexdigest(),counts=d['counts'],scope='Saved workbook value roundtrip; inventory ID lineage, source preservation, component counts, SKU and BOM scope controls. '+('Scoped Bone Spiral/Ammonite refreshes and unchanged other records verified. ' if d.get('updated_utc') else '')+('User One Leaf Left rename and seven separate unapproved guesses checked without changing source/stock/platform values. 'if d.get('review_specification_drafts')else'')+'This does not measure physical sculptures or independently prove visual interpretations.')
(ev/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
