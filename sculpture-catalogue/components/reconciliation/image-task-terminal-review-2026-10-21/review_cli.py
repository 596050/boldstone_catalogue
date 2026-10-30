"""Incremental terminal ledger: record explicit, evidence-bound review decisions."""
import argparse,collections,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
ap=argparse.ArgumentParser();ap.add_argument('command',choices=['status','apply']);ap.add_argument('--decisions');args=ap.parse_args()
items=read(HERE/'terminal-review-items.json')
if args.command=='apply':
 decisions=read(args.decisions);byseq={x['sequence']:x for x in items}
 for d in decisions:
  x=byseq[d['sequence']];assert d['finding']and d['evidence_plates']and d['review_state']!='QUEUED'
  for p in d['evidence_plates']:assert Path(p).is_file()
  event={'recorded_utc':datetime.now(timezone.utc).isoformat(),**d,'task_id':x['task_id'],'source_reference_id':x['prior_action']['reference']['file_id']}
  x['review_state']=d['review_state'];x['findings'].append(event)
  with(HERE/'review-events.jsonl').open('a')as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
  print(f"{x['sequence']:03d} {d['review_state']} | {x['name']} | {x['requested_role']}\n    {d['finding']}")
 write(HERE/'terminal-review-items.json',items)
states=collections.Counter(x['review_state']for x in items);p=read(HERE/'progress.json');p.update(updated_utc=datetime.now(timezone.utc).isoformat(),reviewed=sum(x['review_state']!='QUEUED'for x in items),queued=states['QUEUED'],states=dict(states),resolved=sum(x['review_state']=='RESOLVED_VERIFIED_REFERENCE'for x in items))
write(HERE/'progress.json',p);print(json.dumps({'reviewed':p['reviewed'],'queued':p['queued'],'states':p['states']}))
