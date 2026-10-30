"""Restore native hyperlink targets and verify the saved artifact-tool workbook."""
import collections
import copy
import hashlib
import json
import posixpath
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as E

HERE=Path(__file__).resolve().parent
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
q=lambda t:'{'+S+'}'+t
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def load(p):
    with zipfile.ZipFile(p) as z:files={n:z.read(n) for n in z.namelist()}
    ss=[''.join(x.itertext()) for x in E.fromstring(files['xl/sharedStrings.xml'])] if 'xl/sharedStrings.xml' in files else []
    wr={r.get('Id'):r.get('Target') for r in E.fromstring(files['xl/_rels/workbook.xml.rels'])}
    sheets={}; values={}; formulas={}; styles={}
    for s in E.fromstring(files['xl/workbook.xml']).find(q('sheets')):
        target=wr[s.get('{'+R+'}id')];loc=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        name=s.get('name');root=E.fromstring(files[loc]);cells={};fs={};cs={}
        for c in root.iter(q('c')):
            addr=c.get('r');typ=c.get('t');v=c.find(q('v'));raw=v.text if v is not None and v.text else ''
            if typ=='s':value=ss[int(raw)]
            elif typ=='inlineStr':value=''.join(c.find(q('is')).itertext())
            elif typ=='b':value=raw=='1'
            elif typ in ['str','e']:value=raw
            elif raw:value=float(raw)
            else:value=''
            cells[addr]=value;cs[addr]=c.get('s','0')
            if c.find(q('f')) is not None:fs[addr]='='+(c.find(q('f')).text or '')
            assert typ!='e',f'Formula error: {name}!{addr} {value}'
        sheets[name]={'part':loc,'root':root,'attributes':dict(s.attrib)};values[name]=cells;formulas[name]=fs;styles[name]=cs
    return {'files':files,'sheets':sheets,'values':values,'formulas':formulas,'styles':styles,'style_root':E.fromstring(files['xl/styles.xml'])}

def attach():
    book=HERE/'master-workbook.pending';d=load(book);b=load(HERE/'inputs/master_workbook.before');exp=read(HERE/'expected-edit.json')
    links=collections.defaultdict(list)
    for h in exp['hyperlinks']:links[h['sheet']].append(h)
    assert len({(h['sheet'],h['cell']) for h in exp['hyperlinks']})==len(exp['hyperlinks'])
    updated={}
    late={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
    for n,info in d['sheets'].items():
        loc=info['part'];root=info['root']
        node=root.find(q('hyperlinks'))
        if node is not None:root.remove(node)
        relpath=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
        rels=E.fromstring(d['files'][relpath]) if relpath in d['files'] else E.Element('{'+P+'}Relationships')
        for r in list(rels):
            if r.get('Type','').endswith('/hyperlink'):rels.remove(r)
        node=E.Element(q('hyperlinks'));idx=next((i for i,x in enumerate(root) if x.tag.split('}')[-1] in late),len(root));root.insert(idx,node)
        used={r.get('Id') for r in rels}
        for i,h in enumerate(links[n],1):
            x=E.SubElement(node,q('hyperlink'),ref=h['cell'],display=str(h['label']))
            if h['target'].startswith('#'):x.set('location',h['target'][1:])
            else:
                rid='rIdPhotoLink'+str(i);assert rid not in used
                x.set('{'+R+'}id',rid)
                E.SubElement(rels,'{'+P+'}Relationship',Id=rid,Type=R+'/hyperlink',Target=h['target'],TargetMode='External')
        updated[loc]=E.tostring(root,encoding='utf-8',xml_declaration=True)
        updated[relpath]=E.tostring(rels,encoding='utf-8',xml_declaration=True)
    # Export drops solid-pattern attributes in differential formats. Restore the
    # unchanged original rule and the explicit solid fill authored on new rules.
    dx=d['style_root'].find(q('dxfs'));old=b['style_root'].find(q('dxfs'))
    restored=0
    if old is not None:
        for i,x in enumerate(old):dx.remove(dx[i]);dx.insert(i,copy.deepcopy(x));restored+=1
    for x in dx.iter(q('patternFill')):
        if not x.get('patternType') and (x.find(q('bgColor')) is not None or x.find(q('fgColor')) is not None):x.set('patternType','solid')
    updated['xl/styles.xml']=E.tostring(d['style_root'],encoding='utf-8',xml_declaration=True)
    tmp=HERE/'master-workbook.native-pending'
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in d['files'].items():z.writestr(name,updated.pop(name,raw))
        for name,raw in updated.items():z.writestr(name,raw)
    tmp.replace(book)
    return restored

def verify():
    book=HERE/'master-workbook.pending';a=load(book);b=load(HERE/'inputs/master_workbook.before');expected=read(HERE/'expected-edit.json');plan=read(HERE/'workbook-edit-plan.json');audit=read(HERE/'image-coverage-audit.json');g=read(HERE/'canonical-master-register.json');oldg=read(HERE/'inputs/master_register.before')
    changes={(x['sheet'],x['cell']):x for x in plan['cell_changes']};issues=[];checks=0
    def check(ok,msg):
        nonlocal checks
        checks+=1
        if not ok:issues.append(msg)
    check(list(a['sheets'])==list(b['sheets'])+list(expected['sheets']),'Original tabs kept in order and four audit tabs added')
    for n,info in b['sheets'].items():
        after=a['sheets'][n]['root'];before=info['root']
        check(a['formulas'][n]==b['formulas'][n],n+' original formulas unchanged')
        for c,v in b['values'][n].items():
            target=changes.get((n,c),{}).get('value',v)
            check(a['values'][n].get(c,'')==target,f'{n}!{c} preserved/planned value')
            if (n,c) not in changes:check(a['styles'][n].get(c,'0')==b['styles'][n][c],f'{n}!{c} original cell style')
        for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins']:
            check([E.tostring(x) for x in before.findall(q(tag))]==[E.tostring(x) for x in after.findall(q(tag))],n+' native '+tag)
        def table_targets(data,sheet):
            loc=sheet['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
            rels={r.get('Id'):r.get('Target') for r in E.fromstring(data['files'][rp])}
            result=[]
            for t in sheet['root'].findall('.//'+q('tablePart')):
                target=rels[t.get('{'+R+'}id')]
                part=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(loc)+'/'+target)
                result.append(data['files'][part])
            return result
        check(table_targets(b,info)==table_targets(a,a['sheets'][n]),n+' native table relationships resolve to identical tables')
        check([r.attrib for r in before.find(q('sheetData'))]==[r.attrib for r in after.find(q('sheetData'))],n+' original row heights and attributes')
    for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
        before=b['style_root'].find(q(group));after=a['style_root'].find(q(group))
        check(before is None or after is not None and all(E.tostring(x)==E.tostring(y) for x,y in zip(before,after)),group+' original definitions preserved')
    tables=[x for x in b['files'] if x.startswith('xl/tables/')]
    check(all(a['files'].get(x)==b['files'][x] for x in tables),'All nine original tables and filters byte identical')
    for n,view in expected['sheets'].items():
        cells=a['values'][n]
        for j,h in enumerate(view['headers']):check(cells.get(column(j)+'9','')==h,n+' header')
        for i,row in enumerate(view['rows'],10):
            for j,v in enumerate(row):check(cells.get(column(j)+str(i),'')==v,f'{n}!{column(j)}{i} audit data')
        root=a['sheets'][n]['root'];check(root.find('.//'+q('pane')) is not None,n+' frozen identifiers/headers')
        check(len(root.findall('.//'+q('tablePart')))==1,n+' filterable table')
    for f in expected['formulas']:
        check(a['formulas'][f['sheet']].get(f['cell'])==f['formula'],'New summary formula')
        check(a['values'][f['sheet']].get(f['cell'])==f['expected'],'New summary cached result')
    actual_links={}
    for n,info in a['sheets'].items():
        loc=info['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
        rels={r.get('Id'):r for r in E.fromstring(a['files'][rp])}
        for h in info['root'].findall('.//'+q('hyperlink')):
            url='#'+h.get('location') if h.get('location') else rels[h.get('{'+R+'}id')].get('Target')
            actual_links[(n,h.get('ref'))]=url
    check(len(actual_links)==len(expected['hyperlinks']),'All current native hyperlinks retained/added')
    for h in expected['hyperlinks']:
        check(actual_links.get((h['sheet'],h['cell']))==h['target'],'Native hyperlink destination')
        check(a['values'][h['sheet']].get(h['cell'],'')==h['label'],'Native hyperlink label')
    check(g['summary']==oldg['summary'],'No identity or option count changed')
    check(g['original_review_specification_assertions']==oldg['original_review_specification_assertions'],'1668 original source assertions preserved')
    check(all(x['master_fields']==y['master_fields'] and x['product_id']==y['product_id'] and x['name']==y['name'] for x,y in zip(g['options'],oldg['options'])),'All accepted names and 1104 current specification groups preserved')
    check(len({x['option_id'] for x in audit['coverage']})==184,'All 184 options covered exactly once')
    check(audit['counts']['individual_statuses']=={'Available':157,'Detail only':5,'Group only':21,'Unbound size':1},'Individual image gap reconciliation')
    check(len([x for x in audit['missing_pictures'] if x['role']=='Individual'])==27,'27 individual-image actions')
    check(all(x['reference'] and x['reference']['file_id'] and x['reference']['folder_id'] for x in audit['missing_pictures']),'Every picture action has example and stable file/folder IDs')
    check(all(x['reference'] and x['reference']['file_id'] and x['reference']['folder_id'] for x in audit['identity_review']),'Every identity position has example and stable IDs')
    check(g['options'][81].get('file_id') in [None,''] and not audit['coverage'][81]['individual']['exact_option'],'Long Fish remains exact-photo unbound')
    check(all(x['dropbox_exact_image_binding']=='NO_EXACT_BYTE_MATCH_IN_CURRENT_CHECK' for x in g['wall_circle_native_options']),'Visual swatch comparisons do not upgrade exact-byte source claims')
    check(sum(len(x['variant_ids']) for x in audit['wall_circle_sources'])==144,'18 image bindings preserve 144 source variants')
    for i,c in enumerate(audit['primary_reference_changes'],1):
        md=read(HERE/f'recovered-primary-metadata-{i}.json')['structuredContent']['file'];r=c['new'];asset=read(HERE/'asset-index.json')[r['file_id']]
        check(md['id']==r['file_id'] and md['path_display']==asset['display_path'] and md['size']==asset['bytes'],'Fresh recovered-image metadata')
    check(a['values']['Wall Circle Sources']['M10']==46312.0,'Source snapshot date typed as Excel date')
    check(sum(len(x) for x in a['formulas'].values())==sum(len(x) for x in b['formulas'].values())+len(expected['formulas']),'Only planned summary formulas added')
    result={'status':'PASS' if not issues else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:60],
       'workbook_sha256':digest(book),'register_sha256':digest(HERE/'canonical-master-register.json'),'audit_sha256':digest(HERE/'image-coverage-audit.json'),
       'original_sheet_count':9,'new_sheet_count':4,'original_tables_preserved':9,'all_unrelated_original_cells_formulas_styles_and_native_features_preserved':not issues,
       'native_hyperlinks':len(actual_links),'formula_count':sum(len(x) for x in a['formulas'].values()),'counts':audit['counts'],'native_link_and_differential_fill_fallback':True,
       'unchanged_sheet_visuals':'Prior original-sheet visual QA reused only where rendered content and dependencies are unchanged. Changed examples and new audit sheets rendered separately.'}
    write(HERE/'saved-file-verification.json',result)
    print(json.dumps({k:result[k] for k in ['status','checks','issues','native_hyperlinks','formula_count']}))
    if issues:raise SystemExit(1)

def column(n):
    s=''
    while n>=0:n,r=divmod(n,26);s=chr(65+r)+s;n-=1
    return s

if __name__=='__main__':
    import sys
    if '--attach' in sys.argv:attach()
    verify()
