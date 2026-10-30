"""Correct six unsupported native hyperlink targets; author no cells or formulas."""
import hashlib,importlib.util,json,posixpath,zipfile
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
book=H/'master-workbook.pending';before=sha(book);data=n.load(book);plan=read(H/'workbook-edit-plan.json');links={(x['sheet'],x['cell']):x for x in plan['hyperlinks']};updated={};repairs=[]
for sn,info in data['sheets'].items():
 rp=posixpath.join(posixpath.dirname(info['part']),'_rels',posixpath.basename(info['part'])+'.rels');rels=E.fromstring(data['files'][rp]);rs={x.get('Id'):x for x in rels};changed=False
 for h in info['root'].findall('.//'+n.q('hyperlink')):
  key=(sn,h.get('ref'));expected=links[key]
  if h.get('location'):continue
  rel=rs[h.get('{'+n.R+'}id')]
  if rel.get('Target')!=expected['target']:
   repairs.append({'sheet':sn,'cell':h.get('ref'),'before':rel.get('Target'),'after':expected['target']});rel.set('Target',expected['target']);h.set('display',expected['label']);changed=True
 if changed:updated[rp]=E.tostring(rels,encoding='utf-8',xml_declaration=True);updated[info['part']]=E.tostring(info['root'],encoding='utf-8',xml_declaration=True)
assert {(x['sheet'],x['cell'])for x in repairs}=={('Listing Resolution','R15'),('Listing Resolution','S15'),('Draft Listings','I11'),('Draft Listings','J11'),('Selling Details','L15'),('Selling Details','M15')}
temp=H/'master-workbook.native-links-corrected'
with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED)as z:
 for p,v in data['files'].items():z.writestr(p,updated.get(p,v))
temp.replace(book)
expected=read(H/'expected-edit.json');expected['hyperlinks']=plan['hyperlinks'];(H/'expected-edit.json').write_text(json.dumps(expected,indent=2)+'\n')
after=n.load(book);assert data['values']==after['values']and data['formulas']==after['formulas']and data['styles']==after['styles']
(H/'native-link-correction.json').write_text(json.dumps({'status':'PASS','reason':'Final reference correction changed six destinations after the initial native-link snapshot. Corrected native feature only.','before_sha256':before,'after_sha256':sha(book),'repairs':repairs,'cell_formula_or_style_authoring':False},indent=2)+'\n');print('SIX_NATIVE_LINK_TARGETS_CORRECTED_NO_CELL_OR_FORMULA_CHANGES')
