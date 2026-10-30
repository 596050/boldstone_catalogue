import argparse,collections,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text())
ap=argparse.ArgumentParser();ap.add_argument('decisions');args=ap.parse_args();rows=read(H/'candidate-checks.json');byid={x['sequence']:x for x in rows}
for d in read(args.decisions):
 x=byid[d['sequence']];assert d['finding']and d['evidence_plates']
 assert x['state']=='PENDING_DEEP_REVIEW','Use a distinct follow-up event for already reviewed rows'
 proof=[{'path':str(H/'plates'/p),'sha256':hashlib.sha256((H/'plates'/p).read_bytes()).hexdigest()}for p in d['evidence_plates']]
 event={'recorded_utc':datetime.now(timezone.utc).isoformat(),**d,'evidence_plates':proof,'option_id':x['option_id'],'role':x['role'],'current_native_file_ID':x['candidate_reference']['file_id'],'current_native_folder_ID':x['candidate_reference']['folder_id'],'physical_specification_or_platform_match_upgraded':False}
 x['state']=d['state'];x['findings'].append(event)
 with(H/'decision-events.jsonl').open('a')as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
 print(str(x['sequence']).zfill(3)+' '+x['state']+' | '+x['name']+' | '+x['role']+'\n    '+d['finding'])
(H/'candidate-checks.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');p={'reviewed':sum(x['state']!='PENDING_DEEP_REVIEW'for x in rows),'queued':sum(x['state']=='PENDING_DEEP_REVIEW'for x in rows),'states':dict(collections.Counter(x['state']for x in rows))};(H/'progress.json').write_text(json.dumps(p,indent=2)+'\n');print(json.dumps(p))
