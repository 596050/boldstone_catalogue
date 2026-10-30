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
policy_note = 'Listing use removed under the owner In situ policy; original and other purposes retained. Replacement Primary remains unselected.'
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
for kind, filename in [('core_workbook','Boldstone_Sculpture_Master_Catalogue_2026-10-27_v7.xlsx'),('comprehensive_workbook','Boldstone_Wall_Sculptures_Unified_2026-10-27_v7.xlsx')]:
    book=Book(manifest['sources'][kind]['snapshot']);edits={}
    def edit(sn,cell,value=None,formula=None):
        before=book.sheet(sn)[0].get(cell)
        if formula is None and value=='' and before in (None,('text','')):return
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
        if sn in {'Squarespace raw','Shopify raw','Current image paths'}:continue
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
                            if pid in changed:edit(sn,'V'+r,c.get('V'+r,('',''))[1]+' | '+policy_note)
                        if o.get('context_image_url'):link(sn,'T'+r,o['context_image_url'])
                        elif o.get('context_file_id'):link(sn,'T'+r,o['context_folder_url'],'Folder (image unavailable)')
                        if o.get('context_folder_url'):link(sn,'U'+r,o['context_folder_url'])
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
                        elif o.get('historical_series_reference'):
                            history=o['historical_series_reference']
                            edit(sn,'I'+r,'Historical only / unavailable')
                            link(sn,'J'+r,history['folder_url'],'Folder (series image unavailable)')
                            link(sn,'K'+r,history['folder_url'])
                            edit(sn,'L'+r,c.get('L'+r,('',''))[1]+' | Previous shared context/series image was deleted by owner and verified absent. Historical ID retained; series replacement remains open and context remains held.')
                        if pid in changed:
                            edit(sn,'L'+r,c.get('L'+r,('',''))[1]+' | '+policy_note)
        missing,_=book.sheet('Missing Pictures')
        rowids=sorted({int(re.search(r'\d+',a)[0]) for a in missing})
        last=max(rowids)
        assigned={}
        def request_row(pid,role):
            nonlocal_dummy=None
            existing=[int(a[1:]) for a,v in missing.items() if re.fullmatch(r'B\d+',a) and v[1]==pid and missing.get('D'+a[1:],('',''))[1]==role]
            if existing:return existing[0]
            if (pid,role) not in assigned:assigned[(pid,role)]=last+len(assigned)+1
            return assigned[(pid,role)]
        for pid in report['effective_context_owner_holds']:
            o=options[pid];row=request_row(pid,'In situ')
            values={'A':'Held','B':pid,'C':o['name'],'D':'In situ','E':'Find / capture','F':'Context reference unavailable or previously held; keep the replacement requirement on owner hold.','I':o.get('context_file_id') or 'Unbound','J':o.get('context_folder_id') or 'Unbound','K':'Existing display/variation scope retained.','L':'Current scoped availability and historical source ID remain separate.','M':'Standing context-hold policy retained; no new owner response inferred.','N':'Owner hold'}
            for col,v in values.items():edit('Missing Pictures',col+str(row),v)
            if o.get('context_folder_url'):
                link('Missing Pictures','G'+str(row),o['context_folder_url'],'Folder (reference held)');link('Missing Pictures','H'+str(row),o['context_folder_url'])
        primary_requests=[o for o in options.values() if o['product_id'] in active and o.get('historical_primary_reference') and not o.get('file_id')]
        for o in primary_requests:
            row=request_row(o['product_id'],'Individual')
            policy_removed=o['historical_primary_reference'].get('reason')=='in_situ_listing_exclusion'
            values={'A':'Review','B':o['product_id'],'C':o['name'],'D':'Individual','E':'Find / capture','F':('Choose a permitted full view; the former In situ image remains retained but is excluded from Listing.' if policy_removed else 'Choose a surviving full view or take an individual photograph; previous Primary was deleted and verified absent.'),'I':o['historical_primary_reference']['file_id'],'J':o.get('folder_id') or 'Unbound','K':'Current Primary unbound. Existing identity, working specifications and source relationships retained.','L':('Version-checked Listing exclusion receipt retained; no replacement inferred.' if policy_removed else 'Exact deletion receipt retained; no replacement inferred.'),'M':'No saved replacement Primary at this review cut.','N':'Open'}
            for col,v in values.items():edit('Missing Pictures',col+str(row),v)
            link('Missing Pictures','G'+str(row),o['folder_url'],'Folder (choose Primary)');link('Missing Pictures','H'+str(row),o['folder_url'])
        series_requests=[o for o in options.values() if o['product_id'] in active and o.get('historical_series_reference') and not o.get('current_series_reference')]
        for o in series_requests:
            history=o['historical_series_reference'];row=request_row(o['product_id'],'Series')
            for col,v in {'A':'Review','B':o['product_id'],'C':o['name'],'D':'Series','E':'Find / capture','F':'Find a surviving qualified series reference.','I':history['file_id'],'J':history['folder_id'],'K':history.get('scope',''),'L':history.get('status',''),'M':'No new response inferred.','N':'Open'}.items():edit('Missing Pictures',col+str(row),v)
            link('Missing Pictures','G'+str(row),history['folder_url'],'Historical containing folder');link('Missing Pictures','H'+str(row),history['folder_url'])
        last=max(last,max(assigned.values(),default=last))
        edit('Missing Pictures','B4',formula=f'=COUNTIFS(E10:E{last},"Find / capture",N10:N{last},"Open")')
        edit('Missing Pictures','D4',formula=f'=COUNTIFS(E10:E{last},"Verify existing image",N10:N{last},"<>Resolved")')
        edit('Missing Pictures','F4',formula=f'=COUNTIF(N10:N{last},"Optional")')
        edit('Missing Pictures','A3',f'{len(primary_requests)} Primary choices and {len(series_requests)} unheld series replacements remain open. {len(report["effective_context_owner_holds"])} context cases and the earlier Copper series case remain held. No new owner response inferred.')
        edit('Master Catalogue','A3','186 active options;189 retained records. 91 In situ Listing uses removed; four Primaries cleared without replacement guesses. All working specifications and stable IDs retained.')
        edit('Photo Coverage','A3',f'186 active options; {primary_count} selected Primary and {context_count} qualified context references. Policy cut: '+manifest['policy_cut_utc']+'; native paths retain '+manifest['native_inventory_cut_utc'])
        edit('Master Catalogue','G4','Active Primary references')
        edit('Master Catalogue','H4',formula='=COUNTIFS(Q10:Q198,"<>Unbound",L10:L198,"<>Retired")')
        chiswick=next(re.search(r'\d+',c)[0] for c,v in book.sheet('Master Catalogue')[0].items() if re.fullmatch(r'A\d+',c) and v[1]=='BSI-830A4594D176')
        previews=[['Master Catalogue',f'M{chiswick}:R{chiswick}','cleared-chiswick-primary'],['Missing Pictures',f'B{last-1}:F{last}','latest-picture-requests'],['Image Use Exclusions','A2:F9','listing-exclusions']]
        expected=[{'sheet':'Master Catalogue','cell':'B4','value':186},{'sheet':'Master Catalogue','cell':'H4','value':primary_count},{'sheet':'Missing Pictures','cell':'B4','value':len(primary_requests)+len(series_requests)}]
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
                        if pid in changed:
                            col='AC' if sn=='Wall Sculptures' else 'AA';edit(sn,col+r,c.get(col+r,('',''))[1]+' | '+policy_note)
                    if pid in changed:
                        col='AC' if sn=='Wall Sculptures' else 'AA'
                        retained=c.get(col+r,('',''))[1]
                        if 'deleted' in retained.casefold() or 'no replacement' in retained.casefold():retained='Previous source status: '+retained
                        edit(sn,col+r,retained+' | '+policy_note)
        edit('Wall Sculptures','A3','186 active options. 91 In situ Listing uses excluded; four affected Primaries are unselected. The Image Use Exclusions sheet records exact choices. All specifications and saved platform sources retained.')
        edit('Wall Sculptures','A6',f'Platform source coverage retained: 80 reviewed Squarespace wall products + 1 unconfirmed-scope source; 38 Shopify wall products. Saved source inventory counts remain historical. Current image paths has {len(overlay):,} scoped files ({wall_count:,} Wall Sculptures + {workshop_count:,} retained Workshop). These are photographs, not sculpture counts.')
        edit('Wall Sculptures','Y8','Saved source file count');edit('Wall Sculptures','Z8','Saved unassociated count')
        edit('Overview','A3','186 active options; complete saved sources preserved. Image-use policy cut '+manifest['policy_cut_utc']+'; native paths retain the earlier inventory cut.')
        edit('Guide and sources','B18',f'Current image paths retains {len(overlay):,} audited file records from '+manifest['native_inventory_cut_utc']+'. Image Use Exclusions records91 completed Listing removals at '+manifest['policy_cut_utc']+'. Historical associations and source inventories remain dated source evidence; current exclusions take precedence for Listing use.')
        edit('Native Availability','A3','Historical six-deletion snapshot from 25 October 2026. For later removals and current surviving files, use Current image paths and the published native evidence receipt.')
        edit('Native Availability','A4','Preserved history: the six deletions and source clocks below are unchanged. Current Primary choices are reflected in Wall Sculptures and Products.')
        c,_=book.sheet('Current image paths')
        for cell,val in c.items():
            if re.fullmatch(r'E\d+',cell) and val[1] in files:
                record=files[val[1]];label=' | '.join(x['name']+' — '+x['role'] for x in record['selected_references'])
                edit('Current image paths','K'+cell[1:],label)
        edit('Current image paths','A3','Native image inventory cut '+manifest['native_inventory_cut_utc']+'. Selected references reflect the separately verified In situ Listing exclusions at '+manifest['policy_cut_utc']+'. Filenames and folders remain dated navigation evidence.')
        previews=[['Wall Sculptures','L8:M12','unified-current-links'],['Image Use Exclusions','A2:F9','unified-listing-exclusions']]
        expected=[{'sheet':'Overview','cell':'B7','value':186}]
    expected.extend([{'sheet':'Image Use Exclusions','cell':'B4','value':91},{'sheet':'Image Use Exclusions','cell':'D4','value':68},{'sheet':'Image Use Exclusions','cell':'F4','value':30},{'sheet':'Image Use Exclusions','cell':'H4','value':4}])
    plans.append({'key':kind,'source':str(manifest['sources'][kind]['snapshot']),'source_sha256':manifest['sources'][kind]['sha256'],'output':str(OUT/filename),'edits':list(edits.values()),'expected':expected,'previews':previews,'new_sheet':'Image Use Exclusions','replace_image_sheet':False,'table_expansion':{'sheet':'Missing Pictures','name':'Photo_Missing_Pictures','range':f'A9:N{last}'} if kind=='core_workbook' else None})
    book.close()
write(H/'workbook-edit-plan.json',{'plans':plans})
print(json.dumps({'edits':{p['key']:len(p['edits']) for p in plans},'hyperlinks':{p['key']:sum(e['kind']=='hyperlink' for e in p['edits']) for p in plans},'output':str(OUT)}))
