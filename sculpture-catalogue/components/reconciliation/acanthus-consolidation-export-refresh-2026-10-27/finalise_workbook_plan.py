"""Bind the owner-confirmed retirement to current views, keeping source history."""
from common import *
import re

KEEP='BSI-93ADE7C4103D'
OLD='BSI-E7CDC2CFAC9D'
TITLE='Acanthus Two Leaves White'
NOTE='Owner confirmed Deco Two Leaves — White duplicates Acanthus Two Leaves White on 27 October 2026. Use BSI-93ADE7C4103D. Retain this row and its different source material/price claims as history. No separate listing, photograph or specification task.'
report=read(H/'register-preparation.json')
plan=read(H/'workbook-edit-plan.json')
active_components={o['canonical_component_id'] for o in g['options'] if o['product_id'] in active and o.get('canonical_component_id')}
oldactive=read(manifest['sources']['register']['snapshot'])
native=read(H.parent/'acanthus-duplicate-consolidation-2026-10-27/owner-evidence/verification.json')['after']
extra=[('id:cnqzTNngPVsAAAAAAAyj8Q','Additional listing and advertising image','The owner-moved image is reviewed for Listing and Advertising. It is not Primary.'),('id:cnqzTNngPVsAAAAAAAyluQ','Additional qualified context','Acanthus Two Leaves White is the leftmost panel in this group. Scene origin, scale and installation remain unverified. Existing keeper context is unchanged.')]
for p in plan['plans']:
    book=Book(p['source']); edits={(x['sheet'],x['cell']):x for x in p['edits']}
    def put(sn,cell,value=None,formula=None):
        before=book.sheet(sn)[0].get(cell)
        edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'kind':'formula' if formula is not None else 'value',**({'formula':formula} if formula is not None else {'value':value})}
    def link(sn,cell,url,label):
        c,l=book.sheet(sn);before=c.get(cell)
        f='=HYPERLINK("'+url.replace('"','""')+'","'+label.replace('"','""')+'")'
        edits[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'before_href':l.get(cell),'kind':'hyperlink','formula':f,'url':url,'label':label,'keep_formula':bool(before and before[0]=='formula')}
    def rows(sn,idcol,pid):
        c,_=book.sheet(sn)
        return [re.search(r'\d+',a)[0] for a,v in c.items() if re.fullmatch(idcol+r'\d+',a) and v[1] in {pid,'INDIVIDUAL:'+pid}]
    if p['key']=='core_workbook':
        for sn,idcol,namecol in [('Master Catalogue','A','B'),('Specifications','A','B'),('Photo Coverage','A','B'),('Missing Pictures','B','C'),('Listing Reconciliation','A','B'),('Listing Issues','A','B'),('Listing Resolution','A','B'),('Draft Listings','A','B'),('Selling Details','A','B')]:
            for r in rows(sn,idcol,KEEP):put(sn,namecol+r,TITLE)
        for r in rows('Master Catalogue','A',OLD):
            put('Master Catalogue','L'+r,'Retired');put('Master Catalogue','M'+r,'Owner-confirmed duplicate');put('Master Catalogue','V'+r,NOTE)
        for r in rows('Specifications','A',OLD):put('Specifications','E'+r,'Retired / historical detail. Earlier review state retained in canonical source history.')
        for r in rows('Photo Coverage','A',OLD):
            for col in ['C','F','I']:put('Photo Coverage',col+r,'Retired / not applicable')
            put('Photo Coverage','L'+r,NOTE)
            # A missing old series reference stays historical, without a live image link.
            link('Photo Coverage','J'+r,options[OLD]['current_series_reference']['folder_url'],'Historical folder (image unavailable)')
        for r in rows('Missing Pictures','B',OLD):put('Missing Pictures','N'+r,'Retired');put('Missing Pictures','M'+r,NOTE)
        for sn,col in [('Listing Reconciliation','C'),('Listing Resolution','C'),('Selling Details','P')]:
            for r in rows(sn,'A',OLD):put(sn,col+r,'Retired duplicate — use '+KEEP)
        for r in rows('Listing Resolution','A',OLD):put('Listing Resolution','Q'+r,NOTE)
        for r in rows('Listing Issues','A',OLD):put('Listing Issues','P'+r,'Resolved — consolidated duplicate')
        for r in rows('Selling Details','A',OLD):put('Selling Details','Q'+r,NOTE)
        for r in rows('Components','A','BC-DP-LEAVES'):
            put('Components','D'+r,formula='=COUNTIFS(\'Master Catalogue\'!$D$10:$D$198,A'+r+',\'Master Catalogue\'!$L$10:$L$198,"<>Retired")')
            put('Components','E'+r,'Historical duplicate component. Current option is '+KEEP+' in Acanthus. Retained names and source IDs are history.')
        put('Master Catalogue','A3','186 active options. 189 retained records include three retirements. Acanthus Two Leaves White is the surviving identity. Current navigation uses the captured census and verified absence evidence.')
        put('Master Catalogue','C4','Active component IDs');put('Master Catalogue','D4',formula='=COUNTIF(\'Components\'!D10:D121,">0")')
        put('Master Catalogue','F4',formula='=COUNTIFS(K10:K198,6,L10:L198,"<>Retired")')
        put('Specifications','A3','1,116 active working field groups across 186 options. All 1,134 retained field rows and earlier source values remain available, including retired duplicates.')
        put('Photo Coverage','A3',f"186 active options. {report['current_primary_references']} current Primary references and {report['current_context_references']} qualified context references. Census/review cut: {manifest['recorded_utc']}.")
        put('Missing Pictures','A3','One Primary selection and six series replacements remain open. 27 context cases and the earlier Copper series case remain on owner hold. The Acanthus duplicate has no separate task.')
        put('Selling Details','A3','186 active options. Working prices and made-to-order policies retain their existing qualifications. Retired option prices remain historical and do not create separate offers.')
        # These three new absence cases are NOT labelled as owner deletions.
        for r in ['228','229','230']:
            put('Missing Pictures','F'+r,'Previous shared series image is native NOT_FOUND. Find a surviving qualified group photograph.')
            put('Missing Pictures','L'+r,'Absent from the complete scoped census; separately reported native NOT_FOUND. Cause is not inferred.')
        for i,(fid,label,qualification) in enumerate(extra,23):
            r=str(i);f=files[fid]
            for col,value in {'A':'ACANTHUS-CONSOLIDATION-'+str(i-22),'B':TITLE,'C':label,'D':qualification,'E':'Existing identity; no new option','H':KEEP+' | '+fid+' | '+f['folder_id']}.items():put('References and Gaps',col+r,value)
            link('References and Gaps','F'+r,f['image_url'],'Photograph');link('References and Gaps','G'+r,f['folder_url'],'Containing folder')
        p['expected']=[{'sheet':'Master Catalogue','cell':'B4','value':186},{'sheet':'Master Catalogue','cell':'D4','value':len(active_components)},{'sheet':'Master Catalogue','cell':'F4','value':186},{'sheet':'Master Catalogue','cell':'H4','value':report['current_primary_references']},{'sheet':'Missing Pictures','cell':'B4','value':7}]
        p['previews']=[['Master Catalogue','A14:D20','core-acanthus-name'],['Master Catalogue','A41:D46','core-duplicate-history'],['References and Gaps','A23:G24','core-extra-references']]
    else:
        for sn,idcol,namecol in [('Wall Sculptures','Q','A'),('Products','A','B'),('Specifications','B','C')]:
            for r in rows(sn,idcol,KEEP):put(sn,namecol+r,TITLE)
        for r in rows('Products','A',OLD):
            put('Products','C'+r,'Retired');put('Products','Y'+r,NOTE);put('Products','AA'+r,'Historical reference — duplicate consolidated');put('Products','AF'+r,NOTE)
        for r in rows('Wall Sculptures','Q',OLD):
            put('Wall Sculptures','B'+r,'Retired option history');put('Wall Sculptures','C'+r,'Owner-confirmed duplicate');put('Wall Sculptures','AE'+r,'Use '+KEEP+'. No duplicate offer or draft task.');put('Wall Sculptures','AH'+r,NOTE)
        for r in rows('Specifications','B',OLD):put('Specifications','D'+r,'Retired')
        for r in rows('Components','A','BC-DP-LEAVES'):
            put('Components','D'+r,'RETIRED_DUPLICATE_COMPONENT');put('Components','J'+r,'Retained source identity. Active counterpart is Acanthus Two Leaves White ('+KEEP+').')
        put('Products','A3','186 active options and two retired rows in this saved product table. The earlier Sandstone retirement is retained separately in the 189-row canonical register.')
        put('Overview','A3','186 active options after the owner-confirmed Acanthus duplicate consolidation. Complete source history, saved image qualifications and working specifications are preserved.')
        put('Overview','C7','186 active options. Three retired identities remain in canonical history; the saved Products table retains two retired rows.')
        put('Wall Sculptures','A3','186 active options. Deco Two Leaves — White is consolidated into Acanthus Two Leaves White. Current image paths use the captured native census; source and specification history remain preserved.')
        p['previews']=[['Wall Sculptures','A13:E16','unified-acanthus-name'],['Wall Sculptures','A57:E60','unified-duplicate-history'],['Current image paths','A2:D10','current-image-paths']]
    p['edits']=list(edits.values());book.close()
write(H/'workbook-edit-plan.json',plan)
write(H/'workbook-scope.json',{'active_options':186,'retained_options':189,'active_component_ids':len(active_components),'physical_or_commercial_values_changed':0,'extra_keeper_references':extra,'edits':{p['key']:len(p['edits']) for p in plan['plans']}})
print(json.dumps({'edits':{p['key']:len(p['edits']) for p in plan['plans']},'active_component_ids':len(active_components)}))
