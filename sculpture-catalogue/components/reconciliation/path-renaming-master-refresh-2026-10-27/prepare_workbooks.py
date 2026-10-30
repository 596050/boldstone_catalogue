"""Declare a narrowly scoped workbook edit; preserve original source values."""
from common import *
from collections import defaultdict
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse, quote
import re, sqlite3

original = read(manifest['sources']['register']['snapshot'])
oldoptions = {o['product_id']: o for o in original['options']}
report = read(H / 'register-preparation.json')
primary_count=report['current_primary_references'];context_count=report['current_context_references']
wall_count=sum(r['scope']=='Wall Sculptures' for r in overlay);workshop_count=len(overlay)-wall_count
changed = {r['product_id'] for r in report['primary_changes']}
oldurl = defaultdict(set)
folderpath = {}
completed = read(manifest['sources']['completed_native_census']['snapshot'])
for scope in ['wall', 'workshop']:
    for r in completed[scope]['entries']:
        if r['kind'] == 'folder': folderpath[r['id']] = r['path']
for fid,r in read(manifest['sources']['current_wall_census']['snapshot'])['records'].items():
    if r['kind'] == 'folder': folderpath[fid] = r['path']

def key(url):
    u = urlparse(url)
    if u.netloc not in {'www.dropbox.com','dropbox.com'}: return None
    path = unquote(u.path)
    for prefix in ['/preview','/home']:
        if path.startswith(prefix + '/'):
            if prefix == '/home' and u.query.startswith('preview='):
                return path[len(prefix):].rstrip('/') + '/' + unquote(u.query[len('preview='):])
            return path[len(prefix):].rstrip('/').casefold()
    return None

def addold(url, target):
    k=key(url)
    if k: oldurl[k.casefold()].add(target)

db=sqlite3.connect(manifest['sources']['source_gallery']['snapshot'])
for fid,raw in db.execute('SELECT file_id,record_json FROM images'):
    r=json.loads(raw)
    if fid in files:
        addold(r.get('image_url',''),files[fid]['image_url'])
        if r.get('folder_id') in folderpath:
            addold(r.get('folder_url',''),'https://www.dropbox.com/home'+quote(folderpath[r['folder_id']],safe='/'))
db.close()
for o in original['options']:
    for ik,fk in [('file_id','image_url'),('context_file_id','context_image_url')]:
        if o.get(ik) in files: addold(o.get(fk,''), files[o[ik]]['image_url'])
    for ik,fk in [('folder_id','folder_url'),('context_folder_id','context_folder_url')]:
        if o.get(ik) in folderpath: addold(o.get(fk,''),'https://www.dropbox.com/home'+quote(folderpath[o[ik]],safe='/'))
for fid,r in files.items():
    addold(r['image_url'],r['image_url']);addold(r['folder_url'],r['folder_url'])

plans=[]
for kind, filename in [('core_workbook','Boldstone_Sculpture_Master_Catalogue_2026-10-27.xlsx'),('comprehensive_workbook','Boldstone_Wall_Sculptures_Unified_2026-10-27.xlsx')]:
    book=Book(manifest['sources'][kind]['snapshot']);edits={}
    def edit(sn,cell,value=None,formula=None):
        before=book.sheet(sn)[0].get(cell)
        expected=('formula',formula.lstrip('=')) if formula is not None else ('number',str(value)) if isinstance(value,(float,int)) else ('text',value)
        if before != expected:
            edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'kind':'formula' if formula is not None else 'value',**({'formula':formula} if formula is not None else {'value':value})}
    def link(sn,cell,url,label=None):
        c,links=book.sheet(sn);before=c.get(cell);label=label or (before[1] if before and before[0]=='text' else 'Image' if '/preview/' in url else 'Folder')
        if '/preview/' in url and 'image deleted' in label.casefold():label='Image'
        if before and before[0]=='formula':
            match=re.fullmatch(r'HYPERLINK\("(?:[^"]|"")*","((?:[^"]|"")*)"\)',before[1],re.I)
            if match and label in {'Image','Folder'}:label=match[1].replace('""','"')
        if links.get(cell)==url and before and before[0]=='text' and before[1]==label:return
        f='=HYPERLINK("'+url.replace('"','""')+'","'+label.replace('"','""')+'")'
        if before==('formula',f[1:]):return
        edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'before_href':links.get(cell),'kind':'hyperlink','formula':f,'url':url,'label':label,'keep_formula':bool(before and before[0]=='formula')}
    # Refresh navigation only. The recorded source filenames, paths, clocks and
    # raw platform fields remain unchanged in their captured source tables.
    for sn in book.sheets:
        if sn in {'Squarespace raw','Shopify raw'}:continue
        cells,links=book.sheet(sn)
        for cell,url in links.items():
            targets=oldurl.get((key(url) or '').casefold(),set())
            if len(targets)==1:
                target=next(iter(targets))
                if target!=url:link(sn,cell,target)
        for cell,val in cells.items():
            if val[0]=='formula':
                m=re.fullmatch(r'HYPERLINK\("((?:[^"]|"")*)","((?:[^"]|"")*)"\)',val[1],re.I)
                if m:
                    url=m[1].replace('""','"');targets=oldurl.get((key(url) or '').casefold(),set())
                    if len(targets)==1 and next(iter(targets))!=url:link(sn,cell,next(iter(targets)),m[2].replace('""','"'))
    if kind=='core_workbook':
        for sn in ['Master Catalogue','Photo Coverage']:
            c,_=book.sheet(sn)
            for cell,val in c.items():
                if re.fullmatch(r'A\d+',cell) and val[1] in active:
                    pid=val[1];r=re.search(r'\d+',cell)[0];o=options[pid]
                    if sn=='Master Catalogue':
                        for col,k in [('Q','file_id'),('R','folder_id')]:edit(sn,col+r,o.get(k) or 'Unbound')
                        for col,k in [('N','image_url'),('O','folder_url')]:
                            if o.get(k):link(sn,col+r,o[k])
                        if not o.get('image_url') and o.get('historical_primary_reference'):
                            link(sn,'N'+r,o['folder_url'],'Folder (Primary unavailable)')
                            edit(sn,'V'+r,c.get('V'+r,('',''))[1]+' | Former Primary deleted by owner and verified absent. Historical ID retained; current Primary unbound.')
                        if o.get('context_image_url'):link(sn,'T'+r,o['context_image_url'])
                        elif o.get('context_file_id'):link(sn,'T'+r,o['context_folder_url'],'Folder (image unavailable)')
                        if o.get('context_folder_url'):link(sn,'U'+r,o['context_folder_url'])
                        if pid in changed:edit(sn,'V'+r,c.get('V'+r,('',''))[1]+' | Current owner-selected Primary imported; image choice does not verify physical specifications, scale or exact platform variant.')
                    else:
                        for col,k in [('M','file_id'),('N','folder_id'),('O','context_file_id'),('P','context_folder_id')]:edit(sn,col+r,o.get(k) or 'Unbound')
                        for col,k in [('D','image_url'),('E','folder_url'),('H','context_folder_url')]:
                            if o.get(k):link(sn,col+r,o[k])
                        if not o.get('image_url') and o.get('historical_primary_reference'):
                            link(sn,'D'+r,o['folder_url'],'Folder (Primary unavailable)');edit(sn,'C'+r,'Needs current image')
                        if o.get('context_image_url'):link(sn,'G'+r,o['context_image_url'])
                        elif o.get('context_file_id'):
                            edit(sn,'F'+r,'Owner hold');link(sn,'G'+r,o['context_folder_url'],'Folder (image unavailable)')
                            edit(sn,'L'+r,c.get('L'+r,('',''))[1]+' | Historical context image unavailable in current audited scope; replacement remains on owner hold.')
                        series=o.get('current_series_reference')
                        if series:
                            for col,k in [('Q','file_id'),('R','folder_id')]:edit(sn,col+r,series[k])
                            link(sn,'J'+r,series['image_url']);link(sn,'K'+r,series['folder_url'])
                        if pid in changed:
                            edit(sn,'L'+r,c.get('L'+r,('',''))[1]+' | Current saved Primary choice imported; existing group/design/variation qualifications retained.')
        # The two unavailable historical references are held rather than silently
        # presented as live. Azure gets the preallocated final request row220.
        missing,_=book.sheet('Missing Pictures')
        for row,pid in [(79,'BSI-EBD43DF0704F'),(220,'BSI-3C849B547D50')]:
            o=options[pid]
            values={'A':'Held','B':pid,'C':o['name'],'D':'In situ','E':'Find / capture','F':'Historical reference unavailable; replacement on owner hold.','I':o['context_file_id'],'J':o['context_folder_id'],'K':'Display/reference only; no exact physical evidence.','L':'Current scoped image unavailable; historical ID retained.','M':'Standing owner hold retained.','N':'Owner hold'}
            for col,v in values.items():edit('Missing Pictures',col+str(row),v)
            link('Missing Pictures','G'+str(row),o['context_folder_url'],'Folder (image unavailable)');link('Missing Pictures','H'+str(row),o['context_folder_url'])
        for row,o in enumerate((o for o in options.values() if o['product_id'] in active and o.get('historical_primary_reference')),221):
            values={'A':'Review','B':o['product_id'],'C':o['name'],'D':'Individual','E':'Find / capture','F':'Choose a surviving full view or take an individual photograph; previous Primary deleted by owner.','I':o['historical_primary_reference']['file_id'],'J':o['folder_id'],'K':'Current Primary unbound; historical identity and source values retained.','L':'Owner deletion independently verified; no replacement inferred.','M':'No new owner response inferred.','N':'Open'}
            for col,v in values.items():edit('Missing Pictures',col+str(row),v)
            link('Missing Pictures','G'+str(row),o['folder_url'],'Folder (Primary unavailable)');link('Missing Pictures','H'+str(row),o['folder_url'])
        edit('Missing Pictures','B4',formula='=COUNTIFS(E10:E221,"Find / capture",N10:N221,"Open")')
        edit('Missing Pictures','D4',formula='=COUNTIFS(E10:E221,"Verify existing image",N10:N221,"<>Resolved")')
        edit('Missing Pictures','F4',formula='=COUNTIF(N10:N221,"Optional")')
        edit('Missing Pictures','A3','24 context requirements are on owner hold; one series requirement remains held. Legacy Frozen Fish exact image binding stays deferred. Historical and optional requests retain their scope.')
        edit('Master Catalogue','A3','187 active options; 189 retained rows. Current Dropbox links and saved Primary choices refreshed 27 October 2026. All working specifications and source qualifications retained.')
        edit('Photo Coverage','A3',f'187 active options; {primary_count} current Primary and {context_count} qualified context references. 24 context replacements on owner hold. Dropbox census and review cut: '+manifest['recorded_utc'])
        # The existing header counts retained references, not distinct sculptures.
        edit('Master Catalogue','G4','Active Primary references')
        edit('Master Catalogue','H4',formula='=COUNTIFS(Q10:Q198,"<>Unbound",L10:L198,"<>Retired")')
        previews=[['Master Catalogue','M9:R13','core-current-links'],['Photo Coverage','C9:K12','core-photo-coverage']]
        expected=[{'sheet':'Master Catalogue','cell':'B4','value':187},{'sheet':'Master Catalogue','cell':'H4','value':primary_count}]
    else:
        for sn,idcol in [('Wall Sculptures','Q'),('Products','A')]:
            c,_=book.sheet(sn)
            for cell,val in c.items():
                if re.fullmatch(idcol+r'\d+',cell) and val[1] in active:
                    pid=val[1];r=re.search(r'\d+',cell)[0];o=options[pid]
                    for col,k in ([('AB','file_id'),('AA','folder_id')] if sn=='Wall Sculptures' else [('Z','file_id')]):edit(sn,col+r,o.get(k) or 'Unbound')
                    for col,k in ([('L','image_url'),('M','folder_url')] if sn=='Wall Sculptures' else [('AB','image_url'),('AC','folder_url')]):
                        if o.get(k):link(sn,col+r,o[k])
                    if not o.get('image_url') and o.get('historical_primary_reference'):
                        link(sn,('L' if sn=='Wall Sculptures' else 'AB')+r,o['folder_url'],'Folder (Primary unavailable)')
                        col='AC' if sn=='Wall Sculptures' else 'AA';edit(sn,col+r,c.get(col+r,('',''))[1]+' | Former Primary deleted by owner; current image unbound. Historical ID retained separately.')
                    if pid in changed:
                        col='AC' if sn=='Wall Sculptures' else 'AA'
                        retained=c.get(col+r,('',''))[1]
                        if 'deleted' in retained.casefold() or 'no replacement' in retained.casefold():retained='Previous source status: '+retained
                        edit(sn,col+r,retained+' | Current owner-selected Primary; group/design/variation scope retained; no physical or platform verification inferred.')
        edit('Wall Sculptures','A3','187 active catalogue options with current links at the 27 October publication cut. Captured platform and source inventories remain historical evidence.')
        edit('Wall Sculptures','A6',f'Platform source coverage retained: 80 reviewed Squarespace wall products + 1 unconfirmed-scope source; 38 Shopify wall products. Saved source inventory counts remain historical. Current image paths has {len(overlay):,} scoped files ({wall_count:,} Wall Sculptures + {workshop_count:,} retained Workshop). These are photographs, not sculpture counts.')
        edit('Wall Sculptures','Y8','Saved source file count');edit('Wall Sculptures','Z8','Saved unassociated count')
        edit('Overview','A3','187 active options; complete saved sources preserved. Current native filenames and actual containing folders: 27 October 2026 publication cut.')
        edit('Guide and sources','B18',f'Current image paths holds {len(overlay):,} current audited file records and stable file/folder IDs at '+manifest['recorded_utc']+'. Existing Dropbox source tabs retain their original captured names, paths and counts. Navigation targets were refreshed only through unambiguous stable-ID evidence. Saved Primary choices do not verify physical or commercial fields.')
        edit('Native Availability','A3','Historical six-deletion snapshot from 25 October 2026. For later removals and current surviving files, use Current image paths and the published native evidence receipt.')
        edit('Native Availability','A4','Preserved history: the six deletions and source clocks below are unchanged. Current Primary choices are reflected in Wall Sculptures and Products.')
        previews=[['Wall Sculptures','L8:M12','unified-current-links'],['Current image paths','A2:D11','current-image-paths']]
        expected=[{'sheet':'Overview','cell':'B7','value':187}]
    plans.append({'key':kind,'source':str(manifest['sources'][kind]['snapshot']),'source_sha256':manifest['sources'][kind]['sha256'],'output':str(OUT/filename),'edits':list(edits.values()),'expected':expected,'previews':previews,'new_sheet':'Current image paths' if kind=='comprehensive_workbook' else None})
    book.close()
write(H/'workbook-edit-plan.json',{'plans':plans})
print(json.dumps({'edits':{p['key']:len(p['edits']) for p in plans},'hyperlinks':{p['key']:sum(e['kind']=='hyperlink' for e in p['edits']) for p in plans},'output':str(OUT)}))
