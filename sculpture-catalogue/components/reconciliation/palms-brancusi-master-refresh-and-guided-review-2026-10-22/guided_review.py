"""Show one catalogue review at a time in the terminal without changing evidence."""
import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text())
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');opts={x['product_id']:x for x in g['options']};cov={x['option_id']:x for x in a['coverage']}
tasks=[x for x in a['missing_pictures']if x['status']=='Open']
queues={phase:[x['option_id']for x in tasks if x['role']==role and x['action_type']=='Find / capture']for phase,role in [('individual','Individual'),('in_situ','In situ'),('series','Series')]};queues['physical']=list(opts)
statefile=H/'guided-owner-review-state.json'
if not statefile.exists():
 state={'status':'OWNER_GUIDED_REVIEW_IN_PROGRESS','current_phase':'individual','current_position':1,'current_option_id':queues['individual'][0],'queues':queues,'phase_positions':{k:1 for k in queues},'owner_responses':[],'completed_owner_reviews':[],'deferred_legacy_identity':1,'frozen_fish_current_default':'70 cm high × 15 cm wide','new_picture_candidates':str(H/'new-native-photo-candidates.json'),'scope':'Review answers and evidence remain separate. Keeping a gap open does not verify a specification or close an image role.','pending_question':'Complete isolated Pewter image, or retain capture requirement?','physical_values_are_not_inferred_from_photographs':True}
 statefile.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
state=read(statefile);p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['status','show'],nargs='?',default='show');p.add_argument('--phase',choices=list(queues),default=state['current_phase']);p.add_argument('--position',type=int);args=p.parse_args()
if args.command=='status':
 print('Current review:',state['current_option_id']);print('Remaining source queues:18 individual photographs,61 in situ images,18 series images;1 deferred Frozen Fish identity.');print('Owner review answers recorded:',len(state['owner_responses']));raise SystemExit(0)
position=args.position or state['phase_positions'][args.phase];oid=queues[args.phase][position-1];x=opts[oid];c=cov[oid];r=c['individual'].get('reference')or{};print(f'{args.phase.upper()} REVIEW {position}/{len(queues[args.phase])}: {x["name"]}');print('Option:',oid);print('Component:',x['canonical_component_id']);print('Example image:',r.get('image_url')or x['image_url']);print('Containing folder:',r.get('folder_url')or x['folder_url']);print('Retained file ID:',r.get('file_id')or x['file_id']);print('Actual folder ID:',r.get('folder_id')or x['folder_id']);print()
for role in ['individual','in_situ','series']:
 print(role.replace('_',' ').title()+':',c[role]['status'])
 if c[role].get('reference'):print(' Reference:',c[role]['reference']['image_url'])
 if c[role].get('member_position'):print(' Position:',c[role]['member_position'])
print('\nCURRENT WORKING DETAILS')
for field,v in x['master_fields'].items():print(field+':',v['display'])
print('\nNEXT EVIDENCE: Full individual photo with all edges; an exact finish-specific in-situ image if missing; measurements, weighed mass, maker material statement and rear fixing photo where estimates remain. Retain source qualifications. No crops or new physical measurements are created by this review.')
