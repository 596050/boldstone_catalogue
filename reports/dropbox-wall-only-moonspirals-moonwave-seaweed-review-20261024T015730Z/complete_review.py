import collections,datetime,hashlib,html,json,pathlib,urllib.parse
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=pathlib.Path(__file__).parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(n,d):(ROOT/n).write_text(json.dumps(d,indent=2)+'\n')
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def home(p):return 'https://www.dropbox.com/home'+urllib.parse.quote(p,safe='/')
def main():
    rows=json.loads((ROOT/'verified-original-downloads.json').read_text());byid={r['id']:r for r in rows}
    listing=json.loads((ROOT/'fresh-complete-native-listings.json').read_text())
    mp=[r for r in rows if r['review_index'] in [126,127,128]]
    dest='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moonspirals/Moonspiral 1 and Moonspiral 2 White In Situ'
    dest_id='id:cnqzTNngPVsAAAAAAAyi8w'
    target_names={e['name'].casefold() for f in listing['listings'] for e in f['result']['entries'] if e['object_type']=='file' and e['path'].rsplit('/',1)[0].endswith(dest)}
    for r in mp:assert r['name'].casefold() not in target_names
    protected=json.loads((ROOT/'selected-catalogue-references-before-readonly-review.json').read_text())
    mids={r['id'] for r in mp}
    assert all(o.get(k) not in mids for o in protected['options'] for k in ['file_id','context_file_id'])
    plan={'schema':'boldstone.moonspirals-three-pair-filing-proposal.v1','status':'PROPOSED_NOT_APPLIED','created_utc':NOW,'operation':'MOVE','source_folder':mp[0]['folder_path'],'source_folder_id':mp[0]['folder_id'],'destination_folder':dest,'destination_folder_id':dest_id,'destination_folder_url':home(dest),'folders_to_create':[],'copies':0,'deletes':0,'filename_changes':0,'source_count_before':22,'source_count_after':19,'destination_count_before':28,'destination_count_after':31,'family_images_preserved':148,'family_bytes_preserved':416784106,'family_folders_preserved':9,'all_selected_individual_primaries_and_selected_context_unchanged':True,'collision_check':'NO_EXISTING_DESTINATION_FILENAME_COLLISIONS','basis':'All three images show Moonspiral 2 on the left and an identifiable Moonspiral 1 on the right. The right panel is partly outside the frame. Existing pair folder has equivalent two-component views. No new design or physical cast is inferred.','moves':[{**r,'source_path':r['path'],'destination_path':dest+'/'+r['name'],'destination_image_url':home(dest)+'?preview='+urllib.parse.quote(r['name'],safe=''),'operation':'MOVE'} for r in mp]}
    dump('proposed-three-moonspirals-pair-moves.json',plan)
    wide={17,18,23,40,41,62,79,82,83}
    candidates=[r for r in rows if r['family']=='Moonwave' and r['folder_path'].endswith('/Moonwave White') and int(r['name'].split('__')[-1].split('.')[0]) in wide]
    assert len(candidates)==9
    # These are observations for the next item, not an approved native move plan.
    dump('moonwave-nine-wide-wall-view-observations.json',{'status':'READ_ONLY_NEXT_ITEM_OBSERVATIONS_NOT_APPLIED','basis':'Wide mounted views include substantial brick-wall or garden setting; same design appears in different orientations. No extra component identity is inferred.','candidates':candidates,'all_other77_White_images_retained_in_this_review':True})
    uncertain=[r for r in rows if r['review_index'] in [314,315]]
    dump('seaweed-two-unfinished-setting-observations.json',{'status':'PROVENANCE_UNRESOLVED_KEEP_CURRENT_FILING','reason':'003.JPG and 004.jpg show a tall multi-panel relief in an unfinished setting. Photo alone does not settle workshop display versus installation in progress; no new folder or move is proposed. No new photo request is opened.','images':uncertain})
    decisions=[]
    for r in rows:
        if r['id'] in mids:status='PROPOSED_EXISTING_PAIR_FOLDER_MOVE';note='Moonspiral 2 left and Moonspiral 1 right, partly cropped; pending exact owner confirmation.'
        elif r in candidates:status='NEXT_ITEM_WIDE_WALL_VIEW_OBSERVATION';note='Wide mounted brick-wall view; retain current path until reviewed as next item.'
        elif r in uncertain:status='KEEP_PROVENANCE_UNRESOLVED';note='Unfinished setting does not prove workshop provenance.'
        else:status='KEEP_CURRENT_FILING';note='No sufficiently clear component/family misfiling identified in this image. Cropped neighboring edges do not by themselves require an arrangement reclassification. Product photographs can include a backdrop; orientation and lighting do not establish a different design or finish.'
        decisions.append({'file_id':r['id'],'review_index':r['review_index'],'family':r['family'],'name':r['name'],'image_url':r['image_url'],'folder_url':r['folder_url'],'status':status,'note':note})
    dump('all337-image-filing-decisions.json',decisions)
    boards=json.loads((ROOT/'contact-board-index.json').read_text());dump('contact-sheet-visual-review.json',{'reviewed_utc':NOW,'boards_reviewed':boards,'all337_checked':True,'candidate_pair_originals_also_viewed_individually':[r['id'] for r in mp],'orientation':'EXIF_TRANSPOSED_DERIVATIVES_ONLY; originals unchanged'})
    parts=['<!doctype html><meta charset="utf-8"><title>Three Moonspirals pair moves - proposal</title><style>body{font:17px system-ui;max-width:1200px;margin:25px}img{width:95%;max-width:1100px}article{border-bottom:1px solid #ccc;margin:25px 0;padding:15px}</style><h1>Proposed: three Moonspirals pair photographs</h1><p>Not applied. Move 012.JPG, 013.JPG and 014.JPG from Moonspiral 2 White In Situ into the existing Moonspiral 1 and Moonspiral 2 White In Situ folder. No folder creation, copies, deletes or filename changes.</p><p>Source 22 → 19; destination 28 → 31. Family remains 148 originals in nine folders.</p>']
    for r in mp:
        preview=ROOT/f'proposal-{r["review_index"]:03d}.jpg'
        with Image.open(r['local_path']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1500,1100));im.save(preview,quality=92)
        parts.append(f'<article><h2>{html.escape(r["name"])}</h2><a href="{html.escape(r["image_url"],quote=True)}"><img src="{preview.name}"></a><p><a href="{html.escape(r["image_url"],quote=True)}">Current photograph</a> · <a href="{html.escape(r["folder_url"],quote=True)}">Current containing folder</a> · <a href="{html.escape(home(dest),quote=True)}">Proposed existing destination folder</a></p></article>')
    (ROOT/'review-three-proposed-moonspirals-pair-moves.html').write_text('\n'.join(parts))
    prior=json.loads(pathlib.Path('reports/dropbox-wave-moonshadow-mixed-scene-moves-20261024T014335Z/combined-twenty-seven-family-current-image-links-after-mixed-scene.json').read_text())
    newids=set(byid);combined=[r for r in prior if r['file_id'] not in newids]
    for r in rows:combined.append({'role':'source','family':r['family'],'file_id':r['id'],'name':r['name'],'size':r['size'],'folder_id':r['folder_id'],'folder_path':r['folder_path'],'folder_url':r['folder_url'],'image_url':r['image_url'],'sha256':r['sha256'],'dropbox_content_hash':r['dropbox_content_hash']})
    assert len({r['file_id'] for r in combined})==len(combined)==1094
    assert sum(r['role']=='source' for r in combined)==1084
    assert sum(r['role']!='source' for r in combined)==10
    dump('combined-thirty-family-image-folder-links.json',combined)
    acct={'whole_source_families':len({r['family'] for r in combined if r['role']=='source'}),'whole_family_source_originals':1084,'comparison_only_originals':10,'distinct_originals':1094,'total_distinct_bytes':sum(r['size'] for r in combined),'prior_Moonspiral1_and2_comparison_originals_now_promoted_to_whole_family_source_role':2,'historical_other_family_paths':'Captured evidence dates retained; not all freshly queried this turn. Prior completed Riyadh, Battersea, Spiralmoon and Wave/Moonshadow path overlays retained.','physical_sculpture_or_stock_count_inferred':False}
    assert acct['whole_source_families']==30;dump('cumulative-link-accounting.json',acct)
    (ROOT/'combined-thirty-family-image-folder-links.html').write_text('<!doctype html><meta charset="utf-8"><title>30-family image and folder links</title><h1>1,094 distinct original references</h1><p>1,084 source originals across 30 whole source families, plus 10 comparison-only originals. Other families retain their dated readbacks.</p><table><tr><th>Role</th><th>Family</th><th>Image</th><th>Containing folder</th></tr>'+''.join(f'<tr><td>{html.escape(r["role"])}</td><td>{html.escape(r["family"])}</td><td><a href="{html.escape(r["image_url"],quote=True)}">{html.escape(r["name"])}</a></td><td><a href="{html.escape(r["folder_url"],quote=True)}">{html.escape(r["folder_path"].rsplit("/",1)[-1])}</a></td></tr>' for r in sorted(combined,key=lambda r:(r['family'],r['folder_path'],r['name'])))+'</table>')
    summary={'schema':'boldstone.three-family-native-readonly-review.v1','status':'COMPLETE_READ_ONLY_REVIEW_WITH_ONE_EXACT_PENDING_PROPOSAL','recorded_utc':NOW,'originals_checked':337,'bytes_checked':1673453384,'fresh_original_HTTP_downloads':333,'prior_identical_originals_rehashed_against_fresh_native_hashes':4,'complete_families':3,'photo_folders':15,'all18_contact_boards_reviewed':True,'decisions':dict(collections.Counter(r['status'] for r in decisions)),'pending_owner_approval':'Only the three Moonspirals pair moves are drafted as an exact move proposal. Moonwave nine wide-context observations remain the next review item; Seaweed two unfinished-setting views retain current filing.','native_writes':0,'canonical_writes':0,'outside_Wall_Sculptures_native_queries':0,'new_missing_photo_questions':0,'exact_LeafFormrqDQ_hold_respected':True,'water_features_retained':True,'cumulative':acct}
    dump('review-summary.json',summary)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
