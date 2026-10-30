"""Save an explicit human-reviewed follow-up against a sealed comparison board."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--key',required=True);p.add_argument('--candidates',default='');p.add_argument('--notes',required=True);a=p.parse_args()
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=Path(read(H/'current-work.json')['run'])
manifest=read(run/'source-evidence/unresolved-comparisons/manifest.json')
r=next(x for x in manifest if x['key']==a.key)
assert sha(r['board'])==r['board_sha256'];assert sha(r['source_path'])==r['source_sha256']
indices=[int(x) for x in a.candidates.split(',') if x]
decisions=read(H/'source-visual-decisions.json')
entries=[]
for index in indices or [None]:
    c=r['candidates'][index-1] if index else None
    if c:assert sha(c['cached_path'])==c['cached_sha256']
    entries.append({'key':a.key,'gallery_entry_id':r['gallery_entry_id'],
        'source_path':r['source_path'],'source_sha256':r['source_sha256'],
        'file_id':c['file_id'] if c else None,'current_file_evidence':c,
        'source_visual_role':decisions[a.key]['source_visual_role'],
        'same_photo_correspondence_supported':bool(c),
        'board':r['board'],'board_sha256':r['board_sha256'],
        'notes':a.notes,'reviewed_utc':datetime.now(timezone.utc).isoformat(),
        'method':'Visually compared full displayed source and candidate frames; border/rotation rankings were triage only.',
        'original_encoded_byte_identity':False,'physical_cast_identity':False,
        'variant_assignment_certified':False,'new_canonical_or_native_write':False})
path=H/'source-visual-followups.json';all_rows=read(path) if path.exists() else {}
all_rows[a.key]=entries
path.write_text(json.dumps(all_rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'key':a.key,'explicit_supported_files':len(indices),'followup_entries':len(all_rows)}))
