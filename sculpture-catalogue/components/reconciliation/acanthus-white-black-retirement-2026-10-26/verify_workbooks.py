"""Read saved OOXML independently; permit only the declared retirement edits."""
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone
from xml.etree import ElementTree as E
import hashlib, importlib.util, json, sys

H = Path(__file__).resolve().parent
BASE = H.parents[2]
spec = importlib.util.spec_from_file_location('native_reader', BASE/'components/reconciliation/acanthus-native-availability-2026-10-25/verify_workbook.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
N = native.M
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def structure(node):
    if node is None: return None
    return (node.tag, sorted(node.attrib.items()), node.text or '', [structure(c) for c in node])

def caches(book, name):
    root = E.fromstring(book.zip.read(book.sheets[name]))
    return {c.get('r'): (c.get('t'), c.findtext(N+'v','')) for c in root.iter(N+'c') if c.find(N+'f') is not None}

def run():
    result = []
    for plan in read(H/'workbook-edit-plan.json')['plans']:
        before, after = native.Book(plan['source']), native.Book(plan['output'])
        edits = {(e['sheet'],e['cell']): e for e in plan['edits']}
        errors, changed, links, features, style_changes, cache_changes = [], [], [], [], [], []
        checked = 0
        if list(before.sheets)!=list(after.sheets): errors.append('Original tabs/order changed')
        for name in before.sheets:
            bc, bl = before.sheet(name); ac, al = after.sheet(name)
            for ref in set(bc)|set(ac):
                checked += 1
                old, new = bc.get(ref), ac.get(ref)
                edit = edits.get((name,ref))
                expected = ('formula',edit['formula'].lstrip('=')) if edit and 'formula' in edit else ('text',edit['value']) if edit else old
                if new != expected: errors.append({'sheet':name,'cell':ref,'before':old,'expected':expected,'after':new})
                if old!=new: changed.append({'sheet':name,'cell':ref,'before':old,'after':new})
            for ref in set(bl)|set(al):
                checked += 1
                if bl.get(ref)!=al.get(ref): links.append({'sheet':name,'cell':ref,'before':bl.get(ref),'after':al.get(ref)})
            broot=E.fromstring(before.zip.read(before.sheets[name])); aroot=E.fromstring(after.zip.read(after.sheets[name]))
            for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','dataValidations','autoFilter','pageMargins','pageSetup','sheetProtection','conditionalFormatting','tableParts']:
                if [structure(c) for c in broot.findall(N+tag)] != [structure(c) for c in aroot.findall(N+tag)]: features.append(name+':'+tag)
            bstyles={c.get('r'):c.get('s','0') for c in broot.iter(N+'c')}; astyles={c.get('r'):c.get('s','0') for c in aroot.iter(N+'c')}
            for ref, value in bstyles.items():
                if astyles.get(ref,'0')!=value: style_changes.append(name+'!'+ref)
            br={r.get('r'):dict(r.attrib) for r in broot.iter(N+'row')}; ar={r.get('r'):dict(r.attrib) for r in aroot.iter(N+'row')}
            for ref, value in br.items():
                expected=dict(value)
                if plan['key']=='comprehensive_workbook' and name=='Overview' and ref=='7': expected.update(ht='42',customHeight='1')
                actual=ar.get(ref,{})
                # Number formatting of equivalent row heights is irrelevant.
                if 'ht' in expected and 'ht' in actual:
                    expected['ht']=str(Decimal(expected['ht']).normalize());actual['ht']=str(Decimal(actual['ht']).normalize())
                if expected!=actual: features.append(name+':row '+ref)
            bcache, acache=caches(before,name),caches(after,name)
            for ref in set(bcache)|set(acache):
                if bcache.get(ref)!=acache.get(ref): cache_changes.append({'sheet':name,'cell':ref,'before':bcache.get(ref),'after':acache.get(ref)})
            for c in aroot.iter(N+'c'):
                if c.get('t')=='e': errors.append('Saved formula error '+name+'!'+c.get('r')+' '+c.findtext(N+'v',''))
        for path in before.zip.namelist():
            if path.startswith('xl/tables/'):
                if path not in after.zip.namelist() or structure(E.fromstring(before.zip.read(path)))!=structure(E.fromstring(after.zip.read(path))): features.append(path)
        bs=E.fromstring(before.zip.read('xl/styles.xml')); ass=E.fromstring(after.zip.read('xl/styles.xml'))
        for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
            old,new=bs.find(N+group),ass.find(N+group)
            if old is not None and (new is None or len(new)<len(old) or any(structure(x)!=structure(y) for x,y in zip(old,new))): features.append('styles:'+group)
        for e in plan['expected']:
            root=E.fromstring(after.zip.read(after.sheets[e['sheet']]))
            cell=next(c for c in root.iter(N+'c') if c.get('r')==e['cell'])
            value=after.sheet(e['sheet'])[0][e['cell']]
            if value[0]=='formula':
                if Decimal(cell.findtext(N+'v','NaN'))!=Decimal(e['value']): errors.append('Cached result mismatch '+e['sheet']+'!'+e['cell'])
            elif str(value[1])!=str(e['value']): errors.append('Literal expected mismatch '+e['sheet']+'!'+e['cell'])
        if len(changed)!=len(plan['edits']):errors.append('Declared edit count mismatch')
        report={'key':plan['key'],'output':plan['output'],'sha256':sha(plan['output']),'source_sha256':sha(plan['source']),
            'source_cells_and_links_checked':checked,'declared_edits':len(edits),'actual_edits':len(changed),'changes':changed,
            'formula_count_before':sum(v[0]=='formula' for n in before.sheets for v in before.sheet(n)[0].values()),
            'formula_count_after':sum(v[0]=='formula' for n in after.sheets for v in after.sheet(n)[0].values()),
            'links':sum(len(after.sheet(n)[1]) for n in after.sheets),'hyperlink_changes':links,'style_index_changes':style_changes,
            'native_feature_changes':features,'formula_cache_changes':cache_changes,'errors':errors}
        report['status']='PASS' if not errors and not links and not features and not style_changes else 'NEEDS_REVIEW'
        result.append(report);before.close();after.close()
    report={'status':'PASS' if all(r['status']=='PASS' for r in result) else 'NEEDS_REVIEW','checked_utc':datetime.now(timezone.utc).isoformat(),'workbooks':result}
    target=H/('saved-workbook-verification.json' if '--final' in sys.argv else 'raw-artifact-diagnostics.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'workbooks':[{k:r[k] for k in ['key','sha256','source_cells_and_links_checked','declared_edits','actual_edits','formula_count_before','formula_count_after','links','status']}|{'errors':r['errors'][:10],'hyperlink_changes':len(r['hyperlink_changes']),'native_feature_changes':r['native_feature_changes'][:40],'style_index_changes':len(r['style_index_changes']),'formula_cache_changes':len(r['formula_cache_changes'])} for r in result]},ensure_ascii=False,indent=2))
    if '--final' in sys.argv and report['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':run()
