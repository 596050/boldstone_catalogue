"""Read-only terminal walk-through of the current sculpture records."""
import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
p=argparse.ArgumentParser();p.add_argument('command',choices=['show','status'],nargs='?',default='status');p.add_argument('--phase',choices=['individual','in_situ','series','physical'],default='individual');p.add_argument('--position',type=int,default=1);args=p.parse_args()
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');options={x['product_id']:x for x in g['options']};coverage={x['option_id']:x for x in a['coverage']}
roles={'individual':'Individual','in_situ':'In situ','series':'Series'}
if args.phase=='physical':queue=list(options)
else:queue=[x['option_id']for x in a['missing_pictures']if x['status']=='Open'and x['role']==roles[args.phase]and x['action_type']=='Find / capture']
if args.command=='status':
 print('Current catalogue:188 options /112 working component identities /1128 qualified field groups')
 print('Individual:17 separate-photo gaps plus1 deferred legacy identity. In situ:63. Series:18.')
 print('One Leaf Pewter complete individual image and qualified six-field acceptance recorded.')
 print('Sandstone detail and workshop image: archived copies available; current Dropbox source lookup NOT_FOUND.')
 print('Later owner-review packets from other terminals remain in pending-followups.json until the next controlled import.')
else:
 if not 1<=args.position<=len(queue):raise SystemExit('Position out of range')
 oid=queue[args.position-1];x=options[oid];r=coverage[oid]['individual'].get('reference')or x
 print(f'[{args.position}/{len(queue)}] {x["name"]} ({oid})')
 print('Example image: '+(r.get('archived_original')or r.get('image_url','No bound image')))
 print('Containing folder: '+r.get('folder_url','No current containing folder'))
 if r.get('archived_original'):
  print('Dropbox source: NOT_FOUND; image above is an archived reference copy. Historical IDs are retained.')
  print('Current family navigation: '+r.get('current_family_navigation_url',''))
 print('File ID: '+str(r.get('file_id'))+' | Folder ID: '+str(r.get('folder_id')))
 for f,v in x['master_fields'].items():print(f+' | '+v['display'])
 print('Photo roles: '+json.dumps(x['photo_coverage'],ensure_ascii=False))
 print('Read-only display. Physical verification and image-role approval remain separate.')
