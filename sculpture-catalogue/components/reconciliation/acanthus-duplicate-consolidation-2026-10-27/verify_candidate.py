"""Independently check the exact owner-scoped retirement candidate."""
from pathlib import Path
import argparse,hashlib,json,sqlite3
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=read(H/'input-manifest.json');old=read(m['sources']['register']['snapshot'])
p=argparse.ArgumentParser();p.add_argument('--register',required=True,type=Path);p.add_argument('--gallery',required=True,type=Path);a=p.parse_args()
new=read(a.register);oldopts={o['product_id']:o for o in old['options']};opts={o['product_id']:o for o in new['options']}
KEEP='BSI-93ADE7C4103D';DUP='BSI-E7CDC2CFAC9D'
assert set(new['active_option_ids'])==set(old['active_option_ids'])-{DUP}
assert set(new['retired_option_ids'])==set(old['retired_option_ids'])|{DUP}
assert len(new['active_option_ids'])==186 and set(opts)==set(oldopts)
assert opts[KEEP]['name']=='Acanthus Two Leaves White' and opts[KEEP]['file_id']=='id:cnqzTNngPVsAAAAAAAufMQ'
for pid in opts:
    for key in ['specifications','master_fields','selling_details','offered_fixing_choices']:
        assert opts[pid].get(key)==oldopts[pid].get(key),(pid,key,'physical/commercial source changed')
assert new['original_review_specification_assertions']==old['original_review_specification_assertions']
assert opts[KEEP]['context_file_id']==oldopts[KEEP]['context_file_id']
src=sqlite3.connect(Path(m['sources']['source_gallery']['snapshot']).as_uri()+'?mode=ro',uri=True);db=sqlite3.connect(a.gallery.resolve().as_uri()+'?mode=ro',uri=True)
assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
products={pid:json.loads(raw) for pid,raw in db.execute('select product_id,record_json from products')}
assert products[KEEP]['name']==opts[KEEP]['name'] and products[KEEP]['file_id']==opts[KEEP]['file_id']
assert products[KEEP]['master_fields']==oldopts[KEEP]['master_fields']
oldrows=src.execute('select * from associations').fetchall();newrows=db.execute('select * from associations').fetchall();assert set(oldrows)<=set(newrows)
columns=[r[1] for r in db.execute('pragma table_info(associations)')];added=[dict(zip(columns,r)) for r in set(newrows)-set(oldrows)]
native=read(H/'owner-evidence/verification.json');assert native['status']=='PASS' and native['all_ids_preserved'] and native['all_file_hashes_and_sizes_unchanged']
admitted={fid for fid,row in native['after'].items() if row.get('kind')=='file' and 'Acanthus Two Leaves' in row['path']}|{'id:cnqzTNngPVsAAAAAAAyj8Q'}
old_by_id={row[0]:dict(zip(columns,row)) for row in oldrows}
for edge in added:
    assert edge.get('product_id')==KEEP and edge.get('file_id') in admitted,edge
    raw=json.loads(edge['record_json']);source=old_by_id[raw['duplicate_consolidation']['original_association_id']]
    assert source['product_id']==DUP and source['file_id']==edge['file_id']
    assert source['status']==edge['status'] and source['intended_use']==edge['intended_use'],'A candidate must not become an approval'
    assert edge['intended_use']!='selected_primary_reference','Keeper Primary must not be replaced'
assert db.execute('select count(*) from associations where product_id=? and file_id=?',(KEEP,'id:cnqzTNngPVsAAAAAAAyluQ')).fetchone()[0]>0
assert not any(edge.get('product_id')==KEEP and edge.get('file_id')=='id:cnqzTNngPVsAAAAAAAyluA' for edge in added)
src.close();db.close()
result={'status':'PASS_EXACT_OWNER_DUPLICATE_CONSOLIDATION','active_options':186,'retained_options':len(opts),'original_specification_assertions_preserved':len(new['original_review_specification_assertions']),'all_original_physical_and_commercial_fields_unchanged':True,'keeper_primary_unchanged':True,'keeper_existing_context_choice_unchanged':True,'old_source_associations_preserved':True,'new_associations_limited_to_exact_owner_confirmed_photos':True,'added_exact_associations':added,'register_sha256':sha(a.register),'gallery_sha256':sha(a.gallery),'native_app_or_shared_writes':0}
(H/'independent-candidate-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='added_exact_associations'},indent=2))
