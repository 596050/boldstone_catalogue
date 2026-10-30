"""Record manually supplied visual decisions against the viewed board manifest."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
H=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--board',type=int,required=True);parser.add_argument('--roles',required=True);parser.add_argument('--unmatched',default='');parser.add_argument('--notes',default='{}');args=parser.parse_args()
run=Path(json.loads((H/'current-work.json').read_text())['run'])
manifest=json.loads((run/'source-evidence/comparison-boards/manifest.json').read_text())
board=manifest[args.board-1];assert hashlib.sha256(Path(board['board']).read_bytes()).hexdigest()==board['sha256']
roles=args.roles.split();assert len(roles)==len(board['entries'])
names={'I':'individual','D':'detail','R':'rear','T':'installation','G':'group_context','U':'uncertain'}
unmatched={int(x) for x in args.unmatched.split(',') if x};notes=json.loads(args.notes)
p=H/'source-visual-decisions.json';decisions=json.loads(p.read_text()) if p.exists() else {}
for i,(entry,role) in enumerate(zip(board['entries'],roles),1):
    assert role in names
    key=f"{entry['offer_ref']}:{entry['gallery_order']:02d}"
    row={**entry,'source_visual_role':names[role],
        'visual_assessment':'CURRENT_CANDIDATE_CORRESPONDS_TO_SOURCE_PHOTOGRAPH' if i not in unmatched else 'DISPLAYED_CANDIDATE_DOES_NOT_ESTABLISH_SAME_PHOTOGRAPH',
        'matched_candidate_file_id':entry['candidate_file_id'] if i not in unmatched else None,
        'evidence_board':board['board'],'evidence_board_sha256':board['sha256'],
        'reviewed_utc':datetime.now(timezone.utc).isoformat(),
        'method':'Assistant visually compared both complete displayed frames, including sculpture relief, frame composition, finish pattern and background when present. Numerical score was candidate triage only.',
        'notes':notes.get(str(i),'Visible composition corresponds at the displayed resolution; no identical encoded original-file claim.'),
        'full_resolution_fine_detail_certified':False,'physical_specification_verified':False,
        'exact_variant_configuration_verified':False,'new_native_or_canonical_write':False}
    if role=='R':row['rear_finish_and_current_hardware_attribution']='Unverified; photograph does not certify which current finish/cast has this rear hardware or its load rating.'
    if role=='G':row['group_policy']='Context only; no new component identity or individual sale-unit inferred from group photography.'
    if role=='T':row['installation_provenance']='Contextual room or display view; photographic/composite creation origin not newly certified.'
    if key in decisions:
        old=decisions[key];row['previous_decision']=old
    decisions[key]=row
p.write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'recorded_board':args.board,'entries':len(roles),'total_visual_decisions':len(decisions)}))
