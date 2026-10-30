import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];R=B.parent;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();scope=read(H/'scope.json');p=read(H/'inputs/master_pointer.before');prior=read(B/p['queued_followup_packets']['path']);applied=set(scope['approvals'].values())|set(scope['overlays'].values());entries=[]
for x in prior['entries']:
 path=x.get('path',x.get('packet',x.get('overlay')))
 if isinstance(path,dict):path=path.get('path')
 if path and str(Path(path).resolve())not in applied:entries.append(x)
paths=[]
for d in ['moonphase-four-white-gold-image-approval-2026-10-23','cup-ring-white-in-situ-approval-2026-10-23','spiral-crs1-in-situ-approval-2026-10-23','brancusi-one-garden-variation-approval-2026-10-23']:paths.append(('owner-image-approval',B/'components/parallel-reviews'/d/'owner-image-approval.json'))
base=B/'components/parallel-reviews/guided-photography-review-2026-10-23'
for number in [1,2,3]:paths.append(('owner-image-role-approval',base/f'lava-moon-{number}-sandstone-owner-image-role-approval.json'))
paths.append(('owner-review-outcome',base/'lava-moon-1-sandstone-review-decision.json'))
for folder in ['dropbox-seaweed-ripple-group-rename-2026-10-23','dropbox-leaf-form-group-renames-2026-10-23']:paths.append(('native-overlay',R/'reports'/folder/'current-reference-overlay.json'))
for kind,path in paths:
 if not path.is_file():continue
 d=read(path)
 if any(x.get('path')==str(path)for x in entries):continue
 entries.append({'kind':kind,'path':str(path),'sha256':sha(path),'status':d.get('status'),'product_id':d.get('product_id'),'decision_id':d.get('decision_id'),'applied_to_current_frozen_release':False})
out={'status':'LATER_APPROVALS_AND_NATIVE_CHANGES_READY_FOR_NEXT_INCREMENTAL_IMPORT','recorded_utc':datetime.now(timezone.utc).isoformat(),'frozen_current_scope':str(H/'scope.json'),'entries':entries,'owner_physical_measurement_reply_pending':'Acanthus One Leaf Left Sandstone; exact dimensions/depth, weighed mass, material recipe, fitted fixing type/count','no_current_count_reduction_inferred_from_queued_packets':True};(H/'pending-followups.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'pending_entries':len(entries),'kinds':[x['kind']for x in entries]}))
