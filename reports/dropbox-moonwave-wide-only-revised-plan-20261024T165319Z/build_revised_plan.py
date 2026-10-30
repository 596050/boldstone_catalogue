import collections,datetime,hashlib,html,json,pathlib,re,urllib.parse
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=pathlib.Path(__file__).parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(n):return json.loads((ROOT/n).read_text())
def dump(n,x):(ROOT/n).write_text(json.dumps(x,indent=2)+'\n')
def fq(s):return re.sub(r'^ns:\d+/','',s)
def home(s):return 'https://www.dropbox.com/home'+urllib.parse.quote(s,safe='/')
def board(rows,name,title):
    cols=3;w=500;h=365;out=Image.new('RGB',(cols*w,65+h*((len(rows)+cols-1)//cols)),'#eeeeee');d=ImageDraw.Draw(out);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
    d.text((12,16),title,fill='black',font=font)
    for i,r in enumerate(rows):
        x=i%cols*w;y=65+i//cols*h
        with Image.open(r['local_path']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((485,290));out.paste(im,(x+(w-im.width)//2,y+(290-im.height)//2))
        d.text((x+10,y+300),r['name'].split('__')[-1],fill='black',font=font);d.text((x+10,y+328),r['folder_path'].rsplit('/',1)[-1],fill='black',font=font)
    out.save(ROOT/name,quality=93)
def main():
    native=read('fresh-native-before.json');es={e['file_id']:e for e in native['entries']};fresh={r['id']:r for r in read('fresh-native-content-hashes.json')};metadata={x[x['metadata_type']]['id']:x[x['metadata_type']] for x in read('fresh-file-folder-metadata.json')}
    rows=json.loads(pathlib.Path('reports/dropbox-moonwave-nine-in-situ-review-20261024T144130Z/all99-verified-current-originals.json').read_text());assert len(rows)==99 and len(es)==101
    for r in rows:
        e=es[r['id']];n=fresh[r['id']];assert r['path']==n['path']==e['path'] and n['size']==r['size']==e['file']['size']
        data=pathlib.Path(r['local_path']).read_bytes();sh=hashlib.sha256(data).hexdigest();dh=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest();assert sh==r['sha256'] and dh==n['content_hash']
        r.update(verified_utc=NOW,verification_method='ACTUAL_PRIOR_ORIGINAL_REHASHED_AGAINST_FRESH_NATIVE_HASH',native_action='NONE')
    assert sum(r['size'] for r in rows)==784220860
    byid={r['id']:r for r in rows};inputs=read('selected-evidence-originals.json');num=lambda r:int(r['name'].split('__')[-1].split('.')[0])
    forward=[byid[r['id']] for r in inputs['clear_setting_views']];held=[byid[r['id']] for r in inputs['borderline_hold']];reverse=[byid[r['id']] for r in inputs['close_views_return_to_White'] if num(r) in {3,4,11,12}];room=[byid[r['id']] for r in inputs['close_views_return_to_White'] if num(r) in {7,8,9,13}]
    assert [len(x) for x in [forward,reverse,held,room]]==[6,4,3,4]
    white=metadata['id:cnqzTNngPVsAAAAAAAyi-A'];insitu=metadata['id:cnqzTNngPVsAAAAAAAs6cw'];groups=[]
    for rr,dest,label,reason in [(forward,insitu,'White to In Situ','Clear wider brick-wall setting view; surrounding wall and garden context visible.'),(reverse,white,'In Situ to White','Closely framed brick-wall full-panel or detail view; excluded by the owner brick-wall criterion.')]:
        moves=[]
        for r in rr:
            m=metadata[r['id']];assert m['path_display']==fq(es[r['id']]['path'])
            assert not any(e['object_type']=='file' and fq(e['path']).rsplit('/',1)[0]==dest['path_display'] and e['name'].casefold()==r['name'].casefold() for e in es.values())
            moves.append({**r,'operation':'MOVE','source_path':es[r['id']]['path'],'source_folder_id':r['folder_id'],'destination_folder_id':dest['id'],'destination_path':dest['path_display']+'/'+r['name'],'destination_folder':dest['path_display'],'destination_folder_url':home(dest['path_display']),'destination_image_url':home(dest['path_display'])+'?preview='+urllib.parse.quote(r['name'],safe=''),'old_rev':m.get('rev'),'reason':reason})
        groups.append({'direction':label,'count':len(moves),'moves':moves})
    moves=[r for g in groups for r in g['moves']];ids={r['id'] for r in moves};assert len(ids)==10
    protected=read('protected-catalogue-references.json');o=protected['options'][0];assert o['file_id'] not in ids and o['context_file_id'] not in ids
    for k in ['file_id','context_file_id']:assert metadata[o[k]]['path_display']==fq(es[o[k]]['path'])
    counts=collections.Counter(fq(e['path']).rsplit('/',1)[0] for e in es.values() if e['object_type']=='file');assert counts[white['path_display']]==86 and counts[insitu['path_display']]==13
    plan={'schema':'boldstone.moonwave-revised-brick-wall-filing-proposal.v1','status':'PROPOSED_NOT_APPLIED','created_utc':NOW,'owner_criterion_verbatim':'brick-wall photographs should count as In Situ but not including close framing','owner_criterion_source':'owner-criterion-source-transcript-receipt.json','owner_criterion_is_not_exact_move_approval':True,'scope':'Moonwave brick-wall photographs only','original_nine_proposal_remains_withdrawn':True,'folders_to_create':[],'files_to_copy':[],'files_to_delete':[],'filename_changes':0,'expected_counts':{'White_before':86,'White_after':84,'InSitu_before':13,'InSitu_after':15,'family_originals':99,'family_bytes':784220860,'family_folders':2},'groups':groups,'moves':moves,'borderline_White_images_held_unchanged':[{'file_id':r['id'],'name':r['name'],'image_url':r['image_url'],'folder_url':r['folder_url'],'reason':'Borderline framing; held back conservatively from this immediate plan, not owner-classified as close.'} for r in held],'room_close_views_not_included_in_this_brick_wall_plan':[{'file_id':r['id'],'name':r['name'],'image_url':r['image_url'],'folder_url':r['folder_url'],'reason':'Owner statement specifically addresses brick-wall photographs; no broader room-detail reclassification inferred.'} for r in room],'selected_primary033_and_room_context005_IDs_and_roles_unchanged':True,'current_option_candidate_ID_occurrences':protected['current_candidate_ID_occurrences']['options'],'existing_source_offer_or_coverage_references_to_be_refreshed_by_own_file_ID_if_moves_later_approved':protected['current_candidate_ID_occurrences'],'no_filename_collisions':True,'native_mutations':0,'canonical_writes':0}
    dump('proposed-ten-moonwave-brick-wall-moves.json',plan);dump('all99-current-native-image-and-folder-links.json',rows)
    dump('all99-image-dispositions.json',[{'file_id':r['id'],'name':r['name'],'folder_id':r['folder_id'],'image_url':r['image_url'],'folder_url':r['folder_url'],'disposition':next((g['direction'] for g in groups if any(m['id']==r['id'] for m in g['moves'])),'BORDERLINE_KEEP_CURRENT' if r['id'] in {h['id'] for h in held} else 'KEEP_CURRENT'),'native_action_applied':False} for r in rows])
    board(forward,'six-clear-setting-views.jpg','Six clear setting views: proposed White to In Situ')
    board(reverse,'four-close-brick-wall-views.jpg','Four close brick-wall views: proposed In Situ to White')
    board(held,'three-borderline-views-kept.jpg','Three borderline White photographs: no proposed move')
    (ROOT/'previews').mkdir(exist_ok=True)
    text=['<!doctype html><meta charset="utf-8"><title>Moonwave: revised brick-wall filing proposal</title><style>body{font:17px system-ui;max-width:1300px;margin:25px}article{border-bottom:1px solid #bbb;padding:15px}article img{width:95%;max-width:1200px}p{line-height:1.5}.note{background:#fff0ce;padding:15px}</style><h1>Moonwave: revised brick-wall filing proposal</h1><p class="note">PROPOSED, NOT APPLIED. Owner criterion: brick-wall photographs count as In Situ, excluding close framing. Six clear setting views are proposed into In Situ; four closely framed brick-wall views currently in In Situ are proposed back to White. Three borderline views remain in White. The old nine-file plan stays withdrawn.</p><p>After both directions: White 86 → 84; In Situ 13 → 15. All 99 originals, filenames and both folders preserved. Selected primary White033.JPG and room context In Situ005.JPG remain unchanged.</p>']
    for label,rr in [('Proposed: White to In Situ',forward),('Proposed: In Situ to White',reverse),('Hold unchanged: borderline White photographs',held)]:
        text.append('<h2>'+html.escape(label)+'</h2>')
        for r in rr:
            imagepath=r['id'].replace('id:','')+'.jpg'
            with Image.open(r['local_path']) as im:
                im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1600,1200));im.save(ROOT/'previews'/imagepath,quality=93)
            m=next((m for m in moves if m['id']==r['id']),None);to=(f'<a href="{html.escape(m["destination_folder_url"],quote=True)}">Proposed destination folder</a>' if m else 'No move proposed')
            text.append(f'<article><h3>{html.escape(r["folder_path"].rsplit("/",1)[-1])} / {html.escape(r["name"].split("__")[-1])}</h3><a href="{html.escape(r["image_url"],quote=True)}"><img src="previews/{imagepath}"></a><p><a href="{html.escape(r["image_url"],quote=True)}">Current original image</a> · <a href="{html.escape(r["folder_url"],quote=True)}">Current containing folder</a> · {to}</p></article>')
    text.append('<p>Room close views007.JPG,008.JPG,009.JPG and013.jpeg are outside this brick-wall-only proposal; their current filing is retained.</p>')
    (ROOT/'review-ten-proposed-brick-wall-moves.html').write_text('\n'.join(text))
    (ROOT/'all99-current-image-folder-links.html').write_text('<!doctype html><meta charset="utf-8"><title>Moonwave:99 current image and folder links</title><h1>99 current Moonwave originals</h1><table>'+''.join(f'<tr><td><a href="{html.escape(r["image_url"],quote=True)}">{html.escape(r["name"])}</a></td><td><a href="{html.escape(r["folder_url"],quote=True)}">{html.escape(r["folder_path"].rsplit("/",1)[-1])}</a></td></tr>' for r in rows)+'</table>')
    dump('review-summary.json',{'status':'EXACT_TEN_MOVE_PROPOSAL_PENDING_OWNER_APPROVAL','recorded_utc':NOW,'owner_criterion_answered':True,'new_criterion_question_opened':False,'all99_actual_originals_verified_against_fresh_native_hashes':True,'all99_contact_sheet_views_reexamined':True,'three_previous_candidates_viewed_individually':True,'two_current_close_views_also_viewed_individually':True,'forward_moves_proposed':6,'reverse_moves_proposed':4,'borderline_views_held':3,'room_close_views_no_change':4,'selected_primary_and_context_unchanged':True,'native_writes':0,'canonical_writes':0,'no_source_or_physical_specification_changes':True,'expected_counts':plan['expected_counts']})
    print(json.dumps({'status':plan['status'],'forward':6,'reverse':4,'borderline_held':3,'room_views_unchanged':4,'expected_counts':plan['expected_counts'],'current_reference_hits':{k:len(v) for k,v in protected['current_candidate_ID_occurrences'].items()},'proposal_sha256':hashlib.sha256((ROOT/'proposed-ten-moonwave-brick-wall-moves.json').read_bytes()).hexdigest()},indent=2))
if __name__=='__main__':main()
