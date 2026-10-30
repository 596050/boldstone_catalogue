"""Declare only the two-row consolidation and its dependent counts/aliases."""
from common import *
from xml.etree import ElementTree as E
from pathlib import PurePosixPath
import re
KEEP='BSI-9299D69FEF08';DUP='BSI-4536FDCA0DA9'
keep=options[KEEP];old=options[DUP];decision=read(H/'merge-decision.json')
note='Owner-confirmed duplicate: '+DUP+' is retained as an alias of '+KEEP+'. Keeper specifications and existing review choices remain authoritative; source alternatives remain historical.'
report=read(H/'register-preparation.json')
original=read(manifest['sources']['register']['snapshot']);prior={o['product_id']:o for o in original['options']}
plans=[]
for kind,filename in [('core_workbook','Boldstone_Sculpture_Master_Catalogue_2026-10-28_v8.xlsx'),('comprehensive_workbook','Boldstone_Wall_Sculptures_Unified_2026-10-28_v8.xlsx')]:
    book=Book(manifest['sources'][kind]['snapshot']);edits={}
    def edit(sn,cell,value=None,formula=None):
        before=book.sheet(sn)[0].get(cell)
        if formula is None and value=='' and before in (None,('text','')):return
        wanted=('formula',formula.lstrip('=')) if formula is not None else ('number',str(value)) if isinstance(value,(int,float)) else ('text',value)
        if before!=wanted:edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'kind':'formula' if formula is not None else 'value',**({'formula':formula} if formula is not None else {'value':value})}
    def link(sn,cell,url,label):
        cells,links=book.sheet(sn);before=cells.get(cell)
        if links.get(cell)==url and before==('text',label):return
        f='=HYPERLINK("'+url.replace('"','""')+'","'+label.replace('"','""')+'")'
        if before==('formula',f[1:]):return
        edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'before_href':links.get(cell),'kind':'hyperlink','formula':f,'url':url,'label':label,'keep_formula':bool(before and before[0]=='formula')}
    def row(sn,pid,col='A'):
        return next(re.search(r'\d+',a)[0] for a,v in book.sheet(sn)[0].items() if re.fullmatch(col+r'\d+',a) and v[1]==pid)
    if kind=='core_workbook':
        kr,dr=row('Master Catalogue',KEEP),row('Master Catalogue',DUP)
        edit('Master Catalogue','B'+kr,keep['name']);edit('Master Catalogue','L'+dr,'Retired');edit('Master Catalogue','M'+dr,'Owner-confirmed duplicate alias; see keeper '+KEEP)
        edit('Master Catalogue','V'+dr,note);edit('Master Catalogue','V'+kr,book.sheet('Master Catalogue')[0]['V'+kr][1]+' | '+note)
        edit('Master Catalogue','W'+kr,' | '.join(keep['related_platform_offer_refs']))
        edit('Master Catalogue','X'+kr,'Merged alias retains O009 source evidence and its finish/size/build limits. Exact current variant/SKU and physical specifications remain unverified.')
        edit('Master Catalogue','Y'+kr,' | '.join(keep['source_scopes']))
        link('Master Catalogue','N'+kr,keep['image_url'],'Image');link('Master Catalogue','O'+kr,keep['folder_url'],'Folder')
        edit('Master Catalogue','Q'+kr,keep['file_id']);edit('Master Catalogue','R'+kr,keep['folder_id'])
        edit('Master Catalogue','A3','185 active options;189 retained records, including four retirements. Dune Ripple2 Verdigris is an alias of Verdigris and Copper. Keeper fields and existing review choices preserved; unrelated pending imports remain separate.')
        edit('Master Catalogue','E4','Active rows with six fields')
        krp,drp=row('Photo Coverage',KEEP),row('Photo Coverage',DUP)
        edit('Photo Coverage','B'+krp,keep['name']);edit('Photo Coverage','C'+krp,'Available')
        link('Photo Coverage','D'+krp,keep['image_url'],'Image');link('Photo Coverage','E'+krp,keep['folder_url'],'Folder');edit('Photo Coverage','M'+krp,keep['file_id']);edit('Photo Coverage','N'+krp,keep['folder_id'])
        edit('Photo Coverage','L'+krp,book.sheet('Photo Coverage')[0]['L'+krp][1]+' | '+note+' Two prior accepted-reference qualifications retained; context selection/hold remains separate.')
        for col in ['C','F','I']:edit('Photo Coverage',col+drp,'Retired / not applicable')
        edit('Photo Coverage','L'+drp,note)
        edit('Photo Coverage','A3','185 active options;179 selected Primary references. Scoped owner Dune Ripple2 consolidation only. Current source IDs and photograph qualifications retained; no unrelated later review imports.')
        c,_=book.sheet('Missing Pictures')
        for a,v in c.items():
            if re.fullmatch(r'B\d+',a) and v[1] in {KEEP,DUP}:
                r=a[1:]
                if v[1]==DUP:
                    edit('Missing Pictures','E'+r,'Historical');edit('Missing Pictures','F'+r,'Retired duplicate; retain source reference through keeper '+KEEP);edit('Missing Pictures','N'+r,'Retired')
                elif c.get('D'+r,('',''))[1]=='Individual':
                    edit('Missing Pictures','F'+r,'Closed by preservation of the existing saved keeper Primary in the exact owner merge.');edit('Missing Pictures','M'+r,'Saved Primary '+keep['file_id']+'; no new replacement guessed.');edit('Missing Pictures','N'+r,'Resolved');link('Missing Pictures','G'+r,keep['image_url'],'Saved keeper Primary')
        edit('Missing Pictures','A3','Five Primary choices remain open in this scoped publication. Dune Ripple2 Verdigris/Copper keeper Primary preserved. 28 context cases and one earlier series case stay held. Unrelated later choices remain queued.')
        comps,_=book.sheet('Components');cr=next(a[1:] for a,v in comps.items() if re.fullmatch(r'A\d+',a) and v[1]=='BC-DR-SPIRAL')
        edit('Components','D'+cr,formula='=COUNTIFS(\'Master Catalogue\'!$D$10:$D$198,A'+cr+',\'Master Catalogue\'!$L$10:$L$198,"<>Retired")')
        alias_sn='Aliases';cells,_=book.sheet(alias_sn);ar=max(int(re.search(r'\d+',a)[0]) for a in cells)+1
        for col,value in {'A':old['name'],'B':old['canonical_key'],'C':KEEP,'D':'Owner-confirmed duplicate catalogue option','E':note,'H':keep['file_id'],'I':keep['folder_id']}.items():edit(alias_sn,col+str(ar),value)
        link(alias_sn,'F'+str(ar),keep['image_url'],'Keeper image');link(alias_sn,'G'+str(ar),keep['folder_url'],'Containing folder')
        expansion={'sheet':alias_sn,'name':'Master_Aliases','range':f'A9:I{ar}'}
        previews=[['Master Catalogue',f'L{kr}:R{kr}','merge-primary-links'],['Aliases',f'A{ar}:E{ar}','merge-alias'],['Dune Ripple Merge','A2:F10','merge-evidence']]
        expected=[{'sheet':'Master Catalogue','cell':'B4','value':185},{'sheet':'Master Catalogue','cell':'F4','value':185},{'sheet':'Master Catalogue','cell':'H4','value':179},{'sheet':'Missing Pictures','cell':'B4','value':5}]
    else:
        kr,dr=row('Wall Sculptures',KEEP,'Q'),row('Wall Sculptures',DUP,'Q')
        edit('Wall Sculptures','A'+kr,keep['name']);edit('Wall Sculptures','B'+dr,'Retired alias');edit('Wall Sculptures','C'+dr,'Owner-confirmed duplicate; keeper '+KEEP);edit('Wall Sculptures','X'+dr,KEEP)
        edit('Wall Sculptures','AC'+dr,note);edit('Wall Sculptures','AC'+kr,book.sheet('Wall Sculptures')[0]['AC'+kr][1]+' | '+note)
        link('Wall Sculptures','L'+kr,keep['image_url'],'Image');link('Wall Sculptures','M'+kr,keep['folder_url'],'Folder');edit('Wall Sculptures','AB'+kr,keep['file_id']);edit('Wall Sculptures','AA'+kr,keep['folder_id'])
        for pid in [KEEP,DUP]:
            r=row('Products',pid)
            if pid==DUP:edit('Products','C'+r,'Retired');edit('Products','Y'+r,note)
            else:
                edit('Products','B'+r,keep['name']);edit('Products','Q'+r,' | '.join(keep['related_platform_offer_refs']));edit('Products','Z'+r,keep['file_id']);edit('Products','AE'+r,' | '.join(keep['retained_names']));edit('Products','AA'+r,'Saved keeper Primary; exact owner duplicate consolidation')
                link('Products','AB'+r,keep['image_url'],'Image');link('Products','AC'+r,keep['folder_url'],'Folder')
        edit('Products','A3','185 active options and three retired rows in this saved product table. The earlier Sandstone retirement remains separately retained in the189-row canonical register. Keeper specifications are unchanged.')
        edit('Wall Sculptures','A3','185 active options. Dune Ripple2 Verdigris is retained as an alias of Verdigris and Copper. Two saved Listing choices, Primary, qualified references and source links preserved. Unrelated pending imports remain separate.')
        edit('Overview','A3','185 active options;189 canonical records, four retired. Exact owner Dune Ripple2 consolidation:28 October2026. Earlier source inventories and In situ policy remain dated evidence.')
        edit('Overview','C7','185 active options. Four retired identities remain in canonical history; the saved Products table retains three retired rows.')
        c,_=book.sheet('Current image paths')
        for a,v in c.items():
            if re.fullmatch(r'E\d+',a) and v[1] in files:
                refs=files[v[1]]['selected_references'];edit('Current image paths','K'+a[1:],' | '.join(x['name']+' — '+x['role'] for x in refs))
        edit('Current image paths','A3','Native image paths retain the19:03UTC 27October inventory cut. Selected references reflect only the28October owner Dune Ripple2 consolidation; stable file/folder IDs and other pending imports remain unchanged.')
        alias_sn='Aliases and history';cells,_=book.sheet(alias_sn);ar=max(int(re.search(r'\d+',a)[0]) for a in cells)+1
        for col,value in {'A':decision['decision_id'],'B':old['name'],'C':KEEP,'D':'Owner-confirmed duplicate catalogue option','E':decision['owner_quote'],'F':decision['instruction_path'],'G':0,'H':note}.items():edit(alias_sn,col+str(ar),value)
        edit(alias_sn,'A3',str(ar-6)+' retained alias/history records. Exact Dune Ripple2 consolidation added28October2026; earlier records retained.')
        worksheet=book.sheets[alias_sn];rp=str(PurePosixPath(worksheet).parent/'_rels'/(PurePosixPath(worksheet).name+'.rels'));table_name=None
        for r in E.fromstring(book.zip.read(rp)):
            if r.get('Type').endswith('/table'):
                table_name=E.fromstring(book.zip.read(native.resolve(worksheet,r.get('Target')))).get('name');break
        assert table_name
        expansion={'sheet':alias_sn,'name':table_name,'range':f'A6:H{ar}'}
        previews=[['Wall Sculptures',f'L{kr}:M{kr}','unified-merge-primary'],['Aliases and history',f'A{ar}:D{ar}','unified-merge-alias'],['Dune Ripple Merge','A2:F10','unified-merge-evidence']]
        expected=[{'sheet':'Overview','cell':'B7','value':185}]
    expected.extend([{'sheet':'Dune Ripple Merge','cell':'B4','value':185},{'sheet':'Dune Ripple Merge','cell':'D4','value':189},{'sheet':'Dune Ripple Merge','cell':'F4','value':4},{'sheet':'Dune Ripple Merge','cell':'B5','value':1110}])
    plans.append({'key':kind,'source':str(manifest['sources'][kind]['snapshot']),'source_sha256':manifest['sources'][kind]['sha256'],'output':str(OUT/filename),'edits':list(edits.values()),'expected':expected,'previews':previews,'new_sheet':'Dune Ripple Merge','replace_image_sheet':False,'table_expansion':expansion})
    book.close()
write(H/'workbook-edit-plan.json',{'plans':plans})
evidence=[]
def add(kind,id,name,value,image='',folder='',scope=''):
    evidence.append({'kind':kind,'id':id,'name':name,'value':value,'image':image,'folder':folder,'qualification':scope})
add('Keeper',KEEP,keep['name'],'Active individual option',keep['image_url'],keep['folder_url'],'Existing working specifications and review choices preserved.')
add('Retired alias',DUP,old['name'],KEEP,keep['image_url'],keep['folder_url'],'Retained history; not an extra sculpture or finish option.')
for scope in keep['source_scopes']:add('Source scope',scope,'Retained source identity',KEEP,scope='No source field or exact platform-variant claim is upgraded.')
for who,record in [('Keeper working field',keep),('Retired historical field',old)]:
    for key,v in record['master_fields'].items():add(who,record['product_id'],key,v['display'],scope=v.get('state',''))
for r in keep['current_saved_listing_images']:add('Saved Primary' if r['review_data'].get('primary') else 'Saved Listing image',r['file_id'],keep['name'],', '.join(r['review_data']['uses']),r['image_url'],r['folder_url'],'Exact keeper review preserved; version '+str(r['review_version'])+'. No new physical or native-variant inference.')
r=files['id:cnqzTNngPVsAAAAAAAykxw'];add('Qualified reference',r['file_id'],'Prior accepted context reference','Carried with its original source qualification',r['image_url'],r['folder_url'],'Does not select a new context Primary or remove an owner hold.')
add('Platform source','O009','Prior Verdigris source record','Retained through the exact owner alias merge',scope='Finish, size, build, price, stock and exact current native variant/SKU retain their source qualifications.')
add('Owner decision',decision['decision_id'],'28 October2026',decision['owner_quote'],scope=decision['handling'])
write(H/'merge-evidence-rows.json',evidence)
print(json.dumps({'edits':{p['key']:len(p['edits']) for p in plans},'new_evidence_rows':len(evidence),'active_options':185}))
