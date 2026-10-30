import collections,datetime,hashlib,html,json,pathlib,re,urllib.parse
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=pathlib.Path(__file__).parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(n):return json.loads((ROOT/n).read_text())
def dump(n,x):(ROOT/n).write_text(json.dumps(x,indent=2)+'\n')
def fq(s):return re.sub(r'^ns:\d+/','',s)
def url(s):return 'https://www.dropbox.com/home'+urllib.parse.quote(s,safe='/')
def hashbytes(data):return hashlib.sha256(data).hexdigest(),hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()
def board(rows,name,title,cols=3):
    w=510;h=370;im=Image.new('RGB',(w*cols,60+h*((len(rows)+cols-1)//cols)),(239,239,239));d=ImageDraw.Draw(im)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',19);small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
    d.text((12,15),title,fill='black',font=font)
    for i,r in enumerate(rows):
        x=i%cols*w;y=60+i//cols*h
        with Image.open(r['local_path']) as source:
            preview=ImageOps.exif_transpose(source).convert('RGB');preview.thumbnail((w-15,290));im.paste(preview,(x+(w-preview.width)//2,y+(290-preview.height)//2))
        d.text((x+10,y+300),r['name'].split('__')[-1],fill='black',font=font)
        d.text((x+10,y+326),r['folder_path'].rsplit('/',1)[-1],fill='black',font=small)
    im.save(ROOT/name,quality=93)
def main():
    native=read('fresh-native-before.json');prior=read('prior-originals-for-live-recheck.json');hashes={r['id']:r for r in read('fresh-native-hash-metadata.json')};entries={e['file_id']:e for e in native['listing']['entries']};meta={r['file']['id']:r['file'] for r in read('fresh-nine-and-selected-file-metadata.json')}
    folders={fq(e['path']):e['file_id'] for e in entries.values() if e['object_type']=='folder'};rows=[]
    assert len(prior)==99 and len(hashes)==99 and len(entries)==101 and not native['listing']['has_more']
    for r in prior:
        n=hashes[r['id']];e=entries[r['id']];assert n['path']==e['path']==r['path'] and n['name']==e['name']==r['name'] and n['size']==e['file']['size']==r['size']
        data=pathlib.Path(r['local_path']).read_bytes();sh,dh=hashbytes(data);assert len(data)==r['size'] and sh==r['sha256'] and dh==n['content_hash']
        path=fq(n['path']);parent=path.rsplit('/',1)[0];r={**r,'path_display':path,'folder_path':parent,'folder_id':folders[parent],'folder_url':url(parent),'image_url':url(parent)+'?preview='+urllib.parse.quote(r['name'],safe=''),'sha256':sh,'dropbox_content_hash':dh,'verification_method':'PRIOR_ORIGINAL_ACTUAL_BYTES_REHASHED_AGAINST_FRESH_NATIVE_HASH','verified_utc':NOW};rows.append(r)
    assert sum(r['size'] for r in rows)==784220860
    source=native['source']['folder'];dest=native['destination']['folder'];candidates=read('prior-nine-observations.json')['candidates'];byid={r['id']:r for r in rows};candidates=[byid[r['id']] for r in candidates];assert len(candidates)==9
    counts=collections.Counter(r['folder_id'] for r in rows);assert counts[source['id']]==86 and counts[dest['id']]==13
    destination_names={r['name'].casefold() for r in rows if r['folder_id']==dest['id']}
    for r in candidates:
        assert r['folder_id']==source['id'] and r['name'].casefold() not in destination_names and meta[r['id']]['path_display']==r['path_display']
    protected=read('protected-catalogue-references-before.json');assert all(not v for v in protected['current_candidate_ID_reference_occurrences'].values())
    selected=[]
    for o in protected['options']:
        for k in ['file_id','context_file_id']:
            fid=o.get(k)
            if fid:
                r=byid[fid];assert meta[fid]['path_display']==r['path_display'] and fid not in {c['id'] for c in candidates};selected.append({'role':k,'file_id':fid,'name':r['name'],'folder_id':r['folder_id'],'image_url':r['image_url'],'folder_url':r['folder_url']})
    dump('all99-verified-current-originals.json',rows);dump('unchanged-selected-reference-check.json',selected)
    plan={'schema':'boldstone.moonwave-nine-in-situ-filing-proposal.v1','status':'PROPOSED_NOT_APPLIED','created_utc':NOW,'scope':'/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moonwave','operation':'MOVE','source_folder':source['path_display'],'source_folder_id':source['id'],'source_folder_url':url(source['path_display']),'destination_folder':dest['path_display'],'destination_folder_id':dest['id'],'destination_folder_url':url(dest['path_display']),'folders_to_create':[],'copies':0,'deletes':0,'filename_changes':0,'source_count_before':86,'source_count_after':77,'destination_count_before':13,'destination_count_after':22,'family_images_preserved':99,'family_bytes_preserved':784220860,'family_folders_preserved':2,'moved_bytes':sum(r['size'] for r in candidates),'collision_check':'NO_EXISTING_DESTINATION_FILENAME_COLLISIONS','selected_primary_and_context_unchanged':selected,'basis':'Nine wider views show Moonwave mounted on an outdoor brick wall, with substantial surrounding wall or garden. They match the contextual type already present in Moonwave White In Situ. Different orientations are retained as views of the established design.','scope_limit':'No change is proposed to the remaining 77 White product or detail references; no new component, finish or physical-stock assertion.','moves':[{**r,'source_path':r['path'],'destination_path':dest['path_display']+'/'+r['name'],'destination_image_url':url(dest['path_display'])+'?preview='+urllib.parse.quote(r['name'],safe=''),'operation':'MOVE','old_rev':meta[r['id']].get('rev'),'old_client_modified':meta[r['id']].get('client_modified'),'old_server_modified':meta[r['id']].get('server_modified')} for r in candidates]}
    dump('proposed-nine-moonwave-in-situ-moves.json',plan)
    board(candidates,'nine-proposed-wall-setting-views.jpg','Nine proposed Moonwave wall-setting views - not applied')
    contexts=[r for r in rows if r['folder_id']==dest['id']];board(contexts,'existing-thirteen-in-situ-views.jpg','Existing Moonwave White In Situ - 13 current photographs',cols=4)
    nums={16,17,18,22,23,39,40,41,61,62,63,78,79,80,81,82,83}
    boundary=[r for r in rows if r['folder_id']==source['id'] and int(r['name'].split('__')[-1].split('.')[0]) in nums];board(boundary,'neighboring-product-and-wall-setting-views.jpg','Neighboring product and wall-setting views - filing comparison',cols=4)
    (ROOT/'previews').mkdir(exist_ok=True)
    parts=['<!doctype html><meta charset="utf-8"><title>Nine proposed Moonwave In Situ moves</title><style>body{font:17px system-ui;max-width:1200px;margin:25px}img{width:95%;max-width:1100px}article{border-bottom:1px solid #ccc;padding:15px;overflow-wrap:anywhere}a{color:#1244a7}</style><h1>Nine proposed Moonwave In Situ moves</h1><p>PROPOSED — NOT APPLIED. Move the nine listed wider wall-setting views into the existing Moonwave White In Situ folder. Source 86 → 77; destination 13 → 22; all 99 original images and both folders retained. Filenames and formats stay unchanged.</p><p>Every actual local original was rehashed against a fresh native Dropbox content hash. No fresh HTTP downloads were needed.</p><p><a href="'+html.escape(plan['source_folder_url'],quote=True)+'">Current source folder</a> · <a href="'+html.escape(plan['destination_folder_url'],quote=True)+'">Existing proposed destination</a> · <a href="all99-current-image-folder-links.html">All 99 current image and folder links</a></p>']
    for r in candidates:
        n=r['name'].split('__')[-1];preview=ROOT/'previews'/(n+'.jpg')
        with Image.open(r['local_path']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1600,1200));im.save(preview,quality=93)
        parts.append(f'<article><h2>{html.escape(n)}</h2><a href="{html.escape(r["image_url"],quote=True)}"><img src="previews/{urllib.parse.quote(preview.name)}"></a><p><a href="{html.escape(r["image_url"],quote=True)}">Current original image</a> · <a href="{html.escape(r["folder_url"],quote=True)}">Current containing folder</a> · <a href="{html.escape(plan["destination_folder_url"],quote=True)}">Proposed existing destination</a></p><p>{html.escape(r["name"])}</p></article>')
    (ROOT/'review-nine-proposed-moonwave-moves.html').write_text('\n'.join(parts))
    links=[{k:r[k] for k in ['id','family','name','size','folder_id','folder_path','folder_url','image_url','sha256','dropbox_content_hash']} for r in rows];dump('all99-current-image-folder-links.json',links)
    (ROOT/'all99-current-image-folder-links.html').write_text('<!doctype html><meta charset="utf-8"><title>Moonwave: all99 current image and folder links</title><style>body{font:16px system-ui;margin:20px}td{padding:8px;border-bottom:1px solid #ccc}</style><h1>Moonwave: all 99 current originals</h1><p>Read-only refresh. Nine candidate moves are proposed, not applied.</p><table><tr><th>Image</th><th>Containing folder</th></tr>'+''.join(f'<tr><td><a href="{html.escape(r["image_url"],quote=True)}">{html.escape(r["name"])}</a></td><td><a href="{html.escape(r["folder_url"],quote=True)}">{html.escape(r["folder_path"].rsplit("/",1)[-1])}</a></td></tr>' for r in rows)+'</table>')
    (ROOT/'all99-current-image-folder-links.tsv').write_text('filename\timage_url\tfolder_url\n'+''.join(f'{r["name"]}\t{r["image_url"]}\t{r["folder_url"]}\n' for r in rows))
    dup={k:[{'file_id':r['id'],'name':r['name'],'folder_id':r['folder_id']} for r in rows if r['dropbox_content_hash']==k] for k,n in collections.Counter(r['dropbox_content_hash'] for r in rows).items() if n>1};dump('native-identical-original-byte-groups-not-deletion-plan.json',dup)
    print(json.dumps({'status':'READ_ONLY_PACKET_PREPARED_FOR_VISUAL_REVIEW','files':99,'folders':2,'source':86,'destination':13,'candidates':len(candidates),'candidate_bytes':plan['moved_bytes'],'selected_references':selected,'identical_byte_groups':len(dup),'native_writes':0},indent=2))
if __name__=='__main__':main()
