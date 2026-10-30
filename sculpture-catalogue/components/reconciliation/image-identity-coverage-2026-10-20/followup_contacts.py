"""Expose alternate full views and bounded role-specific media candidates."""
from pathlib import Path
from collections import defaultdict
from PIL import Image, ImageOps, ImageDraw, ImageFont
import json
import sys

HERE = Path(__file__).resolve().parent
read = lambda p: json.loads(Path(p).read_text())
g = read(read(HERE/'input-manifest.json')['master_register']['snapshot'])
a = read(HERE/'asset-index.json')
oldq = read(HERE/'visual-queue.json')
seen = {x['file_id'] for x in oldq}
byfolder = defaultdict(list)
for x in a.values(): byfolder[x['folder_id']].append(x)
for v in byfolder.values(): v.sort(key=lambda x:x['path'])
no_context = {x['product_id'] for x in g['options']} - {x['product_id'] for x in oldq if x['category']=='context'}
obs = read(HERE/'manual-observations.json')
primary_follow = set(obs['primary_detail_labels'] + obs['primary_complete_group_labels'])
folder_targets = defaultdict(set)
folder_roles = defaultdict(set)
for i,x in enumerate(g['options'],1):
    if f'P{i:03d}' in primary_follow:
        folder_targets[x.get('folder_id')].add(x['product_id'])
        folder_roles[x.get('folder_id')].add('alternate full individual view')
all_primary_folders = set(folder_targets)
for c in g['source_media_configuration_coverage']:
    targets = set(c.get('exact_supported_target_ids',[]))
    if targets & no_context:
        for f in c['baseline_context_folder_ids']:
            folder_targets[f].update(targets & no_context)
            folder_roles[f].add('unlinked context candidate')
    for f in c['baseline_series_folder_ids']:
        folder_targets[f].update(targets)
        folder_roles[f].add('series candidate')
replacements = {x['old_folder_id']:x['new_folder_id'] for x in read(HERE/'live-inventory.json')['completed_path_overlay']['retired_folder_replacements']}
for old,new in replacements.items():
    if old in folder_targets:
        folder_targets[new].update(folder_targets.pop(old))
        folder_roles[new].update(folder_roles.pop(old))
queue=[]
for f in sorted(folder_targets):
    candidates = [x for x in byfolder[f] if x['file_id'] not in seen]
    if f in all_primary_folders:
        selected = candidates
    else:
        indices = sorted({0,len(candidates)//2,len(candidates)-1}) if candidates else []
        selected = [candidates[i] for i in indices]
    for x in selected:
        if x['file_id'] in seen: continue
        seen.add(x['file_id'])
        queue.append({'label':f'A{len(queue)+1:03d}','category':'followup','name':x['name'],
            'file_id':x['file_id'],'product_ids':sorted(folder_targets[f]),'role_candidates':sorted(folder_roles[f]),
            'folder_current_file_count':len(byfolder[f]),'folder_full_review_selected':f in all_primary_folders})
prefix='followup'
if '--groups' in sys.argv:
    prefix='group-extra'
    seen.update(x['file_id'] for name in ['followup-queue.json','moon-fishwave-extra-queue.json'] for x in read(HERE/name))
    group_folders={x.get('folder_id') for x in g['arrangement_context_references'] if x.get('folder_id')}
    files=sorted([x for x in a.values() if x['folder_id'] in group_folders and x['file_id'] not in seen],key=lambda x:x['path'])
    queue=[{'label':f'D{i:03d}','category':'Group-only source complete review','name':x['name'],'file_id':x['file_id'],
        'product_ids':[],'role_candidates':['component identification in group source'],
        'folder_current_file_count':len(byfolder[x['folder_id']]),'folder_full_review_selected':True}
        for i,x in enumerate(files,1)]
if '--moon-fishwave' in sys.argv:
    prefix='moon-fishwave-extra'
    queue=[{'label':f'B{i:03d}','category':'Moon Fishwave display and room review','name':x['name'],
            'file_id':x['file_id'],'product_ids':[g['options'][119]['product_id'],g['options'][120]['product_id']],
            'role_candidates':['full component display or room presentation'],
            'folder_current_file_count':len(byfolder['id:cnqzTNngPVsAAAAAAAyisg']),'folder_full_review_selected':True}
           for i,x in enumerate([x for x in byfolder['id:cnqzTNngPVsAAAAAAAyisg'] if x['file_id'] not in seen],1)]
(HERE/(prefix+'-queue.json')).write_text(json.dumps(queue,ensure_ascii=False,indent=2)+'\n')
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',13)
head=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',21)
manifest=[]
for start in range(0,len(queue),20):
    chunk=queue[start:start+20]
    plate=Image.new('RGB',(1440,1360),'#f3f5f2');draw=ImageDraw.Draw(plate)
    draw.text((15,12),f'Alternate individual / context / series candidates | page {start//20+1}',font=head,fill='#25382c')
    for j,x in enumerate(chunk):
        asset=a[x['file_id']];local=asset['full'] or asset['thumb'];left,top=(j%4)*360+8,(j//4)*260+48
        with Image.open(local) as im:
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((344,203));plate.paste(im,(left+(344-im.width)//2,top))
        title=x['label']+' '+x['name']
        for line in range(3):draw.text((left,top+205+line*16),title[line*46:(line+1)*46],font=font,fill='#16281d')
    path=HERE/'contact-sheets'/f'{prefix}-{start//20+1:02d}.jpg';plate.save(path,quality=90)
    manifest.append({'path':str(path),'labels':[x['label'] for x in chunk]})
(HERE/(prefix+'-contact-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'followup_images':len(queue),'plates':len(manifest),'unique_candidate_folders':len(folder_targets),'scope':'All unreviewed files in flagged primary folders; first/middle/last unseen references in other exact-crosswalk role folders. Unselected files are not absence evidence.'}))
