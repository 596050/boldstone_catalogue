"""Restore exact source timestamp labels after Artifact Tool ISO-date coercion.

The documented string-value API exports ISO strings as date cells even with
text number formatting. This narrow serialization adapter restores only the
three explicitly labelled UTC-text columns, after proving instant equality.
All other cells, formulas, links, styles and package parts remain unchanged.
"""
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as E
from collections import Counter
import hashlib,json,zipfile

W=Path(__file__).resolve().parent
d=json.loads((W/'workbook-data.json').read_text());target=Path(d['output'])
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
E.register_namespace('',S);E.register_namespace('r',R)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
before_hash=sha(target)
with zipfile.ZipFile(target) as z:parts={n:z.read(n) for n in z.namelist()}
original=dict(parts);changes=Counter();changed_parts=set()
allowed={'Dropbox files':{17,18},'Dropbox folders':{10}}
for k,t in enumerate(d['tabs'],1):
    if t['name'] not in allowed:continue
    part=f'xl/worksheets/sheet{k}.xml'
    root=E.fromstring(parts[part]);original_tree=E.tostring(root)
    restores=[]
    for cell in root.iter('{'+S+'}c'):
        if cell.get('t')!='d':continue
        addr=cell.get('r');letters=''.join(x for x in addr if x.isalpha())
        ri=int(''.join(x for x in addr if x.isdigit()))-7;ci=0
        for letter in letters:ci=ci*26+ord(letter)-64
        ci-=1
        assert ci in allowed[t['name']] and ri>=0,(t['name'],addr)
        source=t['rows'][ri][ci];v=cell.find('{'+S+'}v');saved=v.text
        assert isinstance(source,str) and datetime.fromisoformat(source.replace('Z','+00:00'))==datetime.fromisoformat(saved.replace('Z','+00:00'))
        assert cell.find('{'+S+'}f') is None
        restores.append((cell,v,saved));cell.set('t','str');v.text=source
        changes[t['name']]+=1
    parts[part]=E.tostring(root,encoding='utf-8',xml_declaration=True)
    for cell,v,saved in restores:cell.set('t','d');v.text=saved
    assert E.tostring(root)==original_tree
    changed_parts.add(part)
assert dict(changes)=={'Dropbox files':13378,'Dropbox folders':441},changes
for part in set(original)-changed_parts:assert parts[part]==original[part]
pending=target.with_suffix('.pending.xlsx')
with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for part,content in parts.items():z.writestr(part,content)
pending.replace(target)
r={'status':'PASS_EXACT_SOURCE_TIMESTAMP_TEXT_RESTORED','before_sha256':before_hash,'sha256':sha(target),
   'restored_cells':sum(changes.values()),'counts_by_sheet':dict(changes),
   'all_date_instants_verified_equal_before_restoration':True,
   'all_other_cells_links_formulas_and_styles_unchanged':True,
   'missing_capability_evidence':'date-probe.xlsx: both before/after @ number formats still export string ISO values as t=d; apostrophe changes literal value. Bounded export help lookup has no string-preservation option.'}
(W/'timestamp-text-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
