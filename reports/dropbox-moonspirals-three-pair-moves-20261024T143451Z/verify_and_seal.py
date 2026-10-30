import collections,datetime,hashlib,html,json,pathlib,re,urllib.parse
ROOT=pathlib.Path(__file__).parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
SCOPE='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moonspirals'
def read(n):return json.loads((ROOT/n).read_text())
def dump(n,x):(ROOT/n).write_text(json.dumps(x,indent=2)+'\n')
def fq(s):return re.sub(r'^ns:\d+/','',s)
def home(s):return 'https://www.dropbox.com/home'+urllib.parse.quote(s,safe='/')
def hashes(data):return hashlib.sha256(data).hexdigest(),hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()
def main():
    pre=read('fresh-native-before.json');post=read('fresh-native-after.json');plan=read('approved-plan-and-guards.json');prior={r['id']:r for r in read('original-prewrite-hashes.json')};fresh={r['id']:r for r in read('fresh-postmove-native-hash-metadata.json')};new={r['id']:r for r in read('three-fresh-postmove-originals.json')}
    old={r['file_id']:r for r in pre['listing']['entries']};cur={r['file_id']:r for r in post['listing']['entries']};assert len(old)==len(cur)==157 and set(old)==set(cur)
    mids={m['id'] for m in plan['moves']};assert len(mids)==3 and set(new)==mids
    folders={fq(r['path']):r['file_id'] for r in cur.values() if r['object_type']=='folder'};folders[SCOPE]=pre['family']['folder']['id']
    oldfolders={fq(r['path']):r['file_id'] for r in old.values() if r['object_type']=='folder'};oldfolders[SCOPE]=pre['family']['folder']['id']
    rows=[];objects=[]
    before_meta={r['file']['id']:r['file'] for r in pre['files']};after_meta={r['file']['id']:r['file'] for r in post['files']}
    for fileid,c in cur.items():
        b=old[fileid];assert c['name']==b['name'] and c['object_type']==b['object_type']
        isfile=c['object_type']=='file';newpath=fq(c['path']);oldpath=fq(b['path']);cp=folders[newpath.rsplit('/',1)[0]];bp=oldfolders[oldpath.rsplit('/',1)[0]]
        if fileid in mids:
            m=next(m for m in plan['moves'] if m['id']==fileid);assert newpath==m['destination_path'] and oldpath==fq(m['source_path']);assert cp==plan['destination_folder_id'] and bp==plan['source_folder_id']
        else:assert c==b
        obj={'file_id':fileid,'object_type':c['object_type'],'old_name':b['name'],'current_name':c['name'],'old_path':oldpath,'current_path':newpath,'current_ns_path':c['path'],'old_parent_id':bp,'current_parent_id':cp,'size':c.get('file',{}).get('size',0),'old_client_modified':b.get('client_modified'),'current_client_modified':c.get('client_modified'),'old_server_modified':b.get('modified_time'),'current_server_modified':c.get('modified_time'),'current_native_url':home(newpath) if not isfile else home(newpath.rsplit('/',1)[0])+'?preview='+urllib.parse.quote(c['name'],safe=''),'status':'success'}
        if isfile:
            assert c['file']['size']==b['file']['size'] and c.get('client_modified')==b.get('client_modified')
            n=fresh[fileid];assert n['path']==c['path'] and n['size']==c['file']['size'] and n['name']==c['name']
            source=new.get(fileid,prior[fileid]);q=pathlib.Path(source['local_path']);data=q.read_bytes();sh,dh=hashes(data)
            assert sh==prior[fileid]['sha256'] and dh==fresh[fileid]['content_hash'] and len(data)==c['file']['size']
            r={**{k:v for k,v in n.items() if k!='download_url'},'family':'Moonspirals','local_path':str(q),'sha256':sh,'dropbox_content_hash':dh,'folder_id':cp,'folder_path':newpath.rsplit('/',1)[0],'folder_url':home(newpath.rsplit('/',1)[0]),'image_url':obj['current_native_url'],'verification_method':'FRESH_POSTMOVE_ORIGINAL_DOWNLOAD' if fileid in mids else 'PRIOR_VERIFIED_ORIGINAL_ACTUAL_BYTES_REHASHED_AGAINST_FRESH_NATIVE_HASH','verified_utc':NOW}
            rows.append(r);obj.update(sha256=sh,dropbox_content_hash=dh,pre_move_sha256_identical=True,original_verification_method=r['verification_method'])
            if fileid in mids:
                bm=before_meta[fileid];am=after_meta[fileid];assert bm['id']==am['id'] and bm['name']==am['name'] and bm['size']==am['size'] and bm.get('client_modified')==am.get('client_modified')
                obj.update(old_rev=bm.get('rev'),current_rev=am.get('rev'))
        objects.append(obj)
    assert len(rows)==148 and sum(r['size'] for r in rows)==416784106
    counts=collections.Counter(r['folder_path'] for r in rows);assert counts[plan['source_folder']]==19 and counts[plan['destination_folder']]==31
    protected=read('protected-catalogue-references-before.json')
    for o in protected['moonspirals_options']:
        for key in ['file_id','context_file_id']:
            fid=o.get(key)
            if fid:assert fid not in mids and cur[fid]==old[fid]
    dump('verified-current-originals.json',rows)
    validation={'schema':'boldstone.moonspirals-three-pair-moves-validation.v1','status':'COMPLETE_VERIFIED','verified_utc':NOW,'approved_moves_completed':3,'family_originals':148,'family_bytes':416784106,'family_folders':9,'source_before':22,'source_after':19,'destination_before':28,'destination_after':31,'all148_original_ID_name_format_size_client_time_and_bytes_preserved':True,'only_three_approved_file_paths_and_parent_IDs_changed':True,'fresh_postmove_original_downloads':3,'unchanged145_originals_rehashed_against_fresh_native_hashes':True,'current_selected_primaries_and_context_IDs_and_paths_unchanged':True,'current_option_offer_coverage_occurrences_using_moved_IDs':protected['current_moved_ID_reference_occurrences'],'created_folders':0,'renames':0,'copies':0,'deletes':0,'outside_wall_sculpture_native_queries':0,'canonical_writes_by_this_lane':0}
    dump('validation.json',validation)
    maps=[{'file_id':o['file_id'],'old_path':o['old_path'],'new_path':o['current_path'],'old_parent_id':o['old_parent_id'],'new_parent_id':o['current_parent_id'],'old_rev':o.get('old_rev'),'new_rev':o.get('current_rev'),'sha256':o['sha256'],'dropbox_content_hash':o['dropbox_content_hash'],'size':o['size']} for o in objects if o['file_id'] in mids]
    overlay={'schema':'boldstone.current-native-reference-overlay.v1','status':'COMPLETE_VERIFIED','recorded_utc':NOW,'source_scope':SCOPE,'owner_authorization':'Direct current user okay quoting exact three Moonspirals move table; see owner-authority.json','preserved_scope_roots':[pre['family']['folder']],'prefix_maps':[],'specific_file_maps':maps,'specific_file_maps_override_prefix_maps':True,'created_folders':[],'deleted_files':[],'deleted_folders':[],'objects':objects,'summary':{'files':148,'folders':9,'bytes':416784106,'moved_file_paths':3,'moved_actual_parents':3,'created_folders':0,'folder_renames':0,'all_original_bytes_preserved':True},'verification':validation,'current_folders':[{'folder_id':fid,'folder_path':path,'folder_url':home(path),'files':counts[path]} for path,fid in folders.items() if path!=SCOPE],'catalogue_projection':{'selected_Moonspirals_individual_primaries_and_contexts_unchanged':True,'current_option_offer_coverage_moved_ID_occurrences':protected['current_moved_ID_reference_occurrences']},'review_proposal_sha256':plan['proposal_sha256'],'master_writes_by_this_lane':0}
    dump('current-reference-overlay.json',overlay)
    links=[{'role':'source','family':'Moonspirals','file_id':r['id'],'name':r['name'],'size':r['size'],'folder_id':r['folder_id'],'folder_path':r['folder_path'],'folder_url':r['folder_url'],'image_url':r['image_url'],'sha256':r['sha256'],'dropbox_content_hash':r['dropbox_content_hash']} for r in rows];links.sort(key=lambda r:(r['folder_path'],r['name']))
    dump('all-current-moonspirals-image-folder-links.json',links)
    (ROOT/'all-current-moonspirals-image-folder-links.tsv').write_text('filename\timage_url\tfolder_url\n'+''.join(f'{r["name"]}\t{r["image_url"]}\t{r["folder_url"]}\n' for r in links))
    (ROOT/'all-current-moonspirals-image-folder-links.html').write_text('<!doctype html><meta charset="utf-8"><title>148 current Moonspirals image and folder links</title><style>body{font:16px system-ui;margin:20px}td{padding:9px;border-bottom:1px solid #ccc}</style><h1>148 current Moonspirals image and folder links</h1><p>Three approved moves complete. Original bytes verified; 3 fresh postmove downloads plus 145 actual prior originals rehashed against fresh native content hashes.</p><table><tr><th>Image</th><th>Containing folder</th></tr>'+''.join(f'<tr><td><a href="{html.escape(r["image_url"],quote=True)}">{html.escape(r["name"])}</a></td><td><a href="{html.escape(r["folder_url"],quote=True)}">{html.escape(r["folder_path"].rsplit("/",1)[-1])}</a></td></tr>' for r in links)+'</table>')
    prev=pathlib.Path('/Users/tprice/Documents/boldstone/reports/dropbox-wall-only-moonspirals-moonwave-seaweed-review-20261024T015730Z/combined-thirty-family-image-folder-links.json');combo=json.loads(prev.read_text());replaced={r['file_id']:r for r in links};combo=[replaced.get(r['file_id'],r) for r in combo];assert len(combo)==1094
    dump('combined-thirty-family-current-image-folder-links.json',combo)
    dump('reversion-plan-not-executed.json',{'status':'NOT_EXECUTED','operation':'MOVE_BACK','entries':[{'source_path':m['id'],'destination_path':fq(m['source_path'])} for m in plan['moves']],'expected_source_count_after_reversion':22,'expected_pair_count_after_reversion':28,'folders_to_remove':[]})
    lines=['MOONSPIRALS THREE PAIR MOVES - COMPLETE VERIFIED','Source Moonspiral 2 White In Situ:22 ->19','Existing Moonspiral 1 and Moonspiral 2 White In Situ:28 ->31','Family148 originals /416784106 bytes /9folders preserved','']
    for r in links:
        if r['file_id'] in mids:lines.extend([r['name'],r['image_url'],'FOLDER '+r['folder_url'],''])
    (ROOT/'terminal-final-structure-and-moved-links.txt').write_text('\n'.join(lines)+'\n')
    dump('catalogue-publication-followup.json',{'native_status':'COMPLETE_VERIFIED','catalogue_status':'SEALED_HANDOFF_PENDING','native_claim_released':False,'shared_master_writes_by_this_lane':0,'recorded_utc':NOW})
    excluded=['execution-seal.json','batch-coordination.json','catalogue-publication-followup.json']
    core=[p for p in ROOT.iterdir() if p.is_file() and p.name not in excluded]
    receipts=[{'path':str(p),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(core)]
    seal={'schema':'boldstone.native-execution-seal.v1','status':'COMPLETE_VERIFIED','created_utc':NOW,'approved_proposal_sha256':plan['proposal_sha256'],'receipts':receipts,'verified_post_move_originals':[{k:r[k] for k in ['id','local_path','size','sha256','dropbox_content_hash','verification_method']} for r in rows],'mutable_followup_files_excluded_from_seal':excluded[1:],'native_moves':3,'master_writes':0}
    dump('execution-seal.json',seal)
    print(json.dumps({'status':'COMPLETE_VERIFIED','files':148,'folders':9,'bytes':416784106,'moves':3,'source':19,'destination':31,'receipts':len(receipts),'overlay_sha256':hashlib.sha256((ROOT/'current-reference-overlay.json').read_bytes()).hexdigest(),'seal_sha256':hashlib.sha256((ROOT/'execution-seal.json').read_bytes()).hexdigest()},indent=2))
if __name__=='__main__':main()
