"""Retain later native handoffs without applying them to this media import."""
import hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;W=H.parents[3];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(H/'pending-followups.json')
for name,digest,reason in [
 ('dropbox-moon-and-shellwave-remaining-arrangement-renames-2026-10-23','971737f60a8366a08ecadbab83ee4203be5f677c69bef7758f5c348e4b2cb833','Compose after the queued pair and triptych overlays;37 same-ID file-name paths and two arrangements.'),
 ('dropbox-remaining-workshop-separation-2026-10-23','f57e25c0fdfae5f792b10fa8e5962288bde430b37233f20bec3b1f1fe5b8ae7b','Compose after the already imported Barbados/Sally workshop renames;2 same-ID folders now under Products/Workshop and Moulding;13 file paths, actual file parents unchanged.')]:
 path=W/'reports'/name/'current-reference-overlay.json';assert sha(path)==digest
 if not any(x['path']==str(path)for x in p['entries']):p['entries'].append({'kind':'COMPLETED_NATIVE_PATH_REFRESH','path':str(path),'sha256':digest,'status':'COMPLETE_VERIFIED','applied_to_current_frozen_release':False,'queue_only_no_coverage_change':True,'reason':reason})
leaf=W/'sculpture-catalogue/components/parallel-reviews/leaf-and-seaweed-context-review-20261023T142144Z/review-findings.json';assert sha(leaf)=='b0c806f1cd6995ec805693a7065b729c2ea87454a258556a4dba092daf2efa27'
p['later_read_only_candidates']={'path':str(leaf),'sha256':sha(leaf),'role_closures':0,'new_owner_decisions':0,'state':'Candidate source review only; no approval or role closure inferred.'}
p['frozen_current_scope']='Fountain Palm display082,14 actual file-parent references, Bronze Two Leaves approved courtyard right panel; no later folder or leaf-candidate import.'
(H/'pending-followups.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'queued_native_entries':len(p['entries']),'later_read_only_roles_closed':0}))
