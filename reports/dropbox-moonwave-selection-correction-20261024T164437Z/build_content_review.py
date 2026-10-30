import collections,datetime,hashlib,html,json,pathlib,re,urllib.parse
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=pathlib.Path(__file__).parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(n,x):(ROOT/n).write_text(json.dumps(x,indent=2)+'\n')
def fq(s):return re.sub(r'^ns:\d+/','',s)
def home(s):return 'https://www.dropbox.com/home'+urllib.parse.quote(s,safe='/')
def main():
    native=json.loads((ROOT/'fresh-native-before.json').read_text());entries={e['file_id']:e for e in native['entries']};fresh={r['id']:r for r in json.loads((ROOT/'fresh-native-content-hashes.json').read_text())}
    prior=json.loads(pathlib.Path('reports/dropbox-moonwave-nine-in-situ-review-20261024T144130Z/all99-verified-current-originals.json').read_text());assert len(prior)==99
    groups={'white_full_brick_wall_views':{'title':'White: complete sculpture mounted on brick wall','description':'Complete mounted views, including close and wide framing. Whether the brick wall is being used as a product backdrop or an installation setting is not established by framing alone.','rows':[]},'white_details':{'title':'White: detail photographs','description':'Crops of the relief or surface, without a complete view of the sculpture.','rows':[]},'white_isolated':{'title':'White: isolated product images','description':'Full product reference images against a plain background.','rows':[]},'insitu_full_brick_wall_views':{'title':'Existing In Situ: complete brick-wall views','description':'These are already in In Situ; the folder label itself does not establish installation provenance.','rows':[]},'insitu_full_room_views':{'title':'Existing In Situ: complete room views','description':'Complete sculpture shown against a red room wall; wider photographs include furnishings. Authenticity and same-cast provenance remain unverified.','rows':[]},'insitu_details':{'title':'Existing In Situ: detail photographs','description':'Close detail images associated with the room or brick-wall sequences. Current filing is retained while the owner clarifies the boundary.','rows':[]}}
    rows=[]
    for r in prior:
        n=fresh[r['id']];e=entries[r['id']];assert n['path']==e['path']==r['path'] and n['size']==e['file']['size']==r['size']
        data=pathlib.Path(r['local_path']).read_bytes();sh=hashlib.sha256(data).hexdigest();dh=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest();assert sh==r['sha256'] and dh==n['content_hash']
        path=fq(e['path']);parent=path.rsplit('/',1)[0];num=int(r['name'].split('__')[-1].split('.')[0]);white=parent.endswith('/Moonwave White')
        if white:
            if num in {85,86}:group='white_isolated'
            elif num in set(range(4,12))|set(range(29,32))|{67}|set(range(74,78))|{84}:group='white_details'
            else:group='white_full_brick_wall_views'
        elif num in {1,2,3,4,11}:group='insitu_full_brick_wall_views'
        elif num in {5,6,7,10}:group='insitu_full_room_views'
        else:group='insitu_details'
        r={**r,'folder_path':parent,'folder_url':home(parent),'image_url':home(parent)+'?preview='+urllib.parse.quote(e['name'],safe=''),'visible_content_group':group,'fresh_original_rehash_utc':NOW,'native_filing_action':'NONE','InSitu_decision':'PENDING_OWNER_CRITERION_CLARIFICATION'};rows.append(r);groups[group]['rows'].append(r)
    counts={k:len(g['rows']) for k,g in groups.items()};assert list(counts.values())==[67,17,2,5,4,4];assert sum(r['size'] for r in rows)==784220860
    old=json.loads(pathlib.Path('reports/dropbox-moonwave-nine-in-situ-review-20261024T144130Z/proposed-nine-moonwave-in-situ-moves.json').read_text());oldids={r['id'] for r in old['moves']};assert oldids<={r['id'] for r in groups['white_full_brick_wall_views']['rows']}
    dump('all99-current-links-and-visible-content.json',rows);dump('descriptive-content-groups-not-move-plan.json',groups)
    (ROOT/'thumbnails').mkdir(exist_ok=True)
    parts=['<!doctype html><meta charset="utf-8"><title>Moonwave: corrected full-image content review</title><style>body{font:17px system-ui;margin:28px;max-width:1500px}article{display:inline-block;vertical-align:top;width:330px;min-height:350px;margin:5px;padding:10px;border:1px solid #bbb;overflow-wrap:anywhere}article img{width:320px;height:230px;object-fit:contain}section{clear:both;margin-top:30px}p{line-height:1.5}.note{padding:16px;background:#fff0ce}</style><h1>Moonwave: full 99-image review</h1><p class="note">The earlier nine-image move proposal is withdrawn. No files have moved. These groups describe what is visible; they do not presume which photographs the owner wants called In Situ. The outstanding question is whether full brick-wall mounted views count as In Situ, including close framing, or remain White product/display references.</p>']
    for group,g in groups.items():
        parts.append(f'<section id="{group}"><h2>{html.escape(g["title"])} — {len(g["rows"])} images</h2><p>{html.escape(g["description"])}</p>')
        for r in g['rows']:
            name=r['name'].split('__')[-1];thumb=r['id'].replace('id:','')+'.jpg'
            with Image.open(r['local_path']) as im:
                im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((640,480));im.save(ROOT/'thumbnails'/thumb,quality=90)
            prev='Previously in the withdrawn nine-image list' if r['id'] in oldids else 'Not in the withdrawn nine-image list'
            parts.append(f'<article><a href="{html.escape(r["image_url"],quote=True)}"><img src="thumbnails/{thumb}"></a><p><a href="{html.escape(r["image_url"],quote=True)}">{html.escape(name)}</a> · <a href="{html.escape(r["folder_url"],quote=True)}">{html.escape(r["folder_path"].rsplit("/",1)[-1])}</a></p><small>{prev}</small></article>')
        parts.append('</section>')
    (ROOT/'all99-visible-content-review.html').write_text('\n'.join(parts))
    samples=[]
    for folder,num in [('Moonwave White',1),('Moonwave White',17),('Moonwave White',33),('Moonwave White In Situ',5)]:samples.append(next(r for r in rows if r['folder_path'].endswith('/'+folder) and int(r['name'].split('__')[-1].split('.')[0])==num))
    board=Image.new('RGB',(1600,1000),'#efefef');draw=ImageDraw.Draw(board);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',25)
    labels=['White 001.JPG: closer complete brick-wall view','White 017.JPG: wide brick-wall view','White 033.JPG: selected primary, complete mounted view','In Situ 005.JPG: selected furnished-room reference']
    for i,r in enumerate(samples):
        x=(i%2)*800;y=(i//2)*500
        with Image.open(r['local_path']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((780,425));board.paste(im,(x+(800-im.width)//2,y+(425-im.height)//2))
        draw.text((x+10,y+438),labels[i],fill='black',font=font)
    board.save(ROOT/'classification-boundary-four-example-images.jpg',quality=94);dump('four-example-image-and-folder-links.json',samples)
    proof={'status':'COMPLETE_CONTENT_REVIEW_AWAITING_OWNER_CRITERION','recorded_utc':NOW,'all99_fresh_native_hashes_match_actual_original_bytes':True,'all99_images_visually_reexamined_in_five_contact_boards':True,'counts_by_visible_content':counts,'initial_nine_proposal_status':'WITHDRAWN_OWNER_REJECTED_SELECTION','initial_nine_moves_applied':0,'new_move_proposal_created':False,'additional_full_brick_wall_views_outside_old_nine':58,'full_mounted_white_filename_ranges':['001-003','012-028','032-066','068-073','078-083'],'unchanged_selected_primary':'moonwave__moonwave-white__033.JPG','unchanged_selected_room_reference':'moonwave__moonwave-white-in-situ__005.JPG','full_mounted_set_contains_selected_primary':True,'future_selection_change_is_not_authorized':True,'native_mutations':0,'canonical_mutations':0,'outstanding_question':'Should complete mounted brick-wall views, including close framing, be In Situ or remain product/display references?','scope':'Moonwave only, inside /BOLDSTONE MASTER/Products/01 Wall Sculptures'}
    dump('review-status.json',proof);print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
