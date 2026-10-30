"""Add a review of existing whole bordered Moonphase originals and actual folders."""
import hashlib,html,json,shutil,re
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2];O=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
g=read(H/'canonical-master-register.json');native=read(H/'current-native-reference-map.json');m=read(H/'report-verification.json');proof=read(H/'original-verification.json');sources={x['file_id']:x for x in proof['files']};images={};cards=[]
from urllib.parse import quote
def refs(fid):
 x=native['current_objects'][fid];p=native['current_objects'][x['parent_id']];return {'file_id':fid,'folder_id':x['parent_id'],'image_url':'https://www.dropbox.com/preview'+quote(x['display_path'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(p['display_path'],safe='/'),'name':x['name']}
def body(fid):
 r=refs(fid);s=sources[fid];src=Path(s['local_original']);dest=O/'images'/('bordered-'+src.name);shutil.copy2(src,dest);assert sha(dest)==s['sha256'];images[fid]={'path':str(dest),'sha256':sha(dest),'file_id':fid,'relative_path':str(dest.relative_to(O))}
 return '<p><a href="'+esc(r['image_url'])+'"><img src="'+esc(str(dest.relative_to(O)))+'" alt="'+esc(r['name'])+'"></a></p><p><a href="'+esc(r['image_url'])+'">Dropbox image</a> · <a href="'+esc(r['folder_url'])+'">Actual containing folder</a></p><p>'+esc(r['name'])+'</p><small>'+esc(r['file_id']+' / '+r['folder_id'])+'</small>'
cards.append('<article id="BSI-65A93033A200"><h2>Moonphase One — White with Border (MP1)</h2><p>Selected listing image001 retained.</p>'+body('id:cnqzTNngPVsAAAAAAAylYg')+'<p>Original008 is an additional existing individual reference, now in this same individual folder. Its stable file ID is retained.</p>'+body('id:cnqzTNngPVsAAAAAAAt4DQ')+'</article>')
cards.append('<article id="BSI-4515726BBC18"><h2>Moonphase Two — White with Border (MP2)</h2><p>Selected listing image001 and its individual containing folder retained.</p>'+body('id:cnqzTNngPVsAAAAAAAylZA')+'</article>')
ids=[x['file_id']for x in read(H/'path-change-history.json')['changes']if x['current']['object_type']=='file'and x['current_parent_id']=='id:cnqzTNngPVsAAAAAAAydLQ'];assert len(ids)==7
cards.append('<article id="bordered-pair"><h2>Moonphase 1 and Moonphase 2 With Borders White</h2><p>Seven pair/detail originals retain their existing IDs in the renamed group folder. The whole001 pair image is also the qualified brick-wall display reference for both existing bordered options. Cropping and physical specification inference are not used. Image origin and authentic installation remain unverified.</p>'+''.join(body(fid)for fid in ids)+'</article>')
css=re.search(r'<style>(.*?)</style>',(O/'index.html').read_text(),re.S).group(1)
p=O/'bordered-moonphase-changes.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bordered Moonphase references and folders</title><style>'+css+'</style></head><body><main><h1>Bordered Moonphase references and folders</h1><p><a href="index.html">Current photograph requests</a> · <a href="active-in-situ-photo-requests.html">Active context photographs</a> · <a href="series-images.html">Series requests</a></p><p>One completed file move and one completed folder rename are reflected by stable Dropbox IDs. Two qualified display associations are added. Individual primaries, component identities, working specifications, prices, availability and held cases are preserved.</p>'+''.join(cards)+'</main></body></html>')
m['pages'].append({'path':str(p),'sha256':sha(p),'cards':3});m['thumbnail_files']+=list(images.values());m['counts'].update(current_file_paths_refreshed=8,current_folder_names_refreshed=1,actual_parent_id_changes=1,additional_individual_references=1)
for name in ['index.html','current-context-references.html']:
 p=O/name;t=p.read_text().replace('</nav>',' · <a href="bordered-moonphase-changes.html">Bordered Moonphase folder changes</a></nav>',1);p.write_text(t)
 for x in m['pages']:
  if x['path']==str(p):x['sha256']=sha(p)
write(H/'report-verification.json',m)
print(json.dumps({'status':'BORDER_REVIEW_ADDED','whole_originals_copied_unchanged':len(images),'cards':3}))
