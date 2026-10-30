"""Prepare an isolated depth-only gallery candidate for Main to publish.

No current pointer, native file, source-photo evidence or association is edited.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser
import hashlib
import html
import json
import shutil
import sqlite3
import urllib.parse

H=Path(__file__).resolve().parent
B=H.parents[2]
G=H.parent/'all-record-image-matching-20261024-B'
source=G/'published-projections/20261025T002820725728Z'
M=B/'components/reconciliation/depth-estimates-master-2026-10-25'
rp=M/'canonical-master-register.json'
wp=M/'master-workbook.pending'
REG_SHA='8b2c785d043198f1be24813fa4f38ea36bd2e0880e118b9de229f48c5ded66e2'
BOOK_SHA='992751b7677568877a993c50292e0fb2dbd6cd030f6c6bf4ea28715bb1563783'
SOURCE_SEAL_SHA='26a1675be114c874c6512a9b3089b27498f4aa5c9fc73df2991b7f56f824ce35'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
e=lambda v:html.escape(str(v),quote=True)
assert sha(rp)==REG_SHA and sha(wp)==BOOK_SHA
assert sha(source/'sealed-handoff.json')==SOURCE_SEAL_SHA
baseline_pointer_sha=sha(B/'current-master.json')
shared_integration_sha=sha(G/'current-integration.json')
source_seal=read(source/'sealed-handoff.json')
for rel,digest in source_seal['files'].items():
    assert sha(source/rel)==digest,rel
register=read(rp)
products={p['product_id']:p for p in register['options'] if p['product_id'] in register['active_option_ids']}
packet=read(H/'depth-estimate-packet.json')
targets={row['product_id']:row for row in packet['rows']}
assert len(products)==188 and len(targets)==14
old_db=sqlite3.connect('file:'+str(source/'complete-image-platform-register.sqlite')+'?mode=ro',uri=True)
old_products={pid:json.loads(blob) for pid,blob in old_db.execute('SELECT product_id,record_json FROM products')}
assert set(old_products)==set(products)
changes=[]
for pid,p in products.items():
    old=old_products[pid]
    changed_keys={k for k in set(p)|set(old) if p.get(k)!=old.get(k)}
    if changed_keys:
        assert pid in targets,(pid,changed_keys)
        assert changed_keys=={'master_fields'},(pid,changed_keys)
        changes.append(pid)
    for field,value in p['master_fields'].items():
        if pid in targets and field=='Dimensions / depth':
            assert value==targets[pid]['after'],pid
        else:
            assert value==old['master_fields'][field],(pid,field)
assert set(changes)==set(targets)

out=G/'published-projections'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True,exist_ok=False)
proofs=['source-gallery-review.json','source-photo-correspondences.json','local-shopify-gallery-review.json','local-shopify-gallery-import-readback.json','current-file-visual-roles.json']
unchanged_json=proofs+['owner-identity-projection.json','per-product-image-lists.json','product-family-navigation.json','product-image-association-review.json','current-images-without-option-scope.json','source-gallery-reader-index.json','family-image-reader-index.json','product-reader-index.json']
for name in unchanged_json:
    shutil.copyfile(source/name,out/name)
    assert sha(source/name)==sha(out/name)
for folder in ['products','families','source-galleries','source-association-review']:
    shutil.copytree(source/folder,out/folder)
for name in ['index.html','product-images.html','source-galleries.html','family-images.html']:
    shutil.copyfile(source/name,out/name)

def rebase(value):
    if isinstance(value,str):return value.replace(str(source),str(out))
    if isinstance(value,list):return [rebase(x) for x in value]
    if isinstance(value,dict):return {k:rebase(v) for k,v in value.items()}
    return value

for p in out.rglob('*.html'):
    content=p.read_text()
    p.write_text(content.replace(str(source),str(out)))
gapfile=out/'source-association-review/all-65-case-dispositions.json'
gap_entries=rebase(read(gapfile));write(gapfile,gap_entries)
assert len(gap_entries)==65
assert Counter(x['disposition'] for x in gap_entries)==Counter(x['disposition'] for x in read(source/'source-association-review/all-65-case-dispositions.json'))

db=sqlite3.connect(out/'complete-image-platform-register.sqlite')
old_db.backup(db)
for pid,p in products.items():
    db.execute('UPDATE products SET name=?,family=?,record_json=? WHERE product_id=?',(p['name'],p.get('family'),json.dumps(p,ensure_ascii=False),pid))
summary=read(source/'summary.json')
summary.update({'status':'PREPARED_DEPTH_ONLY_GALLERY_PROJECTION_FOR_MAIN_PUBLICATION','recorded_utc':datetime.now(timezone.utc).isoformat(),'target_register_sha256':REG_SHA,'target_workbook_sha256':BOOK_SHA,'working_depths_present':188,'new_owner_authorized_estimated_depths':14,'new_physical_measurements':0,'new_image_associations':0,'this_increment_selected_reference_changes':0})
summary['next_work']=['Publish this projection with the exact candidate register and workbook hashes.','Preserve existing source-photo qualifications and deferred photography.']
write(out/'summary.json',summary)
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('integration_summary',json.dumps(summary,ensure_ascii=False)))
db.commit()
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
table_counts={}
for (table,) in old_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    quoted='"'+table.replace('"','""')+'"'
    previous=list(old_db.execute('SELECT * FROM '+quoted))
    current=list(db.execute('SELECT * FROM '+quoted))
    table_counts[table]=len(current)
    if table not in {'products','metadata'}:
        assert sorted(previous,key=repr)==sorted(current,key=repr),table
    elif table=='metadata':
        assert sorted((x for x in previous if x[0]!='integration_summary'),key=repr)==sorted((x for x in current if x[0]!='integration_summary'),key=repr)
assert table_counts['source_product_links']==260
assert {pid:json.loads(blob) for pid,blob in db.execute('SELECT product_id,record_json FROM products')}==products
db.close();old_db.close()

report=M/'depth-estimates.html'
main_index=M/'index.html'
for pid,p in products.items():
    page=out/'products'/(pid+'.html')
    content=page.read_text()
    target_link='<p><a href="'+e(str(main_index)+'#'+pid)+'">Current specifications for this option</a></p>'
    if pid in targets:
        estimate=targets[pid]['estimate']
        target_link+='<p class="notice"><strong>Estimated depth: '+e(estimate['nominal_cm'])+' cm; working range '+e(estimate['range_cm'][0])+'–'+e(estimate['range_cm'][1])+' cm.</strong> Includes backing and relief; excludes mounting stand-off. Not physically measured.</p><p>'+e(targets[pid]['after']['display'])+'</p>'
    anchor='</h1>'
    assert content.count(anchor)==1,pid
    content=content.replace(anchor,anchor+target_link,1)
    page.write_text(content)
intro='<p>All 188 active options have a working depth. Fourteen missing depths were estimated under the owner instruction; estimates are labelled and do not represent physical measurements. <a href="'+e(str(report))+'">Review the 14 estimated depths</a>.</p>'
index=out/'index.html';content=index.read_text();index.write_text(content.replace('</h1>','</h1>'+intro,1))
validation=rebase(read(source/'product-reader-validation.json'))
validation.update({'all188_products_equal_candidate_register':True,'working_depths_present':188,'depth_estimates_added':14,'physical_measurements_added':0})
write(out/'product-reader-validation.json',validation)
remaining=read(source/'remaining-work.json')
remaining['recorded_utc']=datetime.now(timezone.utc).isoformat()
remaining['canonical_release']={'owner_thread':'01a144ab-1a7c-7223-a403-73a4d53d70ff','status':'EXACT_DEPTH_CANDIDATE_PREPARED_FOR_MAIN_PUBLICATION','candidate_register_path':str(rp),'candidate_register_sha256':REG_SHA,'candidate_workbook_path':str(wp),'candidate_workbook_sha256':BOOK_SHA}
remaining['depth_update']={'new_estimates':14,'working_depth_coverage':'188/188','physical_measurements_added':0,'face_dimensions_still_unknown':['BSI-65A93033A200','BSI-4515726BBC18','BSI-3C849B547D50']}
write(out/'remaining-work.json',remaining)
write(out/'publication-rebase.json',{'status':'PREPARED_DEPTH_ONLY_PROJECTION','candidate_register_path':str(rp),'candidate_register_sha256':REG_SHA,'candidate_workbook_path':str(wp),'candidate_workbook_sha256':BOOK_SHA,'previous_published_reader':str(source),'previous_published_reader_sha256':SOURCE_SEAL_SHA,'this_increment_option_changes':[{'product_id':pid,'changed_fields':['master_fields.Dimensions / depth']} for pid in changes],'unchanged_source_proof_files':{name:sha(out/name) for name in proofs},'this_increment_selected_reference_changes':0,'new_shared_design_references':0,'new_exact_variant_assignments':0,'native_or_canonical_or_platform_writes_by_this_projection':0})
write(out/'candidate-release-binding.json',{'status':'PREPARED_FOR_MAIN_PUBLICATION','register':str(rp),'register_sha256':REG_SHA,'workbook':str(wp),'workbook_sha256':BOOK_SHA,'baseline_pointer_sha256':baseline_pointer_sha,'owner_instruction_turn_id':'01a17087-440c-7aa1-b7e5-449f426ca932','depth_packet':str(H/'depth-estimate-packet.json'),'depth_packet_sha256':sha(H/'depth-estimate-packet.json')})
write(out/'input-manifest.json',{str(source/'sealed-handoff.json'):SOURCE_SEAL_SHA,str(rp):REG_SHA,str(wp):BOOK_SHA,str(H/'depth-estimate-packet.json'):sha(H/'depth-estimate-packet.json')})

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in {'href','src'} and v:self.links.append(v)

local_links=0;pending=[]
for page in sorted(out.rglob('*.html')):
    parser=Links();parser.feed(page.read_text())
    for url in parser.links:
        part=urllib.parse.urlsplit(url)
        if part.scheme or part.netloc or not part.path:continue
        target=Path(urllib.parse.unquote(part.path))
        if not target.is_absolute():target=page.parent/target
        local_links+=1
        if not target.exists():
            if target in {main_index,report}:pending.append(str(target))
            else:raise AssertionError((str(page),url,str(target)))
for name in unchanged_json:
    assert sha(source/name)==sha(out/name),name
assert sha(G/'current-integration.json')==shared_integration_sha
assert sha(B/'current-master.json')==baseline_pointer_sha
assert sha(rp)==REG_SHA and sha(wp)==BOOK_SHA
qa={'status':'PASS_ISOLATED_DEPTH_PROJECTION','checked_utc':datetime.now(timezone.utc).isoformat(),'candidate_register_sha256':REG_SHA,'candidate_workbook_sha256':BOOK_SHA,'product_records_equal_candidate':188,'exact_depth_changes':14,'other_retained_field_objects_unchanged':1120,'table_counts':table_counts,'all_nonproduct_association_tables_unchanged':True,'source_proof_files_byte_identical':{name:sha(out/name) for name in proofs},'all_existing_per_product_image_lists_unchanged':True,'all65_case_dispositions_preserved':True,'local_links_checked':local_links,'main_report_links_pending_publication':sorted(set(pending)),'native_or_canonical_or_platform_writes':0,'shared_integration_pointer_unchanged':True,'canonical_pointer_unchanged':True}
write(out/'depth-projection-readback.json',qa)
shutil.copyfile(Path(__file__),out/'project_depth_gallery.py')
seal={'status':'VERIFIED_DEPTH_ONLY_GALLERY_CANDIDATE_FOR_MAIN_PUBLICATION','sealed_utc':datetime.now(timezone.utc).isoformat(),'reviewer_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','canonical_publisher_thread':'01a144ab-1a7c-7223-a403-73a4d53d70ff','target_register_sha256':REG_SHA,'target_workbook_sha256':BOOK_SHA,'run':str(out),'readers':{name:str(out/name) for name in ['index.html','product-images.html','source-galleries.html','family-images.html','source-association-review/index.html']},'counts':validation,'all188_products_equal_candidate_register':True,'owner_questions_remaining':0,'source_proof_files_byte_identical_to_frozen_review':qa['source_proof_files_byte_identical'],'source_product_link_rows_unchanged':260,'deferred_installation_gaps':22,'deferred_series_gaps':1,'new_physical_measurements':0,'selected_primary_references_changed':0,'new_exact_variant_assignments':0,'native_or_canonical_or_platform_writes_by_reviewer':0,'files':{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
sealpath=out/'sealed-handoff.json';write(sealpath,seal)
write(H/'depth-gallery-location.json',{'run':str(out),'seal':str(sealpath),'sha256':sha(sealpath),'register_sha256':REG_SHA,'workbook_sha256':BOOK_SHA})
print(json.dumps({'run':str(out),'seal':str(sealpath),'sha256':sha(sealpath),'qa':qa},ensure_ascii=False,indent=2))
