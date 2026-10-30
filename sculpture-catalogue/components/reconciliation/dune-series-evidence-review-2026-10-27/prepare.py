"""Map three already identified White components into an existing group scene."""
from pathlib import Path
import json,shutil
HERE=Path(__file__).resolve().parent
m=json.loads((HERE/'input-manifest.json').read_text())
if not (HERE/'canonical-master-register.json').exists():shutil.copyfile(m['sources']['register']['snapshot'],HERE/'canonical-master-register.json')
from common import *
from copy import deepcopy
from datetime import datetime,timezone
from html import escape
import hashlib,re,sqlite3,subprocess,urllib.request

FID='id:cnqzTNngPVsAAAAAAAuejQ'
POSITIONS={'BSI-09C1A55D460D':'Leftmost panel: complete flowing-wave DR1 design with turquoise verdigris and rust patches. Colour/size variations remain qualified; Primary choice remains unbound.','BSI-8DDEA2FEC9DA':'Middle panel: recognisable double-curl DR2 design with the Rust finish; adjacent panels supply series context.','BSI-6F3C6CD908A0':'Rightmost panel: double-curl DR2 design with dark bronze/blue verdigris patina, matching the retained individual reference; edge overlap and strong directional lighting remain qualified.'}
original=deepcopy(g);selected=files[FID]
boot=json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap',timeout=60));live=boot['source']['live_dropbox'];census=read(live['path']);native_row=census['records'][FID]
local=H/'originals/cnqzTNngPVsAAAAAAAuejQ.JPG'
digest=hashlib.sha256()
with local.open('rb') as f:
    while block:=f.read(4*1024*1024):digest.update(hashlib.sha256(block).digest())
assert digest.hexdigest()==native_row['content_hash']==selected['content_hash']
assert native_row['folder_id']==selected['folder_id'] and native_row['path']==selected['path']
QUAL='Qualified series/display reference. Whole existing image retained. Scene origin, depicted scale and actual installation are unverified. No dimensions, material, price, stock or exact platform variant inferred.'
evidence={'reviewed_utc':datetime.now(timezone.utc).isoformat(),'file_id':FID,'folder_id':selected['folder_id'],'native_snapshot':live,'native_record':native_row,'local_original':str(local),'local_original_sha256':sha(local),'dropbox_content_hash':digest.hexdigest(),'bytes_match_current_native':True,'image_url':selected['image_url'],'folder_url':selected['folder_url'],'positions':POSITIONS,'qualification':QUAL,'new_owner_identity_or_specification_response_inferred':False,'native_app_or_platform_writes':0}
write(H/'visual-series-evidence.json',evidence)
for o in g['options']:
    if o['product_id'] not in POSITIONS:continue
    assert o['product_id'] in active and not o.get('current_series_reference')
    o['current_series_reference']={k:selected[k] for k in ['file_id','folder_id','image_url','folder_url']}
    o['current_series_reference'].update(scope=QUAL,position=POSITIONS[o['product_id']],basis='Reviewed current native original against retained individual design references',evidence=str(H/'visual-series-evidence.json'),evidence_sha256=sha(H/'visual-series-evidence.json'))
    o['photo_coverage']['series']='Available — qualified group display reference'
for a,b in zip(original['options'],g['options']):
    assert {k for k in set(a)|set(b) if a.get(k)!=b.get(k)} <= ({'current_series_reference','photo_coverage'} if a['product_id'] in POSITIONS else set())
    for k in ['specifications','master_fields','selling_details','file_id','context_file_id','name']:assert a.get(k)==b.get(k)
g.setdefault('historical_qualified_series_reviews',[]).append(deepcopy(g['latest_qualified_series_review']))
g['latest_qualified_series_review']=evidence
write(H/'canonical-master-register.json',g)
for ref in overlay:
    if ref['file_id']==FID:
        for pid in POSITIONS:ref['selected_references'].append({'product_id':pid,'name':options[pid]['name'],'role':'series'})
write(H/'current-image-overlay.json',overlay)
plans=[]
for key,filename in [('core_workbook','Boldstone_Sculpture_Master_Catalogue_2026-10-27_v5.xlsx'),('comprehensive_workbook','Boldstone_Wall_Sculptures_Unified_2026-10-27_v5.xlsx')]:
    book=Book(manifest['sources'][key]['snapshot']);edits=[]
    def put(sn,cell,value):edits.append({'sheet':sn,'cell':cell,'before':book.sheet(sn)[0].get(cell),'kind':'value','value':value})
    def link(sn,cell,url,label):
        c,l=book.sheet(sn);old=c.get(cell);f='=HYPERLINK("'+url.replace('"','""')+'","'+label+'")'
        edits.append({'sheet':sn,'cell':cell,'before':old,'before_href':l.get(cell),'kind':'hyperlink','formula':f,'url':url,'label':label,'keep_formula':bool(old and old[0]=='formula')})
    if key=='core_workbook':
        c,_=book.sheet('Photo Coverage')
        for cell,value in c.items():
            if not re.fullmatch(r'A\d+',cell) or value[1] not in POSITIONS:continue
            pid=value[1];r=cell[1:];put('Photo Coverage','I'+r,'Available')
            link('Photo Coverage','J'+r,selected['image_url'],'Qualified series image');link('Photo Coverage','K'+r,selected['folder_url'],'Actual containing folder')
            put('Photo Coverage','Q'+r,FID);put('Photo Coverage','R'+r,selected['folder_id'])
            put('Photo Coverage','L'+r,c.get('L'+r,('',''))[1]+' | Replacement series reference: '+POSITIONS[pid]+' '+QUAL)
        c,_=book.sheet('Missing Pictures')
        for cell,value in c.items():
            if not re.fullmatch(r'B\d+',cell) or value[1] not in POSITIONS:continue
            r=cell[1:]
            if c.get('D'+r,('',''))[1]!='Series':continue
            for col,val in {'F':'Mapped the existing identifiable White group display as a qualified series reference.','I':FID,'J':selected['folder_id'],'K':POSITIONS[value[1]],'L':QUAL,'M':'Visual mapping under the standing catalogue task. No new owner identity/specification response inferred.','N':'Resolved'}.items():put('Missing Pictures',col+r,val)
            link('Missing Pictures','G'+r,selected['image_url'],'Qualified group photograph');link('Missing Pictures','H'+r,selected['folder_url'],'Containing folder')
        put('Missing Pictures','A3','One Primary selection remains open. All six newly missing series roles now have qualified group references. 27 context cases and the earlier Copper series case remain held.')
        put('Photo Coverage','A3','186 active options. Three Dune Ripple series roles mapped from the current native original. Existing Primary/context choices, scene qualifications and all physical specifications are retained.')
        previews=[['Photo Coverage','I9:K13','core-series-links'],['Missing Pictures','B228:F230','resolved-series-requests']]
        expected=[{'sheet':'Master Catalogue','cell':'B4','value':186},{'sheet':'Missing Pictures','cell':'B4','value':1}]
    else:
        c,_=book.sheet('Wall Sculptures')
        for cell,value in c.items():
            if re.fullmatch(r'Q\d+',cell) and value[1] in POSITIONS:
                r=cell[1:];put('Wall Sculptures','AC'+r,c.get('AC'+r,('',''))[1]+' | Qualified series image '+FID+'. '+POSITIONS[value[1]]+' '+QUAL)
        c,_=book.sheet('Current image paths')
        for cell,value in c.items():
            if re.fullmatch(r'E\d+',cell) and value[1]==FID:
                r=cell[1:];put('Current image paths','K'+r,c.get('K'+r,('',''))[1]+' | '+' | '.join(options[pid]['name']+' — qualified series' for pid in POSITIONS))
        put('Wall Sculptures','A3','186 active options. Three Dune Ripple series roles now use an identifiable mixed-finish group display. The captured inventory dates, existing Primary choices and source/specification history remain preserved.')
        previews=[['Wall Sculptures','A3:D5','unified-series-summary']]
        expected=[{'sheet':'Overview','cell':'B7','value':186}]
    plans.append({'key':key,'source':manifest['sources'][key]['snapshot'],'source_sha256':manifest['sources'][key]['sha256'],'output':str(OUT/filename),'edits':edits,'expected':expected,'previews':previews,'new_sheet':None,'replace_image_sheet':False,'table_expansion':None})
    book.close()
write(H/'workbook-edit-plan.json',{'plans':plans})
dest=H/'gallery-projection';dest.mkdir(exist_ok=True);dbpath=dest/'complete-image-platform-register.sqlite'
assert not dbpath.exists()
copy=subprocess.run(['cp','-c',manifest['sources']['source_gallery']['snapshot'],str(dbpath)],capture_output=True)
if copy.returncode:shutil.copyfile(manifest['sources']['source_gallery']['snapshot'],dbpath)
db=sqlite3.connect(dbpath);db.execute('CREATE TABLE products_before_dune_series_20261027 AS SELECT * FROM products')
dump=lambda a:json.dumps(a,ensure_ascii=False,separators=(',',':'))
added=[]
for o in g['options']:
    if o['product_id'] not in POSITIONS:continue
    db.execute('UPDATE products SET record_json=? WHERE product_id=?',(dump(o),o['product_id']))
    aid=hashlib.sha256(('qualified_series|'+o['product_id']+'|'+FID+'|2026-10-27').encode()).hexdigest()[:24]
    edge={'association_id':aid,'product_id':o['product_id'],'file_id':FID,'intended_use':'selected_series_reference','association_status':'CURRENT_QUALIFIED_SERIES_REFERENCE','visual_role':'group_context','evidence':[{'path':str(H/'visual-series-evidence.json'),'sha256':sha(H/'visual-series-evidence.json'),'position':POSITIONS[o['product_id']]}],'image_url':selected['image_url'],'folder_url':selected['folder_url'],'folder_id':selected['folder_id'],'qualification':QUAL,'new_owner_response_inferred':False}
    db.execute('INSERT INTO associations VALUES(?,?,?,?,?,?)',(aid,o['product_id'],FID,edge['intended_use'],edge['association_status'],dump(edge)));added.append(aid)
current=json.loads(db.execute("SELECT value_json FROM metadata WHERE key='current_navigation_publication'").fetchone()[0]);current['register_sha256']=sha(H/'canonical-master-register.json');db.execute("UPDATE metadata SET value_json=? WHERE key='current_navigation_publication'",(dump(current),));db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
oldseal=read(Path(manifest['sources']['source_gallery']['snapshot']).parent/'sealed-handoff.json')
for html in Path(manifest['sources']['source_gallery']['snapshot']).parent.glob('*.html'):
    text=html.read_text()
    if html.name=='product-images.html':
        for pid in POSITIONS:
            marker='<article id="'+pid+'">';start=text.index(marker);end=text.index('</article>',start);part=text[start:end]
            part=part.replace('Series folder (image unavailable)','Historical series folder')
            part=part.replace('</h2>','</h2><p><a href="'+escape(selected['image_url'],quote=True)+'">Qualified series photograph</a> · <a href="'+escape(selected['folder_url'],quote=True)+'">Actual containing folder</a></p><p class="small">'+escape(POSITIONS[pid]+' '+QUAL)+'</p>',1)
            text=text[:start]+part+text[end:]
    (dest/html.name).write_text(text)
seal={'status':'THREE_QUALIFIED_SERIES_ROLES_MAPPED','database':str(dbpath),'database_sha256':sha(dbpath),'register_sha256':sha(H/'canonical-master-register.json'),'source_database':manifest['sources']['source_gallery'],'source_history_table_map':{'products':'products_before_dune_series_20261027'},'files':{p.name:sha(p) for p in dest.glob('*.html')},'added_association_ids':added,'source_platform_associations_preserved':True,'native_writes':0}
write(dest/'sealed-handoff.json',seal);write(H/'gallery-preparation.json',{'database_sha256':sha(dbpath),'seal_sha256':sha(dest/'sealed-handoff.json')})
write(H/'register-preparation.json',{'active_options':186,'new_context_losses':[],'new_series_losses':[],'effective_context_owner_holds':g['latest_verified_native_filename_import']['effective_context_owner_holds'],'current_series_references':sum(bool(o.get('current_series_reference')) for o in g['options'] if o['product_id'] in active),'current_primary_references':184,'current_context_references':159,'primary_changes':[],'source_assertions_preserved':1668})
print(json.dumps({'status':'THREE_SERIES_ROLES_PREPARED','option_ids':list(POSITIONS),'source_original_matches_current_native':True,'workbook_edits':{p['key']:len(p['edits']) for p in plans}}))
