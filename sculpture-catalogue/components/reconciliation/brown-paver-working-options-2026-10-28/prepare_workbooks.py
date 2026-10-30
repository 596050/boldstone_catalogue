"""Declare the two authorised working options and their affected workbook views."""
from common import *
from xml.etree import ElementTree as E
import re

new_options=read(H/'new-paver-options.json')
new_components=read(H/'new-paver-components.json')
fields=['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability']
plans=[]
for kind,filename in [('core_workbook','Boldstone_Sculpture_Master_Catalogue_2026-10-28_v9.xlsx'),('comprehensive_workbook','Boldstone_Wall_Sculptures_Unified_2026-10-28_v9.xlsx')]:
    book=Book(manifest['sources'][kind]['snapshot']);edits={};expansions=[]
    def edit(sn,cell,value=None,formula=None):
        before=book.sheet(sn)[0].get(cell)
        if formula is None and value in ('',None) and before in (None,('text','')):return
        wanted=('formula',formula.lstrip('=')) if formula is not None else ('number',str(value)) if isinstance(value,(int,float)) else ('text',value)
        if before!=wanted:edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'kind':'formula' if formula is not None else 'value',**({'formula':formula} if formula is not None else {'value':value})}
    def link(sn,cell,url,label):
        before=book.sheet(sn)[0].get(cell)
        formula='=HYPERLINK("'+url.replace('"','""')+'","'+label.replace('"','""')+'")'
        edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'before_href':book.sheet(sn)[1].get(cell),'kind':'hyperlink','formula':formula,'url':url,'label':label,'keep_formula':url.startswith('#') or bool(before and before[0]=='formula')}
    def values(sn,row,cols):
        for col,val in cols.items():edit(sn,col+str(row),val)
    def expand(sn,end):
        sp=book.sheets[sn];rp=str(Path(sp).parent/'_rels'/(Path(sp).name+'.rels'))
        tables=[]
        for r in E.fromstring(book.zip.read(rp)):
            if r.get('Type').endswith('/table'):
                t=E.fromstring(book.zip.read(native.resolve(sp,r.get('Target'))));tables.append(t)
        assert len(tables)==1,sn
        t=tables[0];old=t.get('ref');rng=re.sub(r'\d+$',str(end),old)
        expansions.append({'sheet':sn,'name':t.get('name'),'range':rng,'before_range':old})
    if kind=='core_workbook':
        edit('Master Catalogue','A3','187 active working options;191 retained records, four retired. Two separately buyable Brown pavers added with provisional component IDs. Their six working fields are estimates or owner policies; audited images are references with Primary unselected. Earlier records and queued decisions preserved.')
        edit('Master Catalogue','C4','Active component IDs incl. provisional')
        edit('Master Catalogue','G4','Active image references')
        for cell,f in {'B4':'=COUNTIFS(A10:A200,"<>",L10:L200,"<>Retired")','D4':'=COUNTIF(\'Components\'!D10:D123,">0")','F4':'=COUNTIFS(K10:K200,6,L10:L200,"<>Retired")','H4':'=COUNTIFS(Q10:Q200,"<>Unbound",L10:L200,"<>Retired")'}.items():edit('Master Catalogue',cell,formula=f)
        edit('Specifications','A3','1,122 active working field groups across187 options;1,146 retained field rows. Twelve new Brown paver proposals are labelled estimates, hypotheses or standing owner policies. The1,668 original review assertions remain unchanged in the canonical register.')
        edit('Components','A3','112 earlier identified component records plus two provisional working Brown paver components. Active component IDs include these provisional records; they are not proof of two additional moulds or physical designs. Existing working design groups and their qualifications remain historical evidence.')
        edit('Photo Coverage','A3','187 active options;181 source image references, including two new Brown references with Primary unselected. Technical image classifications stay separate from Listing/Primary approval. Thirty unresolved context cases remain under the standing owner hold; no new context question inferred.')
        for cell in ['B4','D4','F4','B5','D5','F5']:
            f=book.sheet('Photo Coverage')[0][cell][1].replace('198','200');edit('Photo Coverage',cell,formula='='+f)
        edit('Missing Pictures','A3','Five earlier Primary/capture requests remain in this scoped source. Two new Brown pavers have audited appearance references and need explicit Primary selection, not new capture by default. Thirty context cases and one earlier series case stay held; unrelated later choices remain queued.')
        for cell in ['B4','D4','F4']:edit('Missing Pictures',cell,formula='='+book.sheet('Missing Pictures')[0][cell][1].replace('234','238'))
        edit('Missing Pictures','G4','New Primary choices');edit('Missing Pictures','H4',formula='=COUNTIFS(E10:E238,"Choose Primary",N10:N238,"Open")')
        for n,(o,c) in enumerate(zip(new_options,new_components)):
            r=199+n;pid=o['product_id'];cid=c['component_id'];scope=' | '.join(o['source_scopes'])
            values('Master Catalogue',r,{'A':pid,'B':o['name'],'C':o['family'],'D':cid,'M':o['identity_basis'],'Q':o['file_id'],'R':o['folder_id'],'S':'Custom orientation offered; actual mounting and orientation unverified','V':o['source_scope_notes'],'X':o['platform_scope_note'],'Y':scope})
            link('Master Catalogue','N'+str(r),o['image_url'],'Working reference — Primary unselected');link('Master Catalogue','O'+str(r),o['folder_url'],'Containing folder')
            link('Master Catalogue','P'+str(r),'#\'Specifications\'!A'+str(1144+n*6),'Six qualified working fields')
            for col,field in zip('EFGHIJ',fields):
                f=f'=IF(COUNTIFS(\'Specifications\'!$P$10:$P$1155,$A{r}&"::{field}",\'Specifications\'!$Q$10:$Q$1155,1)=1,INDEX(\'Specifications\'!$D$10:$D$1155,MATCH($A{r}&"::{field}",\'Specifications\'!$P$10:$P$1155,0)),"Working detail missing, unaccepted or duplicated")'
                edit('Master Catalogue',col+str(r),formula=f)
            edit('Master Catalogue','K'+str(r),formula=f'=COUNTIFS(\'Specifications\'!$A$10:$A$1155,A{r},\'Specifications\'!$Q$10:$Q$1155,1)')
            edit('Master Catalogue','L'+str(r),formula=f'=IF(K{r}=6,"Six working fields recorded","Working details incomplete")')
            for i,field in enumerate(fields):
                sr=1144+n*6+i;v=o['master_fields'][field]
                values('Specifications',sr,{'A':pid,'B':o['name'],'C':field,'D':v['display'],'E':v['state'],'F':v['basis'],'G':scope,'I':1,'L':o['file_id'],'M':o['folder_id'],'N':' | '.join(v['proposal_ids']),'O':'New owner-requested working Brown paver option; no physical or native-platform verification.','P':pid+'::'+field})
                link('Specifications','J'+str(sr),o['image_url'],'Working appearance reference');link('Specifications','K'+str(sr),o['folder_url'],'Containing folder')
                edit('Specifications','Q'+str(sr),formula=f'=IF(AND(I{sr}=1,COUNTBLANK(D{sr})=0,COUNTIFS($P$10:$P$1155,P{sr})=1),1,0)')
            cr=122+n
            values('Components',cr,{'A':cid,'B':c['name'],'C':c['family'],'E':c['scope_note'],'H':o['file_id'],'I':o['folder_id'],'K':o['name']})
            edit('Components','D'+str(cr),formula=f'=COUNTIFS(\'Master Catalogue\'!$D$10:$D$200,A{cr},\'Master Catalogue\'!$L$10:$L$200,"<>Retired")')
            link('Components','F'+str(cr),o['image_url'],'Working reference');link('Components','G'+str(cr),o['folder_url'],'Containing folder')
            values('Photo Coverage',r,{'A':pid,'B':o['name'],'C':o['photo_coverage']['individual'],'F':'Owner hold','I':'Optional / no fixed set','L':o['source_scope_notes'],'M':o['file_id'],'N':o['folder_id'],'S':'Audited whole-component appearance reference; no saved image-use approval.','T':'Retained PNG; photographic/processed/rendered lineage unconfirmed.','U':'Standing hold applies to all unresolved wider-display requests until owner resumes.','V':'No mandatory fixed set or unproved series membership.'})
            link('Photo Coverage','D'+str(r),o['image_url'],'Working reference — Primary unselected');link('Photo Coverage','E'+str(r),o['folder_url'],'Containing folder')
            for rr,role,action,state,detail in [(235+n*2,'Individual','Choose Primary','Open','Audited full-component reference exists. Explicit Listing and Primary selection is still required; no auto-approval.'),(236+n*2,'In situ','Find / capture','Owner hold','No verified broader-display reference. Standing owner deferral applies; do not repeat the question until resumed.')]:
                values('Missing Pictures',rr,{'A':'Review','B':pid,'C':o['name'],'D':role,'E':action,'F':detail,'I':o['file_id'],'J':o['folder_id'],'K':o['source_scope_notes'],'L':'Owner-requested working product and audited native folder/file IDs.','M':'Source reference only; saved Listing, Advertising and Primary remain unselected.','N':state})
                link('Missing Pictures','G'+str(rr),o['image_url'],'Working reference');link('Missing Pictures','H'+str(rr),o['folder_url'],'Containing folder')
        for sn,end in [('Master Catalogue',200),('Specifications',1155),('Components',123),('Photo Coverage',200),('Missing Pictures',238)]:expand(sn,end)
        expected=[{'sheet':'Master Catalogue','cell':'B4','value':187},{'sheet':'Master Catalogue','cell':'D4','value':113},{'sheet':'Master Catalogue','cell':'F4','value':187},{'sheet':'Master Catalogue','cell':'H4','value':181},{'sheet':'Master Catalogue','cell':'K199','value':6},{'sheet':'Master Catalogue','cell':'K200','value':6},{'sheet':'Missing Pictures','cell':'B4','value':5},{'sheet':'Missing Pictures','cell':'H4','value':2}]
        previews=[['Master Catalogue','A2:H4','core-summary'],['Master Catalogue','A199:D200','core-new-identities'],['Master Catalogue','M199:R200','core-new-reference-links'],['Specifications','B1144:F1149','core-new-working-fields'],['Missing Pictures','C235:F238','core-primary-and-holds'],['Brown Paver Options','A2:G11','core-paver-review']]
        row_formats=[{'sheet':'Master Catalogue','first':199,'last':200,'height':132},{'sheet':'Specifications','first':1144,'last':1155,'height':144},{'sheet':'Components','first':122,'last':123,'height':150},{'sheet':'Photo Coverage','first':199,'last':200,'height':132},{'sheet':'Missing Pictures','first':235,'last':238,'height':132}]
    else:
        edit('Wall Sculptures','A3','187 active working options. Two separately buyable Brown paver options added with qualified visual CRS2/CRS1 relationships. Their estimates, source image references and provisional identities do not establish native SKU, physical mould, material or saved Primary/Listing approval.')
        edit('Products','A3','187 active options and three retired rows in this saved product table;191 canonical records include the separately retained earlier Sandstone retirement. Two new Brown pavers have working fields and reference-only images; no automatic Primary or Listing selection.')
        edit('Overview','A3','187 active working options;191 retained records, four retired. Two provisional Brown pavers added with labelled working fields; physical specifications and stock remain unverified.')
        edits[('Overview','A3')]['navigation_refinement']=True
        edit('Overview','C7','187 active options. Four retired identities remain in canonical history; this saved Products table retains three retired rows. Brown paver identities are provisional working component options.')
        edit('Specifications','A3','1,146 retained working field rows, including12 new qualified Brown proposals. Active working groups:1,122. The1,668 original source review assertions are preserved separately in the canonical register.')
        edit('Components','A3','114 retained component records:112 earlier identified records plus2 provisional Brown paver working components. No additional physical mould or unique-design count is asserted.')
        for cell in ['B5','D5','F5','H5']:edit('Wall Sculptures',cell,formula='='+book.sheet('Wall Sculptures')[0][cell][1].replace('421','423'))
        for a,v in book.sheet('Overview')[0].items():
            if v[0]=='formula':
                f=re.sub(r'(\$?[A-Z]+\$?)194\b',r'\g<1>196',v[1]);f=re.sub(r'(\$?[A-Z]+\$?)1140\b',r'\g<1>1152',f);f=re.sub(r'(\$?[A-Z]+\$?)118\b',r'\g<1>120',f)
                if f!=v[1]:edit('Overview',a,formula='='+f)
        for n,(o,c) in enumerate(zip(new_options,new_components)):
            r=422+n;pid=o['product_id'];cid=c['component_id'];scope=' | '.join(o['source_scopes']);fs={f:o['master_fields'][f]['display'] for f in fields}
            values('Wall Sculptures',r,{'A':o['name'],'B':'Individual option','C':'Owner-requested working option; provisional component identity','D':o['family'],'E':'Brown — working build/finish description','P':o['canonical_key'],'Q':pid,'X':'Visual correspondence only: '+o['visual_design_relationships'][0]['historical_code'],'Y':0,'Z':0,'AA':o['folder_id'],'AB':o['file_id'],'AC':o['source_scope_notes'],'AE':o['identity_basis'],'AG':scope,'AH':'Reference-only source image. Primary, Listing and Advertising unselected. No proved Squarespace/Shopify SKU or variant.'})
            for col,field in zip('FGHIJK',fields):edit('Wall Sculptures',col+str(r),fs[field])
            link('Wall Sculptures','L'+str(r),o['image_url'],'Working reference — Primary unselected');link('Wall Sculptures','M'+str(r),o['folder_url'],'Containing folder')
            pr=195+n
            values('Products',pr,{'A':pid,'B':o['name'],'C':'Working option; provisional component identity','D':o['family'],'E':cid,'F':cid,'G':fs[fields[0]],'H':fs[fields[1]],'I':fs[fields[2]],'J':fs[fields[3]],'K':225,'M':fs[fields[4]],'N':fs[fields[5]],'O':1,'P':2,'W':'Brown working option','X':'NEW:'+cid+':BROWN-WORKING','Y':o['source_scope_notes'],'Z':o['file_id'],'AA':'Working reference; Primary unselected','AE':o['name'],'AF':'Six working fields; physical details unverified. No verified live price or native-platform offer.'})
            link('Products','AB'+str(pr),o['image_url'],'Working appearance reference');link('Products','AC'+str(pr),o['folder_url'],'Containing folder')
            for i,field in enumerate(fields):
                sr=1141+n*6+i;v=o['master_fields'][field]
                values('Specifications',sr,{'A':pid+' | '+field,'B':pid,'C':o['name'],'D':'Active','E':field,'F':v['display'],'G':v['state'],'H':v['basis'],'I':1,'J':0,'K':scope,'L':json.dumps(v['source_references'],ensure_ascii=False),'M':json.dumps({'proposal_ids':v['proposal_ids']},ensure_ascii=False)})
            cr=119+n
            values('Components',cr,{'A':cid,'B':c['name'],'C':c['family'],'D':'Provisional working component','E':pid,'F':o['name'],'G':1,'I':o['name'],'J':c['scope_note']})
            link('Components','K'+str(cr),o['image_url'],'Working appearance reference');link('Components','L'+str(cr),o['folder_url'],'Containing folder')
        for a,v in book.sheet('Current image paths')[0].items():
            if re.fullmatch(r'E\d+',a) and v[1] in {o['file_id'] for o in new_options}:
                refs=files[v[1]]['selected_references'];edit('Current image paths','K'+a[1:],' | '.join(x['name']+' — '+x['role'] for x in refs))
        edit('Current image paths','A3','Native image paths retain the19:03UTC27October inventory cut. Two audited Brown working references are associated with their new provisional options, with Primary unselected. Stable file/folder IDs, previous references, exclusions and unrelated pending imports are preserved.')
        for sn,end in [('Wall Sculptures',423),('Products',196),('Specifications',1152),('Components',120)]:expand(sn,end)
        expected=[{'sheet':'Overview','cell':'B7','value':187},{'sheet':'Wall Sculptures','cell':'B5','value':187}]
        previews=[['Overview','A2:C9','unified-summary'],['Wall Sculptures','A422:E423','unified-new-identities'],['Products','K195:P196','unified-new-selling-estimates'],['Components','A119:D120','unified-provisional-components'],['Brown Paver Options','A2:G11','unified-paver-review']]
        row_formats=[{'sheet':'Wall Sculptures','first':422,'last':423,'height':144},{'sheet':'Products','first':195,'last':196,'height':144},{'sheet':'Specifications','first':1141,'last':1152,'height':144},{'sheet':'Components','first':119,'last':120,'height':150}]
    expected += [{'sheet':'Brown Paver Options','cell':'B4','value':187},{'sheet':'Brown Paver Options','cell':'D4','value':191},{'sheet':'Brown Paver Options','cell':'F4','value':2},{'sheet':'Brown Paver Options','cell':'B5','value':1122}]
    plans.append({'key':kind,'source':manifest['sources'][kind]['snapshot'],'source_sha256':manifest['sources'][kind]['sha256'],'output':str(OUT/filename),'edits':list(edits.values()),'table_expansions':expansions,'expected':expected,'previews':previews,'row_formats':row_formats,'new_sheet':'Brown Paver Options','replace_image_sheet':False})
    book.close()
rows=[]
for o in new_options:
    rows.append({'kind':'Working option','id':o['product_id'],'name':o['name'],'value':'Separate buyable component; provisional identity','image':o['image_url'],'folder':o['folder_url'],'qualification':o['source_scope_notes']})
    rows.append({'kind':'Image reference','id':o['file_id'],'name':'Primary unselected','value':'Audited complete-component appearance reference','image':o['image_url'],'folder':o['folder_url'],'qualification':'No saved Listing, Advertising or Primary approval. The retained PNG does not certify photographic lineage or physical material.'})
    for f in fields:
        v=o['master_fields'][f];rows.append({'kind':'Working specification','id':o['product_id'],'name':f,'value':v['display'],'image':o['image_url'],'folder':o['folder_url'],'qualification':v['state']+' — '+v['basis']})
write(H/'paver-evidence-rows.json',rows)
write(H/'workbook-edit-plan.json',{'plans':plans})
print(json.dumps({'edits':{p['key']:len(p['edits']) for p in plans},'table_expansions':{p['key']:len(p['table_expansions']) for p in plans},'new_evidence_rows':len(rows)}))
