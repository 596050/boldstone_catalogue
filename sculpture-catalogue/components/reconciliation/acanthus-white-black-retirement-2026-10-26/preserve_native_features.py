"""Keep original package features; insert only verified Artifact-authored payloads.

The Artifact round trip rewrites thousands of native hyperlink destinations and
loses differential-fill details. No semantic values are authored by this adapter.
"""
from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as E
import hashlib, importlib.util, io, json, os, zipfile

H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('reader',H/'verify_workbooks.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
N=reader.N
read=reader.read
sha=reader.sha
diagnostics=read(H/'raw-artifact-diagnostics.json')
assert not (H/'native-preservation-receipt.json').exists()
reports=[]
for plan, diagnostic in zip(read(H/'workbook-edit-plan.json')['plans'],diagnostics['workbooks']):
    assert plan['key']==diagnostic['key'] and not diagnostic['errors']
    out=Path(plan['output'])
    assert sha(out)==diagnostic['sha256']
    raw=H/(plan['key']+'-artifact-authored.xlsx')
    assert not raw.exists();raw.write_bytes(out.read_bytes())
    before, donor=reader.native.Book(plan['source']),reader.native.Book(raw)
    parts={p:before.zip.read(p) for p in before.zip.namelist()}
    strings=E.fromstring(donor.zip.read('xl/sharedStrings.xml')) if 'xl/sharedStrings.xml' in donor.zip.namelist() else None
    changes={(e['sheet'],e['cell']) for e in plan['edits']}
    cached={(e['sheet'],e['cell']) for e in diagnostic['formula_cache_changes']}
    modified=[];cells_transferred=0
    for name in before.sheets:
        required={r for sn,r in changes|cached if sn==name}
        if not required:continue
        path=before.sheets[name]
        root=E.fromstring(parts[path]);authored=E.fromstring(donor.zip.read(donor.sheets[name]))
        original_cells={c.get('r'):c for c in root.iter(N+'c')}
        donor_cells={c.get('r'):c for c in authored.iter(N+'c')}
        for ref in required:
            old=original_cells[ref];new=deepcopy(donor_cells[ref])
            # Each semantic edit/cache comes from the independently checked tool export.
            if new.get('t')=='s':
                item=deepcopy(strings[int(new.findtext(N+'v'))])
                item.tag=N+'is'
                new.remove(new.find(N+'v'));new.append(item);new.set('t','inlineStr')
            if old.get('s') is None:new.attrib.pop('s',None)
            else:new.set('s',old.get('s'))
            for key,value in old.attrib.items():
                if key not in {'t','s'}:new.set(key,value)
            parent=next(r for r in root.iter(N+'row') if old in list(r))
            idx=list(parent).index(old);parent.remove(old);parent.insert(idx,new)
            cells_transferred+=1
        if plan['key']=='comprehensive_workbook' and name=='Overview':
            target=next(r for r in root.iter(N+'row') if r.get('r')=='7')
            source=next(r for r in authored.iter(N+'row') if r.get('r')=='7')
            assert source.get('ht') in {'42','42.0'}
            target.set('ht',source.get('ht'));target.set('customHeight','1')
        for _,(prefix,uri) in E.iterparse(io.BytesIO(parts[path]),events=['start-ns']):
            if prefix not in {'ns0','ns1','ns2'}:E.register_namespace(prefix,uri)
        parts[path]=E.tostring(root,encoding='utf-8',xml_declaration=True)
        modified.append(path)
    # No dependency, table, hyperlink, styles, source strings, or unrelated sheet changes.
    for p in before.zip.namelist():
        if p not in modified:assert parts[p]==before.zip.read(p),p
    temp=out.with_suffix('.native-pending.xlsx')
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path,payload in parts.items():z.writestr(path,payload)
    os.replace(temp,out)
    reports.append({'key':plan['key'],'source_sha256':sha(plan['source']),'artifact_authored_snapshot':str(raw),
        'artifact_authored_sha256':sha(raw),'output':str(out),'output_sha256':sha(out),
        'authorized_semantic_edits':len(changes),'tool_authored_cells_or_caches_transferred':cells_transferred,
        'modified_worksheet_parts':modified,'untouched_package_parts_byte_identical':len(parts)-len(modified),
        'native_hyperlinks_styles_tables_and_other_parts_preserved':True,'adapter_semantic_authoring':False})
    before.close();donor.close()
receipt={'status':'NATIVE_FEATURES_PRESERVED_PENDING_INDEPENDENT_READBACK','workbooks':reports}
(H/'native-preservation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
