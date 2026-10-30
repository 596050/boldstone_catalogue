"""Independently check the proposed catalogue and effective app projection."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,sqlite3,sys
from unittest.mock import patch
H=Path(__file__).resolve().parent;PROJECT=H.parents[2];APP=PROJECT/'catalogue-review'
sys.path.insert(0,str(APP))
from catalogue import Catalogue
from dropbox_sync import apply_inventory
from filename_overlay import apply_filename_overlay
from projection import Projection
from store import ReviewStore
from component_links import payload
OUT=PROJECT/'sculpture-catalogue/components/reconciliation/frozen-fish-three-finishes-2026-10-29'
RUNTIME=Path('/Users/tprice/Library/Application Support/BoldstoneReview')
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=read(OUT/'inputs/canonical-master-register.json');new=read(OUT/'canonical-master-register.json')
decision=read(OUT/'owner-decision.json');names=decision['active_names'];retired=set(decision['retired_option_ids']);white=decision['replacement_option_id']
a={o['product_id']:o for o in old['options']};b={o['product_id']:o for o in new['options']}
assert len(new['active_option_ids'])==184 and len(b)==191 and len(new['retired_option_ids'])==7
assert set(old['active_option_ids'])-set(new['active_option_ids'])==retired
assert {p:o['name'] for p,o in b.items() if p in new['active_option_ids'] and o['family']=='Frozen Fish'}==names
for p in a:
 for key in ('specifications','master_fields','selling_details'):assert a[p].get(key)==b[p].get(key),(p,key)
 if p not in names and p not in retired:assert a[p]==b[p],p
for p in retired:assert a[p]['name'] in b[white]['retained_names']
old_db=OUT/'inputs/complete-image-platform-register.sqlite';new_db=OUT/'gallery-projection/complete-image-platform-register.sqlite'
with closing(sqlite3.connect(old_db)) as src,closing(sqlite3.connect(new_db)) as dst:
 assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 tables=[r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")]
 for t in tables:
  before=set(src.execute('SELECT * FROM "'+t+'"'));after=set(dst.execute('SELECT * FROM "'+t+'"'))
  if t in ('associations','source_product_links'):assert before<=after,t
  elif t not in ('products','metadata'):assert before==after,t
 assert len(dst.execute('SELECT * FROM associations').fetchall())-len(src.execute('SELECT * FROM associations').fetchall())==33
# Read review rows without opening a writer or changing runtime permissions.
with closing(sqlite3.connect('file:'+str(RUNTIME/'reviews.sqlite3')+'?mode=ro',uri=True)) as db:
 db.row_factory=sqlite3.Row
 reviews=[ReviewStore.unpack(r) for r in db.execute('SELECT * FROM reviews ORDER BY updated_at')]
inventory=read(RUNTIME/'dropbox-sync/inventory.json')
previous=apply_inventory(Catalogue(PROJECT,RUNTIME),inventory,RUNTIME)
# Keep the real cache trust root while substituting only the candidate pointer.
read_text=Path.read_text
def candidate_read(path,*args,**kwargs):
 if path.resolve()==PROJECT/'sculpture-catalogue/current-master.json':return read_text(OUT/'next-current-master.json')
 return read_text(path,*args,**kwargs)
with patch.object(Path,'read_text',candidate_read):
 staged=apply_inventory(Catalogue(PROJECT,RUNTIME),inventory,RUNTIME)
apply_filename_overlay(previous,RUNTIME);apply_filename_overlay(staged,RUNTIME)
assert len(staged.products)==184
assert set(previous.assets)==set(staged.assets)
for aid in previous.assets:
 x,y=previous.assets[aid],staged.assets[aid]
 assert {k:v for k,v in x.items() if k!='product_ids'}=={k:v for k,v in y.items() if k!='product_ids'},aid
 expected={white if p in retired else p for p in x.get('product_ids',[])}
 assert set(y.get('product_ids',[]))==expected,(aid,expected,y.get('product_ids'))
old_view=Projection(previous,reviews);future_reviews=deepcopy(reviews)
for r in future_reviews:
 if r['kind']=='field' and r['item_id']=='Name' and r['product_id'] in names:r['data']['value']=names[r['product_id']]
view=Projection(staged,future_reviews)
for pid in set(staged.products)-set(names):
 assert staged.products[pid]==previous.products[pid],pid
 assert view.edges[pid]==old_view.edges[pid],pid
for pid in names:
 assert [f for f in staged.products[pid]['fields'] if f['key']!='Name']==[f for f in previous.products[pid]['fields'] if f['key']!='Name'],pid
white_old=set().union(*(set(old_view.edges[pid]) for pid in retired|{white}))
assert white_old<=set(view.edges[white]), sorted(white_old-set(view.edges[white]))
root='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Frozen Fish/'
current={aid:r for aid,r in inventory['records'].items() if r['kind']=='file' and r['path'].startswith(root)}
assert len(current)==43,len(current)
checks={}
for pid,name in names.items():
 finish=name.rsplit(' - ',1)[1]
 intended={aid for aid,r in current.items() if r['path'].split('/')[-2] in ('Frozen Fish '+finish,'Frozen Fish '+finish+' In Situ')}
 shown=set()
 for aid in intended:
  chosen={r['product_id'] for r in payload(view,view.cid(aid),include_primary=True)['rows'] if r['shown']}
  assert pid in chosen,(name,aid,chosen)
  assert not (retired&chosen)
  assert not ((set(names)-{pid})&chosen),(name,aid,chosen)
  shown.add(aid)
 checks[pid]={'name':name,'current_dropbox_images':len(shown),'all_retained_associations':len(view.edges[pid]),'working_fields_unchanged':True}
assert 'id:cnqzTNngPVsAAAAAAAyk8g' in current
receipt={'status':'PASS_THREE_FINISHES_PRESERVATION','checked_utc':datetime.now(timezone.utc).isoformat(),'register_sha256':sha(OUT/'canonical-master-register.json'),'gallery_sha256':sha(new_db),'active_options':184,'retained_options':191,'retired_options':7,'current_frozen_fish_images':43,'listings':checks,'unrelated_active_products_checked':181,'asset_identity_bytes_paths_preserved':len(staged.assets),'all_source_specifications_preserved':191,'all_old_association_rows_preserved':True,'native_writes':0}
(OUT/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
