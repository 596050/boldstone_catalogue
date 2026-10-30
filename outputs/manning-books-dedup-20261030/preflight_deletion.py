from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, sys

PROJECT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).resolve().parent
FROZEN_SHA='89da063cb5402204dfc8ac55ad4dced916e2eb3392559133ff183a6b3054846c'
body=(OUT/'deletion-review.json').read_bytes()
assert hashlib.sha256(body).hexdigest()==FROZEN_SHA, 'Approved manifest changed'
plan=json.loads(body)
assert len(plan['keepers'])==179 and len(plan['removals'])==4403
assert sum(r['size'] for r in plan['removals'])==69700643226
assert not plan['folders']
sys.path.insert(0,str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.common import PathRoot
from dropbox.files import FileMetadata

def info(m):
    r={'id':m.id,'name':m.name,'object_type':'file' if isinstance(m,FileMetadata) else 'folder','path_display':m.path_display,'path_lower':m.path_lower}
    for k in ('rev','size','content_hash'):
        if hasattr(m,k):r[k]=getattr(m,k)
    return r

with connection(PROJECT) as (client, verified_catalogue_root):
    scoped=client.with_path_root(PathRoot.namespace_id('10782830832'))
    root=scoped.files_get_metadata('id:cnqzTNngPVsAAAAAAAgI_w')
    assert root.name=='Manning Books' and root.id=='id:cnqzTNngPVsAAAAAAAgI_w'
    page=scoped.files_list_folder('',recursive=True,limit=2000,include_deleted=False)
    entries=list(page.entries)
    while page.has_more:
        page=scoped.files_list_folder_continue(page.cursor)
        entries.extend(page.entries)
    current={r.id:info(r) for r in entries if hasattr(r,'id')}
    discrepancies=[]
    for r in plan['keepers']+plan['removals']:
        m=current.get(r['id'])
        if not m:
            discrepancies.append({'id':r['id'],'action':r['action'],'path':r['display_path'],'error':'missing'})
            continue
        wrong=[k for k in ('rev','size','content_hash','path_lower') if m.get(k)!=r[k]]
        if m['object_type']!='file':wrong.append('object_type')
        if wrong:discrepancies.append({'id':r['id'],'action':r['action'],'path':r['display_path'],'changed_fields':wrong,'current':m})
    original_ids={r['id'] for r in plan['keepers']+plan['removals']}
    extras=[m for fid,m in current.items() if m['object_type']=='file' and fid not in original_ids]
    receipt={'status':'PASS' if not discrepancies else 'CHANGED_FILES_REQUIRE_RECONCILIATION','checked_utc':datetime.now(timezone.utc).isoformat(),'approved_manifest_sha256':FROZEN_SHA,'approval_text':'do it: - Remove 4,403 files, totalling 69.7 GB','approved_removals':4403,'approved_remove_bytes':69700643226,'keepers':179,'current_files':sum(m['object_type']=='file' for m in current.values()),'discrepancies':discrepancies,'new_files_preserved':extras,'dropbox_mutations_performed':0,'root':info(root)}
    (OUT/'deletion-preflight.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
    if discrepancies:raise SystemExit(2)
