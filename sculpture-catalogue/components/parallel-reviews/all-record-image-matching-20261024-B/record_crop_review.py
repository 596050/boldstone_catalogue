"""Record a manually inspected bounded comparison without inventing a match."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=argparse.ArgumentParser();a.add_argument('--keys',required=True);a.add_argument('--note',required=True);args=a.parse_args()
run=Path(read(H/'current-work.json')['run'])
manifest={r['key']:r for r in read(run/'source-evidence/crop-comparisons/manifest.json')}
p=H/'bounded-crop-comparison-review.json';d=read(p) if p.exists() else {}
for key in args.keys.split(','):
 r=manifest[key];assert sha(r['source_path'])==r['source_sha256'];assert sha(r['board'])==r['board_sha256']
 for c in r['candidates']:assert sha(c['cached_path'])==c['cached_sha256']
 d[key]={**r,'reviewed_utc':datetime.now(timezone.utc).isoformat(),'reviewer_thread_id':'01a13fe6-495b-7253-b923-31823b4cbca8','all_displayed_candidates_visually_reviewed':True,'status':'NO_NEW_EXACT_PHOTO_EDGE_SUPPORTED_BY_THIS_BOUNDED_COMPARISON','note':args.note,'new_photo_edges':0,'no_global_absence_claim':True}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'recorded':args.keys,'total':len(d)}))
