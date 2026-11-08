"""Read back the private Google-native export and the public feed independently."""
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as E
import zipfile
from pathlib import Path
sys.path.insert(0,'/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook
sys.path.insert(0,'/Users/tprice/Documents/boldstone/catalogue-review/scripts')
from import_saatchi_snapshot import Xlsx,NS,column

OUT=Path(__file__).parent
read=lambda name:json.loads((OUT/name).read_text())
source=CalamineWorkbook.from_path(str(OUT/'catalogue_wall_sculptures.xlsx'))
native=CalamineWorkbook.from_path(str(OUT/'google-native-master-backup.xlsx'))
assert source.sheet_names==native.sheet_names
differences=[];checked=0;nonblank=0
def value(rows,r,c):
    return rows[r][c] if r<len(rows) and c<len(rows[r]) and rows[r][c] is not None else ''
def equal(a,b):
    if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7)
    return a==b
for sheet in source.sheet_names:
    before=source.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
    after=native.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
    for r in range(max(len(before),len(after))):
        columns=max(len(before[r]) if r<len(before) else 0,len(after[r]) if r<len(after) else 0)
        for c in range(columns):
            a,b=value(before,r,c),value(after,r,c)
            checked+=1;nonblank+=a!=''
            if not equal(a,b):differences.append(dict(sheet=sheet,row=r+1,column=c+1,source=str(a)[:250],native=str(b)[:250]))
(OUT/'google-native-differences.json').write_text(json.dumps(differences,indent=2)+'\n')
old_xml=Xlsx(OUT/'catalogue_wall_sculptures.xlsx');native_xml=Xlsx(OUT/'google-native-master-backup.xlsx')
links=lambda book,sheet:{h.get('ref'):h.attrib for h in E.fromstring(book.parts[book.paths[sheet]]).findall('s:hyperlinks/s:hyperlink',NS)}
old_links,native_links=links(old_xml,'Wall Sculptures'),links(native_xml,'Wall Sculptures')
display_changes=[];rounding_changes=[];unexpected=[]
from decimal import Decimal,ROUND_CEILING
for diff in differences:
    address=column(diff['column'])+str(diff['row'])
    if diff['sheet']=='Wall Sculptures' and diff['column']==46:
        before_link,after_link=old_links.get(address),native_links.get(address)
        if before_link and after_link and before_link.get('display')==diff['native'] and before_link.get('location')==after_link.get('location'):
            display_changes.append(dict(cell=address,display=diff['native'],location=after_link['location']))
            continue
    if diff['sheet']=='Wall Sculptures' and diff['column']==479 and 8<=diff['row']<=188:
        row=diff['row'];floor=Decimal(str(old_xml.value('Wall Sculptures','RJ'+str(row))));discount=Decimal(str(old_xml.value('Wall Sculptures','QO4')))
        exact=(floor/(1-discount)).quantize(Decimal('.01'),rounding=ROUND_CEILING)
        assert Decimal(diff['native'])==exact and abs(Decimal(diff['source'])-exact)==Decimal('.01')
        assert old_xml.formula('Wall Sculptures',address)==f'ROUNDUP(RJ{row}/(1-$QO$4),2)'
        f=native_xml.cells['Wall Sculptures'][address].find('s:f',NS);assert f is not None
        if f.text:expr=f.text
        else:
            si=f.get('si');anchor,formula=next((a,c.find('s:f',NS)) for a,c in native_xml.cells['Wall Sculptures'].items() if c.find('s:f',NS) is not None and c.find('s:f',NS).get('si')==si and c.find('s:f',NS).text)
            delta=row-int(re.sub(r'\D','',anchor))
            expr=re.sub(r'(\$?[A-Z]+)(\$?)(\d+)',lambda m:m[1]+m[2]+str(int(m[3])+(0 if m[2] else delta)),formula.text)
        assert expr==old_xml.formula('Wall Sculptures',address)
        rounding_changes.append(diff)
        continue
    unexpected.append(diff)
assert not unexpected,unexpected[:8]
assert len(display_changes)==181 and 3<=len(rounding_changes)<=181
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
formula_counts={};table_counts={};errors=[]
for name in ['catalogue_wall_sculptures.xlsx','google-native-master-backup.xlsx']:
    with zipfile.ZipFile(OUT/name) as archive:
        formula_counts[name]=0
        table_counts[name]=sum(bool(re.fullmatch(r'xl/tables/table\d+\.xml',part)) for part in archive.namelist())
        for part in archive.namelist():
            if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',part):
                tree=E.fromstring(archive.read(part))
                formula_counts[name]+=len(tree.findall('.//s:f',ns))
                errors.extend(dict(file=name,part=part,cell=c.get('r'),error=c.find('s:v',ns).text) for c in tree.findall('.//s:c',ns) if c.get('t')=='e')
assert not errors,errors[:5]
assert len(set(formula_counts.values()))==1
assert len(set(table_counts.values()))==1
plan=read('plan.json');public=read('pinterest-google-native-readback.json')['values']
assert public[0]==plan['pinterest_feed_fields'] and len(public)==177
for r,record in enumerate(plan['public_feed_rows'],1):
    for c,key in enumerate(plan['pinterest_feed_fields']):
        assert str(public[r][c] if c<len(public[r]) else '')==str(record[key]),(r,key)
assert all(not record['GTIN'] and not record['mpn'] for record in plan['public_feed_rows'])
receipt=dict(status='PASS',owner='info@boldstone.co.uk',master_private=True,
    source_master_sha256=hashlib.sha256((OUT/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest(),
    native_backup_sha256=hashlib.sha256((OUT/'google-native-master-backup.xlsx').read_bytes()).hexdigest(),
    native_url=read('google-sheet-destinations.json')['master_url'],sheets=source.sheet_names,
    cells_compared=checked,nonblank_values_checked=nonblank,unexpected_value_differences=0,formula_counts=formula_counts,
    preserved_internal_hyperlinks_with_native_display_labels=display_changes,
    native_engine_rounding_differences=rounding_changes,
    native_table_counts=table_counts,formula_errors=0,public_feed_rows=176,public_feed_columns=46,
    public_feed_all_cells_matched=True,no_unverified_gtins_or_mpns=True,
    owner_evidence='google-master-owner-private.txt',scope='Google-native export readback, not merely the authored input file')
(OUT/'google-master-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
