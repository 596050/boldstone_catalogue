"""Keep a qualified paired-display reference without claiming a complete set."""
from common import *
from datetime import datetime,timezone

pid='BSI-DB7FBD3E1323';fid='id:cnqzTNngPVsAAAAAAAucig';o=options[pid];r=files[fid]
proof=read(H/'golden-series-original-proof.json')
assert proof['id']==fid and proof['content_hash']==r['content_hash'] and proof['size']==r.get('bytes',r.get('size'))
assert not o.get('current_series_reference') and o['historical_series_reference']['file_id']=='id:cnqzTNngPVsAAAAAAAuh7g'
scope='Qualified paired-display reference. Golden Spiral is fully shown on the right; the gold relief companion is only partly visible at the left edge. This is not a complete set portrait. Companion identity, displayed scale, exact cast and actual installation remain unverified. No physical or commercial field is inferred.'
evidence={'reviewed_utc':datetime.now(timezone.utc).isoformat(),'product_id':pid,'file_id':fid,'folder_id':r['folder_id'],'image_url':r['image_url'],'folder_url':r['folder_url'],'original_proof':str(H/'golden-series-original-proof.json'),'original_proof_sha256':sha(H/'golden-series-original-proof.json'),'position':'Whole Golden Spiral panel at right; partial gold companion at left','scope':scope,'owner_primary_choice_remains_separate':True,'native_or_app_writes':0}
write(H/'golden-series-binding.json',evidence)
o['current_series_reference']={k:r[k] for k in ['file_id','folder_id','image_url','folder_url']}
o['current_series_reference'].update(scope=scope,position=evidence['position'],evidence=str(H/'golden-series-binding.json'),evidence_sha256=sha(H/'golden-series-binding.json'))
o['photo_coverage']['series']='Available — qualified paired display; companion partial'
g['latest_verified_native_filename_import']['qualified_series_replacements'].append(evidence)
write(H/'canonical-master-register.json',g)
for r in overlay:
    if r['file_id']==fid:r['selected_references'].append({'product_id':pid,'name':o['name'],'role':'qualified paired series; companion partial'})
write(H/'current-image-overlay.json',overlay)
report=read(H/'register-preparation.json');report['new_series_losses']=[x for x in report['new_series_losses'] if x!=pid];report['series_changes'].append(evidence);report['current_series_references']+=1;report['register_sha256']=sha(H/'canonical-master-register.json');write(H/'register-preparation.json',report)
print('Golden Spiral paired-display reference bound; companion remains explicitly partial; no source specifications or Primary changed')
