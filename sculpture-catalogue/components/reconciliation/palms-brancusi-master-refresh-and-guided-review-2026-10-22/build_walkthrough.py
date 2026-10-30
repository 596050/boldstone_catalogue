"""Link verified folder changes and the current owner review without promoting evidence."""
import csv,hashlib,html,json
from pathlib import Path
H=Path(__file__).resolve().parent;BASE=H.parents[2];OUT=BASE/'outputs/palms-brancusi-master-refresh-and-guided-review-2026-10-22';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
d=read(H/'combined-native-object-crosswalk.json');objects=d['objects'];earliest={};source=[]
for key in ['egyptian','gold','white']:
 o=read(H/'inputs'/f'{key}_overlay.before');source.append(o)
 for x in o['objects']:earliest.setdefault(x['file_id'],x['old_path'])
rows=[]
for fid,x in objects.items():
 if x['object_type']!='file':continue
 old=earliest[fid];old='/'+old.split('//',1)[1]if old.startswith('ns:202238505//')else old
 if old==x['current_path']:continue
 rows.append({'file_id':fid,'earlier_path':old,'current_path':x['current_path'],'actual_parent_id':x['current_parent_id'],'bytes':x['size'],'current_image_url':x['current_native_url']})
assert len(rows)==205
p=OUT/'Changed_Image_References_205.csv'
with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def link(u,label):return'<a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'
cards=[]
for o in source:
 for folder in o['prefix_maps']:
  fid=folder['file_id'];example=next(x for x in objects.values()if x['object_type']=='file'and x['current_parent_id']==fid)
  cards.append('<article><h2>'+esc(folder['current_name'])+'</h2><p>Earlier name: '+esc(folder['old_name'])+'</p><p>'+link(example['current_native_url'],'Example image')+' · '+link(folder['current_native_url'],'Containing folder')+'</p><p>Retained folder ID: '+esc(fid)+'<br>Example file ID: '+esc(example['file_id'])+'</p><p>Existing components, specifications, provenance and photo-role classifications retained.</p></article>')
css='body{font:16px/1.5 Arial,sans-serif;background:#f5f6f3;color:#28362d;margin:0}main{max-width:1100px;margin:auto;padding:24px}article{background:white;border:1px solid #d8ded4;padding:20px;margin:20px 0;overflow-wrap:anywhere}h1,h2{color:#344e40}a{color:#245f7a}th,td{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd}'
page=lambda title,body:'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1>'+body+'</main></body></html>'
folderpath=OUT/'folder-changes.html';folderpath.write_text(page('Egyptian Palms and Brancusi folder-reference updates','<p>Five approved group folders are now projected in the master. All530 original file IDs and25 folder IDs including the two family roots are preserved. No components or specifications have been added.</p>'+''.join(cards)+'<p>'+link('Changed_Image_References_205.csv','All205 changed image paths')+'</p>'))
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json')
x=next(option for option in g['options']if option['product_id']=='BSI-3635E3DC3434')
c=next(row for row in a['coverage']if row['option_id']==x['product_id'])
r=c['individual']['reference'];series=c['series']['reference']
body='<p>Individual photograph review1of18. The additional legacy Frozen Fish identity remains deferred; current Frozen Fish are70×15cm.</p><article><h2>'+esc(x['name'])+'</h2><p>'+link(r['image_url'],'Current detail image')+' · '+link(series['image_url'],'Workshop series image')+' · '+link(r['folder_url'],'Containing folder')+'</p><p>Individual: detail only. In situ: no verified image. Series: available, with Pewter already identified at the back right. Name and identity are retained.</p><table>'+''.join('<tr><th>'+esc(f)+'</th><td>'+esc(v['display'])+'</td></tr>'for f,v in x['master_fields'].items())+'</table><p>Owner question: Is there a separate photograph of this exact Pewter sculpture showing every edge? Enter its Dropbox filename/link if available, or keep the photograph requirement open. Actual measurements and fitted hardware remain separate from the estimates above.</p></article><p>'+link('individual-images.html','All18 separate photograph requests and deferred identity')+' · '+link('in-situ-images.html','61 in situ gaps')+' · '+link('series-images.html','18 series gaps')+' · '+link('specifications-to-verify.html','All qualified specification checks')+'</p>'
guide=OUT/'guided-review.html';guide.write_text(page('Current sculpture review in the terminal',body))
manifest={'status':'PASS_LINKED_CHANGE_WALKTHROUGH','pages':[{'path':str(z),'sha256':sha(z)}for z in [folderpath,guide]],'csv_files':[{'path':str(p),'sha256':sha(p),'rows':205}],'new_components_or_image_role_changes':0,'owner_guided_review':'IN_PROGRESS_AWAITING_FIRST_RESPONSE'};(H/'folder-refresh-report-verification.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':manifest['status'],'folder_changes':5,'current_owner_review':x['name']}))
