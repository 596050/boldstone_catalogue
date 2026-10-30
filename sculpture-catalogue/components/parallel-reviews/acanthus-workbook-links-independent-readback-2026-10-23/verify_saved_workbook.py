import datetime, hashlib, json, posixpath, re, zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as E

HERE=Path(__file__).resolve().parent
CAT=HERE.parents[2]
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(ok,msg):
    if not ok:raise AssertionError(msg)
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def contents(path):
    cells={};links={};names=[]
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(n.itertext()) for n in E.fromstring(z.read('xl/sharedStrings.xml'))]
        wb=E.fromstring(z.read('xl/workbook.xml'))
        wr={r.attrib['Id']:r.attrib['Target'] for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sh in wb.find('m:sheets',NS):
            name=sh.attrib['name'];names.append(name)
            target=wr[sh.attrib['{'+NS['r']+'}id']]
            sp=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            sx=E.fromstring(z.read(sp))
            for c in sx.findall('m:sheetData/m:row/m:c',NS):
                typ=c.attrib.get('t','n');v=c.find('m:v',NS);raw=v.text if v is not None else None
                f=c.find('m:f',NS);formula=f.text if f is not None else None
                if typ=='s':value=('string',strings[int(raw)])
                elif typ=='inlineStr':value=('string',''.join(t.text or '' for t in c.findall('.//m:t',NS)))
                elif raw is None and formula is None:continue
                elif typ=='n' and raw is not None:
                    try:value=('number',str(Decimal(raw).normalize()))
                    except InvalidOperation:value=(typ,raw)
                else:value=(typ,raw)
                cells[(name,c.attrib['r'])]=(value,formula)
            rp=posixpath.dirname(sp)+'/_rels/'+posixpath.basename(sp)+'.rels'
            rels={r.attrib['Id']:r.attrib.get('Target','') for r in E.fromstring(z.read(rp))} if rp in z.namelist() else {}
            for h in sx.findall('m:hyperlinks/m:hyperlink',NS):
                rid=h.attrib.get('{'+NS['r']+'}id')
                dest=rels[rid] if rid in rels else '#'+h.attrib.get('location','')
                links[(name,h.attrib['ref'])]=dest
    return names,cells,links

pointer=load(CAT/'current-master.json');baseline_pointer=load(HERE/'pointer.before.json')
book=CAT/pointer['workbook'];start=sha(book)
check(start==pointer['workbook_sha256'],'Published workbook SHA')
check(start!=baseline_pointer['workbook_sha256'],'Acanthus correction not published yet')
packet=load(HERE.parent/'acanthus-master-photo-search-2026-10-23/workbook-folder-link-drift.json')
expected={(x['sheet'],x['cell']):x for x in packet['matched_stale_hyperlinks']}
check(len(expected)==22,'Correction target count')
names0,cells0,links0=contents(HERE/'workbook.before')
names1,cells1,links1=contents(book)
check(names0==names1,'Worksheet names/order changed')
check(cells0==cells1,'Workbook values or formulas changed')
check(set(links0)==set(links1),'Hyperlink locations changed')
diff={k:(links0[k],links1[k]) for k in links0 if links0[k]!=links1[k]}
check(set(diff)==set(expected),'Changed hyperlinks differ from22verified Acanthus targets')
for k,x in expected.items():
    check(links0[k]==x['saved_target'],'Baseline hyperlink mismatch')
    check(links1[k]==x['suggested_target'],'Corrected hyperlink mismatch')
check(not any(re.search(r'BOLDSTONE[_ ]BACKUP',unquote(v),re.I) for v in links1.values()),'Backup hyperlink')
check(not any('/BOLDSTONE MASTER/Products/01 Wall Sculptures/Acanthus Two Leaves Pewter/' in unquote(v) for v in links1.values()),'Obsolete Acanthus family prefix remains')
base_register=load(CAT/baseline_pointer['register']);register=load(CAT/pointer['register'])
check(register['options']==base_register['options'],'Option objects changed during link-only correction')
check(register['components']==base_register['components'],'Component definitions changed during link-only correction')
check(pointer['current_image_review_links']['counts']==baseline_pointer['current_image_review_links']['counts'],'Current photo totals changed')
check(sha(book)==start,'Workbook changed during readback')
out={'status':'PASS_PUBLISHED_22_ACANTHUS_LINK_CORRECTION','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'workbook':str(book),'workbook_sha256':start,'baseline_sha256':baseline_pointer['workbook_sha256'],'register_sha256':sha(CAT/pointer['register']),'worksheets_unchanged':len(names1),'cells_and_formulas_unchanged':len(cells1),'hyperlink_locations_unchanged':len(links1),'exact_verified_hyperlink_targets_changed':22,'all188option_objects_unchanged':True,'all112components_unchanged':True,'photo_counts_unchanged':True,'current_backup_hyperlinks':0,'canonical_writes':False,'workbook_export_performed':False,'dropbox_writes':False}
(HERE/'published-native-readback.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
