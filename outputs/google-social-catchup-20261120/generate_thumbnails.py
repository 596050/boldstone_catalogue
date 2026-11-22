"""Small local review images; publication media are untouched."""
import concurrent.futures,json,sqlite3,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest
ids={p['catalogue_id'] for p in json.loads((OUT/'coverage-inventory.json').read_text())['sculptures']}
db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
jobs=[json.loads(p) for (p,) in db.execute('SELECT payload FROM jobs')]
jobs=[p for p in jobs if p['platform']=='google_business_profile' and p['catalogue_id'] in ids]
(OUT/'thumbnails').mkdir(exist_ok=True)
def create(p):
 source=Path(p['media_path']);target=OUT/'thumbnails'/(p['catalogue_id']+'.png')
 if not target.exists():subprocess.run(['/usr/bin/sips','-Z','480','-s','format','png',str(source),'--out',str(target)],capture_output=True,check=True,timeout=30)
 return {'catalogue_id':p['catalogue_id'],'source_sha256':digest(source.read_bytes()),'thumbnail_sha256':digest(target.read_bytes()),'bytes':target.stat().st_size}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(create,jobs))
atomic_json(OUT/'thumbnail-receipts.json',receipts)
print(json.dumps({'review_thumbnails':len(receipts),'bytes':sum(r['bytes'] for r in receipts),'publication_media_changed':False}))
