import json,argparse
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2];p=argparse.ArgumentParser();p.add_argument('--option',default='BSI-C41824131174');p.add_argument('--list',action='store_true');args=p.parse_args();pointer=json.loads((B/'current-master.json').read_text());g=json.loads((B/pointer['register']).read_text());a=json.loads(Path(pointer['latest_image_coverage_audit']['path']).read_text());rows=[x for x in a['missing_pictures']if x['status']=='Open'and x['role']=='Individual']
if args.list:
 for i,x in enumerate(rows,1):print(f"{i}. {x['name']} ({x['action_type']})\n   Image: {x['reference']['image_url']}\n   Folder: {x['reference']['folder_url']}")
 raise SystemExit(0)
x=next(x for x in g['options']if x['product_id']==args.option);c=next(x for x in a['coverage']if x['option_id']==args.option)
print(x['name']+'\n'+x['product_id']+' / '+x['canonical_component_id']+'\n')
for f,v in x['master_fields'].items():print(f+': '+v['display'])
print('\nImage: '+x['image_url']+'\nContaining folder: '+x['folder_url']+'\nTechnical individual photo status: '+c['individual']['status'])
if args.option=='BSI-C41824131174':print('\nNEXT PHYSICAL CHECK\nRecord actual width x height x maximum projection in cm, weighed bare-panel kg, maker material recipe, and fitted fixing type/count. Unknown values remain unknown. The workshop Sandstone panel is BACK CENTRE; its accepted identity is unchanged.\nWorkshop image: '+c['series']['reference']['image_url'])
print('\nPublished queue: '+str(len(rows))+' individual/identity actions; '+str(a['counts']['in_situ_statuses']['No verified image'])+' in situ; '+str(a['counts']['series_statuses']['No verified image'])+' series. Later approved packets remain separately queued for the next import.')
