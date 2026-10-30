"""Project a published canonical navigation update onto the frozen image review.

Only the Main publisher's exact current pointer is accepted. The original review
packet and all source-photo proof remain unchanged.
"""
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import argparse,hashlib,json,shutil,sqlite3

H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=argparse.ArgumentParser();a.add_argument('--published-pointer-sha256',required=True);args=a.parse_args()
pointer_path=B/'current-master.json'
assert sha(pointer_path)==args.published_pointer_sha256
pointer=read(pointer_path);regpath=B/pointer['register'];assert sha(regpath)==pointer['register_sha256']
register=read(regpath);active=set(register['active_option_ids'])
products={r['product_id']:r for r in register['options'] if r['product_id'] in active}
source=H/'integrations/20261024T225748917419Z'
source_seal=source/'sealed-handoff.json'
assert sha(source_seal)=='a93db7e5584a4cc356adf03e633ee50efdff92bce82206f65dfb75b9a2347450'
assert len(products)==188 and args.published_pointer_sha256!=read(source/'summary.json')['baseline_pointer_sha256']
original=sqlite3.connect('file:'+str(source/'complete-image-platform-register.sqlite')+'?mode=ro',uri=True)
old={pid:json.loads(blob) for pid,blob in original.execute('SELECT product_id,record_json FROM products')}
assert set(products)==set(old)
allowed={'BSI-C02D6DF365D3':{'context_image_url','context_folder_url'},'BSI-EBD43DF0704F':{'current_context_navigation'},'BSI-D5A939264C82':{'file_id','image_url','current_link_basis','current_primary_navigation','context_image_url','context_folder_url'},'BSI-65520F070145':{'file_id','image_url','current_link_basis','current_primary_navigation'}}
changes=[]
for pid,p in products.items():
    keys={k for k in set(p)|set(old[pid]) if p.get(k)!=old[pid].get(k)}
    assert keys<=allowed.get(pid,set()),(pid,keys)
    if keys:changes.append({'product_id':pid,'changed_fields':sorted(keys)})
replacements={pid:(old[pid]['file_id'],p['file_id']) for pid,p in products.items() if p.get('file_id')!=old[pid].get('file_id')}
assert replacements=={'BSI-D5A939264C82':('id:cnqzTNngPVsAAAAAAAs9QA','id:cnqzTNngPVsAAAAAAAr1HA'),'BSI-65520F070145':('id:cnqzTNngPVsAAAAAAAr1IQ','id:cnqzTNngPVsAAAAAAAs9Pw')}
out=H/'published-projections'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');out.mkdir(parents=True,exist_ok=False)
db=sqlite3.connect(out/'complete-image-platform-register.sqlite');original.backup(db);original.close()
images={fid:json.loads(blob) for fid,blob in db.execute('SELECT file_id,record_json FROM images')}
for pid,p in products.items():db.execute('UPDATE products SET record_json=? WHERE product_id=?',(json.dumps(p,ensure_ascii=False),pid))
for pid,(oldfid,newfid) in replacements.items():
    p=products[pid];im=images[newfid]
    assert im['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'
    for key in ['folder_id','image_url','folder_url']:assert p[key]==im[key]
    row=db.execute('SELECT association_id,record_json FROM associations WHERE product_id=? AND file_id=? AND status=?',(pid,oldfid,'CURRENT_ACCEPTED_REFERENCE')).fetchone();assert row
    aid,blob=row;historical=json.loads(blob);historical['association_status']='HISTORICAL_REPLACED_PRIMARY_REFERENCE'
    historical['replacement_reference']={'file_id':newfid,'published_register':str(regpath),'published_register_sha256':pointer['register_sha256']}
    db.execute('UPDATE associations SET status=?,record_json=? WHERE association_id=?',(historical['association_status'],json.dumps(historical,ensure_ascii=False),aid))
    nid=hashlib.sha256(json.dumps([pid,newfid,'published_selected_primary',pointer['register_sha256']]).encode()).hexdigest()[:24]
    selected={**historical,'association_id':nid,'file_id':newfid,'intended_use':'selected_primary_reference','association_status':'CURRENT_ACCEPTED_REFERENCE','image_url':im['image_url'],'folder_url':im['folder_url'],'folder_id':im['folder_id'],'current_image_in_map':True,'current_native_status':im['inventory_status'],'visual_role':im['visual_role'],'visual_role_status':im['visual_review_status'],'evidence':[{'path':str(regpath),'sha256':pointer['register_sha256'],'product_id':pid,'details':{'current_primary_navigation':p['current_primary_navigation'],'note':'Selected equivalent photograph is projected from the published canonical register. Historical selection and identity holds remain retained.'}}]}
    selected.pop('replacement_reference',None)
    db.execute('INSERT INTO associations VALUES(?,?,?,?,?,?)',(nid,pid,newfid,selected['intended_use'],selected['association_status'],json.dumps(selected,ensure_ascii=False)))
per_product=defaultdict(dict)
for blob, in db.execute('SELECT record_json FROM associations'):
    row=json.loads(blob);fid=row['file_id'];im=images.get(fid,{})
    grouped=per_product[row['product_id']].setdefault(fid,{'file_id':fid,'name':im.get('name'),'visual_role':im.get('visual_role'),'visual_review_status':im.get('visual_review_status'),'image_url':im.get('image_url'),'folder_url':im.get('folder_url'),'native_status':im.get('inventory_status','NOT_IN_CURRENT_MAP'),'association_statuses':[],'evidence':[]})
    if row['association_status'] not in grouped['association_statuses']:grouped['association_statuses'].append(row['association_status'])
    grouped['evidence'].append({'association_id':row['association_id'],'intended_use':row['intended_use'],'source_evidence':row['evidence']})
unchanged_files=['source-gallery-review.json','source-photo-correspondences.json','local-shopify-gallery-review.json','local-shopify-gallery-import-readback.json','current-file-visual-roles.json']
for name in unchanged_files:shutil.copyfile(source/name,out/name);assert sha(source/name)==sha(out/name)
write(out/'per-product-image-lists.json',{pid:list(rows.values()) for pid,rows in per_product.items()})
write(out/'published-pointer-snapshot.json',pointer)
summary=read(source/'summary.json');summary.update({'status':'PUBLISHED_NAVIGATION_PROJECTED_FULL_REVIEW_UNCERTAINTIES_RETAINED','baseline_pointer_sha256':args.published_pointer_sha256,'frozen_review_baseline_pointer_sha256':read(source/'summary.json')['baseline_pointer_sha256'],'main_publication_observed':True,'recorded_utc':datetime.now(timezone.utc).isoformat(),'next_work':['Incorporate pending exact owner identity decisions through the existing review owner.','Retain unresolved exact-photo comparisons and deferred photography until supporting evidence or owner instructions arrive.']})
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('integration_summary',json.dumps(summary,ensure_ascii=False)));db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
write(out/'summary.json',summary)
manifest=read(source/'input-manifest.json');manifest.update({str(regpath):pointer['register_sha256'],str(out/'published-pointer-snapshot.json'):sha(out/'published-pointer-snapshot.json'),str(source_seal):sha(source_seal)});write(out/'input-manifest.json',manifest)
receipt={'status':'PUBLISHED_CANONICAL_NAVIGATION_PROJECTED_ONLY','published_pointer_sha256':args.published_pointer_sha256,'published_register_path':str(regpath),'published_register_sha256':pointer['register_sha256'],'frozen_review_handoff':str(source_seal),'frozen_review_handoff_sha256':sha(source_seal),'allowed_option_changes':changes,'selected_reference_replacements':replacements,'unchanged_source_proof_files':{name:sha(out/name) for name in unchanged_files},'all_other_product_fields_preserved':True,'historical_primary_references_preserved':True,'new_identity_or_finish_assignments':0,'native_or_canonical_or_platform_writes_by_this_projection':0}
write(out/'publication-rebase.json',receipt)
remaining=read(source/'remaining-work.json')
remaining['recorded_utc']=datetime.now(timezone.utc).isoformat()
remaining['canonical_release']={'owner_thread':'01a144ab-1a7c-7223-a403-73a4d53d70ff','status':'MAIN_PUBLICATION_APPLIED_AND_PROJECTED','published_register_path':str(regpath),'published_register_sha256':pointer['register_sha256'],'selected_equivalent_Wall_Circle_references_projected':2,'historical_reference_rows_preserved':True}
write(out/'remaining-work.json',remaining)
(out/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Published catalogue image register</title><style>body{font:17px system-ui;max-width:900px;margin:50px auto;padding:0 20px;line-height:1.6}a{color:#1c6354}</style><h1>Catalogue image register</h1><p>The current catalogue links and two replacement Wall Circle references are included. All 6,360 current wall-sculpture images and the complete local platform galleries have been reviewed.</p><ul><li><a href="product-images.html">188 product image lists</a></li><li><a href="source-galleries.html">81 complete source galleries, including local Shopify records</a></li><li><a href="family-images.html">60 current family image libraries</a></li></ul><p>Every image list retains its image roles, Dropbox image and folder links, and any uncertainty. Group photographs remain context.</p><p>Still open: the legacy Frozen Fish identity and three Wall Circle pattern decisions. Exact Dropbox photograph matches remain uncertain for 29 Squarespace and three Shopify gallery images. The 22 installation gaps and one series gap remain deferred.</p><p><a href="remaining-work.json">Detailed remaining work</a> · <a href="publication-rebase.json">Catalogue update record</a> · <a href="summary.json">Matching counts</a></p>')
write(H/'current-integration.json',{'run':str(out),'summary':str(out/'summary.json'),'reader':str(out/'index.html'),'database':str(out/'complete-image-platform-register.sqlite')})
assert sha(pointer_path)==args.published_pointer_sha256
print(json.dumps({'projection':str(out),'receipt':receipt},indent=2))
