"""Import exactly the owning session's eighteen saved Name edits."""
from common import *
from copy import deepcopy
import re,sqlite3,shutil

source=BASE.parent/'catalogue-review/reviews/white-title-and-job-audit-20261027/title-audit-result.json'
audit=read(source)
assert audit['status']=='PASS' and len(audit['corrected'])==18 and audit['native_file_writes']==0
assert audit['non_name_fields_and_reviews_unchanged']
shutil.copyfile(source,H/'white-title-audit-input.json')
changes={r['id']:r for r in audit['corrected']}
before=deepcopy(g)
for o in g['options']:
    if o['product_id'] not in changes:continue
    assert o['product_id'] in active
    r=changes[o['product_id']]
    old=o['name'];o['name']=r['name']
    o['retained_names']=list(dict.fromkeys(o.get('retained_names',[])+[old,r['old_name'],r['name']]))
    o['current_name_review_import']={'source':str(source),'source_sha256':sha(source),'source_checked_at':audit['checked_at'],'old_canonical_name':old,'saved_app_name':r['name'],'scope':'Name only. No finish-material, specification, photo-choice, platform or stock change.'}
for a,b in zip(before['options'],g['options']):
    for k in set(a)|set(b):
        if k not in {'name','retained_names','current_name_review_import'}:assert a.get(k)==b.get(k),(a['product_id'],k)
g['latest_white_title_review_import']={'source':str(source),'source_sha256':sha(source),'corrected':audit['corrected'],'held':audit['held'],'old_names_preserved_as_aliases':True,'non_name_fields_changed':0}
write(H/'canonical-master-register.json',g)
for r in overlay:
    for ref in r['selected_references']:
        if ref['product_id'] in changes:ref['name']=changes[ref['product_id']]['name']
write(H/'current-image-overlay.json',overlay)
plans=read(H/'workbook-edit-plan.json')
for p in plans['plans']:
    book=Book(p['source']);edits={(x['sheet'],x['cell']):x for x in p['edits']}
    sheets=([('Master Catalogue','A','B'),('Specifications','A','B'),('Photo Coverage','A','B'),('Missing Pictures','B','C'),('Listing Reconciliation','A','B'),('Listing Issues','A','B'),('Listing Resolution','A','B'),('Draft Listings','A','B'),('Selling Details','A','B')] if p['key']=='core_workbook' else [('Wall Sculptures','Q','A'),('Products','A','B'),('Specifications','B','C')])
    for sn,idcol,namecol in sheets:
        c,_=book.sheet(sn)
        for cell,value in c.items():
            if not re.fullmatch(idcol+r'\d+',cell):continue
            pid=value[1].removeprefix('INDIVIDUAL:')
            if pid not in changes:continue
            dest=namecol+re.search(r'\d+',cell)[0]
            edits[(sn,dest)]={'sheet':sn,'cell':dest,'before':c.get(dest),'kind':'value','value':changes[pid]['name']}
    p['edits']=list(edits.values());book.close()
write(H/'workbook-edit-plan.json',plans)
dbpath=H/'gallery-projection/complete-image-platform-register.sqlite';db=sqlite3.connect(dbpath)
for o in g['options']:
    if o['product_id'] in changes:db.execute('UPDATE products SET name=?,record_json=? WHERE product_id=?',(o['name'],json.dumps(o,ensure_ascii=False,separators=(',',':')),o['product_id']))
raw=json.loads(db.execute("SELECT value_json FROM metadata WHERE key='current_navigation_publication'").fetchone()[0]);raw['register_sha256']=sha(H/'canonical-master-register.json');db.execute("UPDATE metadata SET value_json=? WHERE key='current_navigation_publication'",(json.dumps(raw),));db.commit();db.close()
seal=read(H/'gallery-projection/sealed-handoff.json');seal['register_sha256']=sha(H/'canonical-master-register.json');seal['database_sha256']=sha(dbpath);write(H/'gallery-projection/sealed-handoff.json',seal)
write(H/'title-import-receipt.json',{'status':'EXACT18_SAVED_NAMES_IMPORTED','source_sha256':sha(source),'option_ids':list(changes),'register_sha256':sha(H/'canonical-master-register.json'),'old_names_kept':True,'physical_commercial_and_photo_choice_changes':0})
print('Imported exactly 18 saved titles; original aliases and every non-name option field preserved')
