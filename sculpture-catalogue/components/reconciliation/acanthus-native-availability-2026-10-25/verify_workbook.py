"""Independent native-XLSX readback of the separately authored v3 workbook."""
from pathlib import Path
from decimal import Decimal
from urllib.parse import unquote
import argparse
import hashlib
import json
import posixpath
import zipfile
import xml.etree.ElementTree as ET

H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
M='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P='{http://schemas.openxmlformats.org/package/2006/relationships}'
def resolve(base,target):
    return target.lstrip('/')if target.startswith('/')else posixpath.normpath(posixpath.join(posixpath.dirname(base),target))
class Book:
    def __init__(self,path):
        self.path=Path(path);self.zip=zipfile.ZipFile(path)
        s=ET.fromstring(self.zip.read('xl/sharedStrings.xml'))if 'xl/sharedStrings.xml'in self.zip.namelist()else None
        self.strings=[]
        if s is not None:self.strings=[''.join(t.text or ''for t in si.iter(M+'t'))for si in s]
        wb=ET.fromstring(self.zip.read('xl/workbook.xml'))
        rels={e.attrib['Id']:e.attrib['Target']for e in ET.fromstring(self.zip.read('xl/_rels/workbook.xml.rels'))}
        self.sheets={s.attrib['name']:resolve('xl/workbook.xml',rels[s.attrib[R+'id']])for s in wb.find(M+'sheets')}
        self._cache={}
    def sheet(self,name):
        if name in self._cache:return self._cache[name]
        target=self.sheets[name];root=ET.fromstring(self.zip.read(target));cells={};links={}
        for c in root.iter(M+'c'):
            t=c.attrib.get('t');v=c.find(M+'v');f=c.find(M+'f');text=v.text if v is not None else None
            if f is not None:value=('formula',f.text or '')
            elif t=='s':value=('text',self.strings[int(text)])
            elif t=='inlineStr':value=('text',''.join(x.text or ''for x in c.iter(M+'t')))
            elif t=='b':value=('bool',text=='1')
            elif text is not None and t not in ('str','e'):
                try:value=('number',str(Decimal(text).normalize()))
                except Exception:value=(t or 'raw',text)
            elif text is not None:value=('text'if t=='str'else t,text)
            else:continue
            if value!=('text',''):cells[c.attrib['r']]=value
        rp=posixpath.join(posixpath.dirname(target),'_rels',posixpath.basename(target)+'.rels')
        rels={e.attrib['Id']:e.attrib.get('Target','')for e in ET.fromstring(self.zip.read(rp))}if rp in self.zip.namelist()else{}
        for link in root.iter(M+'hyperlink'):
            links[link.attrib['ref']]=rels.get(link.attrib.get(R+'id'), '#'+link.attrib.get('location',''))
        self._cache[name]=(cells,links);return cells,links
    def close(self):self.zip.close()
def run(output,report,metadata_allowlist=None):
    packet=read(H/'workbook-cutoff-packet.json');overlay=read(packet['overlay_path'])
    source=Path(packet['source_workbook']);assert sha(source)==packet['source_workbook_sha256']
    before=Book(source);after=Book(output)
    errors=[];changes=[];link_changes=[];new_cells=0;new_links=0;checked=0
    old_names=list(before.sheets);new_names=list(after.sheets)
    if [n for n in new_names if n in old_names]!=old_names:errors.append('Existing sheet order changed')
    if len(new_names)!=23 or set(new_names)-set(old_names)!={'Native Availability'}:errors.append('Expected22 retained sheets plus Native Availability')
    if new_names[0]!='Wall Sculptures':errors.append('Primary sheet changed')
    for name in old_names:
        if name not in after.sheets:errors.append('Missing sheet '+name);continue
        bc,bl=before.sheet(name);ac,al=after.sheet(name)
        for ref,value in bc.items():
            checked+=1
            if ac.get(ref)!=value:changes.append({'sheet':name,'cell':ref,'before':list(value),'after':list(ac[ref])if ref in ac else None})
        for ref,target in bl.items():
            checked+=1
            if al.get(ref)!=target:link_changes.append({'sheet':name,'cell':ref,'before':target,'after':al.get(ref)})
        new_cells+=len(set(ac)-set(bc));new_links+=len(set(al)-set(bl))
    allowed_metadata=read(metadata_allowlist)if metadata_allowlist else []
    allowed_coordinates={('Wall Sculptures','A6'),('Wall Sculptures','L11'),('Wall Sculptures','AC11'),('Wall Sculptures','AC12'),
        ('Products','AA8'),('Products','AA9'),('Products','AB8'),('Overview','C12'),('Guide and sources','B18')}
    for change in allowed_metadata:
        if (change['sheet'],change['cell'])not in allowed_coordinates or change['before'][0]!='text' or change['after'][0]!='text':
            errors.append('Metadata allowlist outside approved text-only scope')
    unexpected=[change for change in changes if change not in allowed_metadata]
    unused=[change for change in allowed_metadata if change not in changes]
    if unexpected:errors.append('Unapproved existing cell value changes')
    if unused:errors.append('Approved metadata changes do not match saved workbook')
    flower=next(r for r in overlay['rows']if r['file_id']=='id:cnqzTNngPVsAAAAAAAt4Uw')
    allowed_targets={flower['folder_url'],'http://127.0.0.1:8767/#BSI-C02D6DF365D3'}
    for x in link_changes:
        if x['sheet']not in {'Wall Sculptures','Products'} or x['after']not in allowed_targets or 'acanthus-flower-white__001.jpg'not in unquote(x['before']):
            errors.append('Unapproved existing hyperlink change '+x['sheet']+'!'+x['cell'])
    if not link_changes:errors.append('Deleted Flower current hyperlink was not redirected')
    native_values={v[1]for v in after.sheet('Native Availability')[0].values()if v[0]=='text'}if 'Native Availability'in after.sheets else set()
    for r in overlay['rows']:
        for key in ['file_id','revision_at_deletion','folder_id']:
            if r[key]not in native_values:errors.append('Missing native availability value '+r['file_id']+' '+key)
    primary=after.sheet('Wall Sculptures')[0]
    primary_text=[v[1]for v in primary.values()if v[0]=='text']
    for oid in ['BSI-C02D6DF365D3','BSI-9C7406B46836']:
        if oid not in primary_text:errors.append('Affected option row missing '+oid)
    out={'status':'PASS_V3_NATIVE_AVAILABILITY_WORKBOOK'if not errors else'NEEDS_REVIEW_V3_WORKBOOK',
        'source_workbook':str(source),'source_workbook_sha256':sha(source),
        'output_workbook':str(Path(output).resolve()),'output_workbook_sha256':sha(output),
        'overlay_sha256':sha(packet['overlay_path']),'review_event_cutoff':overlay['review_event_cutoff'],
        'source_sheet_count':len(old_names),'output_sheet_count':len(new_names),
        'source_cells_and_links_checked':checked,'existing_cell_value_changes':changes,
        'approved_metadata_text_changes':len(allowed_metadata),'source_or_specification_cell_changes':len(unexpected),
        'metadata_allowlist_sha256':sha(metadata_allowlist)if metadata_allowlist else None,
        'existing_hyperlink_changes':link_changes,'new_cells_in_retained_sheets':new_cells,
        'new_hyperlinks_in_retained_sheets':new_links,
        'output_hyperlinks':sum(len(after.sheet(n)[1])for n in new_names),
        'native_deletion_ids_and_revisions_present':not any('Missing native availability value'in e for e in errors),
        'errors':errors,'canonical_or_review_state_writes':0,'native_calls':0}
    before.close();after.close();Path(report).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items()if k not in ['existing_cell_value_changes','existing_hyperlink_changes']},ensure_ascii=False,indent=2))
    return 0 if not errors else 1
if __name__=='__main__':
    arg=argparse.ArgumentParser();arg.add_argument('--output',required=True,type=Path);arg.add_argument('--report',required=True,type=Path)
    arg.add_argument('--metadata-allowlist',type=Path);a=arg.parse_args()
    raise SystemExit(run(a.output,a.report,a.metadata_allowlist))
