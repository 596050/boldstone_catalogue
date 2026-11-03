"""Join a supplied Saatchi snapshot to existing components by native artwork ID.

This imports dated observations only. It does not change app specifications or
publish to Saatchi. XLSX authoring is handled by the artifact-tool builder.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from prepare_saatchi_catalogue import native_artwork_bindings

U='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'s':U};Q=lambda x:'{'+U+'}'+x

def column(n):
    s=''
    while n:n,d=divmod(n-1,26);s=chr(65+d)+s
    return s

def column_index(s):
    n=0
    for c in re.sub(r'\d','',s):n=n*26+ord(c)-64
    return n

class Xlsx:
    def __init__(self,path):
        self.path=Path(path)
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            self.parts={n:z.read(n) for n in z.namelist()}
        self.shared=[''.join(t.text or '' for t in e.iter(Q('t'))) for e in ET.fromstring(self.parts['xl/sharedStrings.xml'])] if 'xl/sharedStrings.xml' in self.parts else []
        rel={e.get('Id'):'xl/'+e.get('Target').lstrip('/').removeprefix('xl/') for e in ET.fromstring(self.parts['xl/_rels/workbook.xml.rels'])}
        self.paths={e.get('name'):rel[e.get('{'+R+'}id')] for e in ET.fromstring(self.parts['xl/workbook.xml']).find('s:sheets',NS)}
        self.cells={name:{c.get('r'):c for c in ET.fromstring(self.parts[p]).findall('s:sheetData/s:row/s:c',NS)} for name,p in self.paths.items()}

    def value(self,sheet,address):
        c=self.cells[sheet].get(address)
        if c is None:return None
        if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(Q('t')))
        v=c.find('s:v',NS);s=v.text if v is not None else ''
        if c.get('t')=='s':return self.shared[int(s)]
        if c.get('t')=='b':return s=='1'
        if c.get('t')=='e':raise ValueError(f'Excel error {sheet}!{address}: {s}')
        if c.get('t','n')=='n' and s:
            f=float(s);return int(f) if f.is_integer() else f
        return s

    def formula(self,sheet,address):
        c=self.cells[sheet].get(address);f=c.find('s:f',NS) if c is not None else None
        return f.text if f is not None else None

    def rows(self,sheet,start):
        end=max(int(re.search(r'\d+',a).group()) for a in self.cells[sheet])
        return range(start,end+1)

def slug(s):
    if s=='#':return 'record_number'
    s=s.replace('US$',' USD ').replace('£',' GBP ').replace('$',' USD ')
    return re.sub(r'[^a-z0-9]+','_',s.casefold()).strip('_')

def artwork_records(source):
    headers=[source.value('Artworks',column(n)+'1') for n in range(1,61)]
    assert all(isinstance(h,str) and h for h in headers) and len(set(headers))==60
    records=[]
    for n in source.rows('Artworks',2):
        row={h:source.value('Artworks',column(i+1)+str(n)) for i,h in enumerate(headers)}
        if row['Artwork ID'] in (None,''):continue
        row['Artwork ID']=str(row['Artwork ID'])
        assert row['Artwork ID'].isdigit()
        assert '/'+row['Artwork ID']+'/view' in row['Public listing']
        assert '/art/'+row['Artwork ID']+'/overview' in row['Studio page']
        assert '-A'+row['Artwork ID']+'-' in row['Saatchi SKU']
        row['_source_row']=n;records.append(row)
    assert len({r['Artwork ID'] for r in records})==len(records)
    return headers,records

def prepare(out,source_path):
    read=lambda n:json.loads((out/n).read_text())
    write=lambda n,v:(out/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
    source=Xlsx(source_path);master=Xlsx(out/'previous-catalogue.xlsx')
    assert list(source.paths)==['Artworks','Shipping by destination','Notes']
    headers,observed=artwork_records(source)
    app=read('app-after.json');products={p['id']:p for p in app['products']}
    fields={p['id']:{f['key']:f['value'] for f in p['fields']+p['listing_fields']} for p in app['products']}
    sku_to_pid={fields[pid]['Seller SKU']:pid for pid in products}
    assert len(sku_to_pid)==len(products)
    native=native_artwork_bindings(ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
    native_to_sku={v:k for k,v in native.items()};assert len(native_to_sku)==len(native)
    rows={master.value('Wall Sculptures',f'AA{n}'):n for n in range(8,189)}
    assert set(rows)==set(products)
    existing={master.value('Wall Sculptures',a):re.sub(r'\d','',a) for a in master.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',a)}
    assert len(existing)==len({h.casefold() for h in existing})
    assert not any(h.startswith('saatchi_') for h in existing),'Existing Saatchi fields need a deliberate refresh, not another import'
    first=max(column_index(c) for c in existing.values())+1
    meta=['saatchi_snapshot_scope','saatchi_source_file','saatchi_source_date','saatchi_source_sha256','saatchi_match_basis',
          'saatchi_catalogue_sku','saatchi_update_state','saatchi_source_gbp_per_usd','saatchi_source_artist_share']
    mapped={h:'saatchi_observed_'+slug(h) for h in headers}
    shipping={}
    for c in range(5,21,2):
        group=source.value('Shipping by destination',column(c)+'2')
        assert group and source.value('Shipping by destination',column(c)+'3')=='Shipping'
        shipping[c]='saatchi_observed_shipping_'+slug(group)+'_usd'
        shipping[c+1]='saatchi_observed_list_price_'+slug(group)+'_usd'
    added=meta+list(mapped.values())+list(shipping.values())
    assert len(added)==len({h.casefold() for h in added}) and not set(added)&set(existing)
    allheaders={**existing,**{h:column(first+i) for i,h in enumerate(added)}}
    rate=source.value('Notes','B5');share=source.value('Notes','B6')
    assert isinstance(rate,(int,float)) and rate>0 and 0<share<1
    values={pid:{'saatchi_snapshot_scope':'Not included in the supplied Saatchi snapshot'} for pid in products}
    matches,unmatched=[],[]
    digest=hashlib.sha256(source.path.read_bytes()).hexdigest()
    shipping_by_id={}
    for n in source.rows('Shipping by destination',4):
        native_id=source.value('Shipping by destination','B'+str(n))
        if native_id in (None,''):continue
        native_id=str(native_id)
        assert native_id not in shipping_by_id
        shipping_by_id[native_id]={'source_row':n,'values':{shipping[c]:source.value('Shipping by destination',column(c)+str(n)) for c in shipping}}
    assert set(shipping_by_id)=={r['Artwork ID'] for r in observed}
    for record in observed:
        native_id=record['Artwork ID'];sku=native_to_sku.get(native_id);pid=sku_to_pid.get(sku)
        if not pid:
            unmatched.append({'artwork_id':native_id,'source_row':record['_source_row'],'title':record['Title'],'reason':'No unambiguous native-ID to current catalogue SKU binding'})
            continue
        assert all(r['catalogue_id']!=pid for r in matches),'Multiple Saatchi artworks for one component require separate handling'
        source_row=record['_source_row'];shiprow=shipping_by_id[native_id]['source_row']
        assert source.value('Shipping by destination','C'+str(shiprow))==record['Title']
        assert source.value('Shipping by destination','D'+str(shiprow))==record['Artwork price (US$)']
        data={mapped[h]:record[h] for h in headers}
        data.update(shipping_by_id[native_id]['values'])
        data.update(saatchi_snapshot_scope='Matched by existing native artwork ID and exact catalogue SKU',
            saatchi_source_file=source_path.name,saatchi_source_date='2026-11-03',saatchi_source_sha256=digest,
            saatchi_match_basis='Saved Saatchi artwork-ID binding → current Seller SKU; no title-based identity inference',
            saatchi_catalogue_sku=sku,saatchi_update_state='Imported supplied snapshot only. Core catalogue and live Saatchi listings unchanged.',
            saatchi_source_gbp_per_usd=rate,saatchi_source_artist_share=share)
        values[pid]=data
        matches.append({'platform':'saatchi','artwork_id':native_id,'catalogue_id':pid,'sku':sku,'source_row':source_row,
                        'shipping_source_row':shiprow,'catalogue_row':rows[pid],'observed_title':record['Title'],
                        'catalogue_retail_name':fields[pid]['Retail name']})
    assert len(matches)==len(observed),'Unmatched Saatchi rows require review; never silently discard them'
    assert len(matches)==98
    patches=[]
    identifier_corrections=[]
    def put(sheet,cell,value,fmt=None,replace=False):
        assert replace or master.value(sheet,cell) in (None,''),(sheet,cell,'Unexpected populated destination')
        patches.append({'sheet':sheet,'cell':cell,'before':master.value(sheet,cell),'value':value,'formula':None,'format':fmt})
    for h in added:
        put('Wall Sculptures',allheaders[h]+'7',h,'header')
        for pid,n in rows.items():
            v=values[pid].get(h)
            if v is None:continue
            fmt=None
            if h.endswith('uploaded_utc'):fmt='yyyy-mm-dd hh:mm'
            elif h.endswith('artist_share'):fmt='0%'
            elif h.endswith('gbp_per_usd'):fmt='0.000000'
            elif isinstance(v,(int,float)) and not isinstance(v,bool):
                fmt='0.00' if any(s in h for s in ('usd','gbp','_kg','_lb','_cm','_in')) else '0'
            elif h.endswith('artwork_id') or h.endswith('_sku'):fmt='@'
            put('Wall Sculptures',allheaders[h]+str(n),v,fmt)
    for match in matches:
        n=match['catalogue_row'];pid=match['catalogue_id'];sku=match['sku']
        if master.value('Wall Sculptures','AQ'+str(n))!=sku:
            assert master.value('Upload Plan','C'+str(n))==pid
            for sheet,address in [('Wall Sculptures','AQ'+str(n)),('Upload Plan','D'+str(n))]:
                prior=master.value(sheet,address)
                assert prior=='BOLD-'+pid.removeprefix('BSI-'),(sheet,address,'Unrecognised legacy SKU')
                put(sheet,address,sku,'@',replace=True)
                identifier_corrections.append({'sheet':sheet,'cell':address,'catalogue_id':pid,'before':prior,'value':sku,
                    'basis':'Current app Seller SKU and existing native artwork-ID binding agree; stale generated export SKU replaced.'})
    # Keep the source's global notes and destination definitions with existing references.
    for c,v in [('J22','Saatchi source notes'),('K22','Source value'),('L22','Source explanations; formulas refer to supplied file. Values here are static.')]:put('Platform Review',c,v,'header')
    for n in source.rows('Notes',1):
        for src,dest in [('A','J'),('B','K'),('C','L')]:
            v=source.value('Notes',src+str(n))
            if v not in (None,''):put('Platform Review',dest+str(n+22),v,'0.000000' if n==5 and src=='B' else '0%' if n==6 and src=='B' else None)
    original_rows={int(row.get('r')):row for row in ET.fromstring(master.parts[master.paths['Platform Review']]).findall('s:sheetData/s:row',NS)}
    row_updates=[]
    for n in source.rows('Notes',1):
        lines=max(len(str(source.value('Notes',column(c)+str(n)) or ''))//(28 if c==1 else 85)+1 for c in range(1,4))
        height=max(24,min(220,lines*16));before_height=float(original_rows[n+22].get('ht','15'))
        if height>before_height:row_updates.append({'sheet':'Platform Review','row':n+22,'height':height})
    plan={'scope':'Import supplied 3 November Saatchi snapshot as uniquely prefixed saatchi_ fields: artworks, images, destination shipping and source notes. Existing app specifications, prices, Chairish/eBay fields and native listings unchanged.',
          'patches':patches,'headers':allheaders,'master_rows':rows,'added_master_columns':added,'first_master_column':first,
          'last_master_column':first+len(added)-1,'source_file':str(source.path),'source_sha256':digest,
          'matched_artworks':len(matches),'source_artwork_columns':len(headers),'destination_groups':len(shipping)//2,
          'matched-platform-records':matches,'global_notes_first_row':22,'global_notes_last_row':max(source.rows('Notes',1))+22,
          'row_format_updates':row_updates,'identifier_corrections':identifier_corrections,
          'column_format_updates':[{'sheet':'Platform Review','first':12,'last':12,'width':90}]}
    if identifier_corrections:
        plan['scope']+=' Align the stale generated Dune Ripple II Verdigris/Copper SKU in two export cells with the current app Seller SKU SQ0059342.'
    write('saatchi-import-plan.json',plan);write('matched-platform-records.json',matches);write('unmatched-records.json',unmatched)
    write('source-snapshot.json',{'source':str(source.path),'sha256':digest,'artworks':observed,
        'shipping':shipping_by_id,'source_formulas':{s:{a:source.formula(s,a) for a in cs if source.formula(s,a)} for s,cs in source.cells.items()},
        'source_notes':[{column(c):source.value('Notes',column(c)+str(n)) for c in range(1,4)} for n in source.rows('Notes',1)]})
    print(json.dumps({k:plan[k] for k in ['matched_artworks','source_artwork_columns','destination_groups','first_master_column','last_master_column']}|{'new_prefixed_fields':len(added),'cells':len(patches),'unmatched':len(unmatched)}))

def verify(out):
    read=lambda n:json.loads((out/n).read_text())
    p=read('saatchi-import-plan.json');source=Xlsx(p['source_file']);original=Xlsx(out/'previous-catalogue.xlsx');final=Xlsx(out/'catalogue_wall_sculptures.xlsx')
    assert hashlib.sha256(Path(p['source_file']).read_bytes()).hexdigest()==p['source_sha256']
    assert original.paths==final.paths and len(final.paths)==12
    for c in p.get('column_format_updates',[]):
        root=ET.fromstring(final.parts[final.paths[c['sheet']]])
        cols=[x for x in root.findall('s:cols/s:col',NS) if int(x.get('min'))<=c['first'] and int(x.get('max'))>=c['last']]
        assert len(cols)==1 and float(cols[0].get('width'))==c['width']
    for c in p.get('row_format_updates',[]):
        root=ET.fromstring(final.parts[final.paths[c['sheet']]])
        assert float(root.find(f's:sheetData/s:row[@r="{c["row"]}"]',NS).get('ht'))==c['height']
    changed={(c['sheet'],c['cell']):c for c in p['patches']}
    preserved=0
    for sheet,cells in original.cells.items():
        for a,c in cells.items():
            if (sheet,a) in changed:
                correction=next((x for x in p['identifier_corrections'] if x['sheet']==sheet and x['cell']==a),None)
                assert correction and original.value(sheet,a)==correction['before'] and final.value(sheet,a)==correction['value']
                continue
            assert ET.tostring(c)==ET.tostring(final.cells[sheet][a]),(sheet,a)
            preserved+=1
    for c in p['patches']:
        v=final.value(c['sheet'],c['cell']);exp=c['value']
        assert v==exp or isinstance(v,(int,float)) and isinstance(exp,(int,float)) and abs(v-exp)<1e-8,(c['sheet'],c['cell'],v,exp)
        assert not final.formula(c['sheet'],c['cell'])
    headers={final.value('Wall Sculptures',a):re.sub(r'\d','',a) for a in final.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',a)}
    assert len(headers)==len(set(k.casefold() for k in headers))==p['last_master_column']
    seen=set()
    for match in read('matched-platform-records.json'):
        r=match['catalogue_row'];sr=match['source_row'];native=match['artwork_id']
        assert str(source.value('Artworks','B'+str(sr)))==native and native not in seen;seen.add(native)
        assert final.value('Wall Sculptures','AA'+str(r))==match['catalogue_id']
        assert final.value('Wall Sculptures','AQ'+str(r))==match['sku']
        for c in range(1,61):
            h=source.value('Artworks',column(c)+'1');key='saatchi_observed_'+slug(h)
            exp=source.value('Artworks',column(c)+str(sr));exp=str(exp) if h=='Artwork ID' else exp
            got=final.value('Wall Sculptures',headers[key]+str(r))
            assert got==exp or got in ('',None) and exp in ('',None),(native,h,got,exp)
        shiprow=match['shipping_source_row']
        for c in range(5,21,2):
            group=slug(source.value('Shipping by destination',column(c)+'2'))
            for offset,stem in [(0,'shipping'),(1,'list_price')]:
                key='saatchi_observed_'+stem+'_'+group+'_usd'
                assert final.value('Wall Sculptures',headers[key]+str(r))==source.value('Shipping by destination',column(c+offset)+str(shiprow))
    assert len(seen)==98
    # Core price/cost columns, every original formula and native relationship are retained.
    formula_count=sum(final.formula(s,a) is not None for s,cs in final.cells.items() for a in cs)
    original_formulas=sum(original.formula(s,a) is not None for s,cs in original.cells.items() for a in cs)
    assert formula_count==original_formulas
    tables=[ET.fromstring(v) for n,v in final.parts.items() if re.fullmatch(r'xl/tables/table\d+.xml',n)]
    table=next(t for t in tables if len(t.find('s:tableColumns',NS))==p['last_master_column'])
    assert table.get('ref')=='A7:'+column(p['last_master_column'])+'188'
    receipt={'status':'PASS','components':181,'source_artworks':98,'matched_artworks':98,'ambiguous_matches':0,
             'new_prefixed_fields':len(p['added_master_columns']),'destination_groups':8,'original_cells_unchanged':preserved,
             'original_formulas_preserved':formula_count,'core_values_preserved_except_verified_stale_export_sku':True,
             'stale_exported_sku_cells_corrected':len(p['identifier_corrections']),
             'sha256':hashlib.sha256((out/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()}
    (out/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','verify']);ap.add_argument('output',type=Path);ap.add_argument('--source',type=Path)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if a.mode=='prepare':
        if not a.source:ap.error('--source is required to prepare')
        prepare(a.output.resolve(),a.source.resolve())
    else:verify(a.output.resolve())
