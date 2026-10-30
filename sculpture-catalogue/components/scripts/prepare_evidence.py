import hashlib,json,math,pickle
from collections import defaultdict,Counter
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw

project=Path(__file__).resolve().parents[1];ev=project/'evidence';reviews=project/'reviews'
audit=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency')
identity=audit/'identity-resolution-20261016T120156Z';product=audit/'product-evidence-resolution-20261016T201618Z'
inventory=json.loads((ev/'current_inventory.json').read_text());root=inventory['root_path']+'/'
heads=json.loads(Path('/Users/tprice/BoldstoneMigration/path-realignment-20261016/CURRENT-FILE-PATHS.json').read_text())['files'];heads={r['id']:r for r in heads}
current={r['file_id']:r for r in inventory['entries']}
assert {fid for fid,r in current.items() if r['object_type']=='file'}==set(heads)
folders=sorted([r for r in inventory['entries'] if r['object_type']=='folder' and r['path'][len(root):].count('/')==1],key=lambda r:r['path'].casefold())
folder_by_path={r['path'].casefold():r for r in folders}
files_by_group=defaultdict(list)
assets=[];missing=[]
cases=json.loads((identity/'Final_Identity_Register.json').read_text())['cases'];case_by_folder={r['stable_folder_id']:r for r in cases}
source_decisions=json.loads((product/'Case_Evidence_Decisions.json').read_text())['cases'];source_by_case={r['case_number']:r for r in source_decisions}
origin=json.loads((product/'Product_Evidence_Asset_Register_Final.json').read_text())['assets'];origin={r['id']:r for r in origin}
cache=json.loads((project.parent/'evidence/image_review_cache_index.json').read_text())
for fid,head in heads.items():
    r=current[fid];parent=folder_by_path[r['path'].rsplit('/',1)[0].casefold()]
    assert r.get('file',{}).get('size',0)==head['size']
    thumb=audit/'review-20261015T223009Z/thumbnails'/(head['content_hash']+'.jpg')
    receipt=audit/'review-20261015T223009Z/local-asset-receipts'/(head['content_hash']+'.json')
    full=''
    if receipt.exists():full=json.loads(receipt.read_text()).get('source_cache_path','')
    if not full and fid in cache:full=cache[fid].get('local_path','')
    if not thumb.exists() and full and Path(full).exists():
        thumb=reviews/(fid[3:]+'.jpg')
        with Image.open(full) as im:ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'),(640,640)).save(thumb,quality=90)
    asset=dict(id=fid,folder_id=parent['file_id'],name=r['name'],path=r['path'],family=r['path'][len(root):].split('/')[0],group=parent['name'],content_hash=head['content_hash'],bytes=head['size'],thumb=str(thumb) if thumb.exists() else '',full=full,origin_evidence=origin.get(fid,{}))
    assets.append(asset);files_by_group[parent['file_id']].append(asset)
    if not thumb.exists():missing.append(fid)
def feature(asset):
    if not asset['thumb']:return None
    with Image.open(asset['thumb']) as im:
        im=im.convert('RGB');ratio=im.width/im.height
        gray=list(im.convert('L').resize((9,8)).getdata());dh=0
        for y in range(8):
            for x in range(8):dh=(dh<<1)|int(gray[y*9+x]>gray[y*9+x+1])
        color=tuple(round(sum(p[c] for p in im.resize((8,8)).getdata())/64) for c in range(3))
    return dh,color,ratio
features={a['id']:feature(a) for a in assets if a['thumb']}
def distance(a,b):
    fa=features[a['id']];fb=features[b['id']]
    return (fa[0]^fb[0]).bit_count()+sum(abs(x-y) for x,y in zip(fa[1],fb[1]))/30+abs(math.log(fa[2]/fb[2]))*5
known=[]
for name in ['image_review_curated_review.json','established_image_decisions.json']:
    for r in json.loads((project.parent/'evidence'/name).read_text()):
        fid=r.get('asset_id') or (r.get('source') or {}).get('id')
        if fid:known.append(fid)
groups=[]
for n,folder in enumerate(folders,1):
    aa=sorted(files_by_group[folder['file_id']],key=lambda r:r['name'].casefold());available=[a for a in aa if a['thumb']]
    picks=[]
    if available:
        first=next((a for a in available if a['id'] in known),available[0]);picks=[first]
        if len(available)>1:
            second=max(available,key=lambda a:distance(a,first))
            if second['id']!=first['id']:picks.append(second)
    case=case_by_folder.get(folder['file_id']);case_num=case['case_number'] if case else None
    groups.append(dict(group_ref=f'G{n:03d}',id=folder['file_id'],name=folder['name'],family=folder['path'][len(root):].split('/')[0],path=folder['path'],files=len(aa),selected=[a['id'] for a in picks],case_number=case_num,earlier_full_group_review=bool(case),earlier_observations=case.get('observations','') if case else '',source_decision=source_by_case.get(case_num,{})))
by_id={a['id']:a for a in assets}
for start in range(0,len(groups),16):
    chunk=groups[start:start+16];board=Image.new('RGB',(1640,((len(chunk)+3)//4)*278),'white');draw=ImageDraw.Draw(board)
    for i,g in enumerate(chunk):
        x=(i%4)*410;y=(i//4)*278
        for j,fid in enumerate(g['selected']):
            with Image.open(by_id[fid]['thumb']) as src:
                im=ImageOps.contain(src.convert('RGB'),(198,194));board.paste(im,(x+j*205+(205-im.width)//2,y))
        label=g['group_ref']+' '+g['family']+'\n'+g['name']+'\n'+str(g['files'])+' files'+(' | prior full review '+str(g['case_number']) if g['case_number'] else '')
        draw.multiline_text((x+4,y+198),label,fill='black',spacing=3)
    board.save(reviews/f'groups-{start//16+1:02d}.jpg',quality=94)
refs=json.loads((product/'Manufacturing_Labelled_References.json').read_text())
for start in range(0,len(refs),16):
    chunk=refs[start:start+16];board=Image.new('RGB',(1400,((len(chunk)+3)//4)*245),'white');draw=ImageDraw.Draw(board)
    for i,r in enumerate(chunk):
        x=i%4*350;y=i//4*245
        with Image.open(r['picture']['path']) as src:
            im=ImageOps.contain(src.convert('RGB'),(335,180));board.paste(im,(x+(350-im.width)//2,y))
        draw.multiline_text((x+4,y+183),r['code'].strip()+' | row '+str(r['row'])+'\n'+r['name'],fill='black',spacing=3)
    board.save(reviews/f'manufacturing-{start//16+1:02d}.jpg',quality=94)
model=dict(inventory_finished_utc=inventory['finished_utc'],groups=groups,assets=assets,manufacturing_refs=refs,manufacturing_rows=json.loads((product/'Manufacturing_Sheet_Extract.json').read_text()),document_sources=json.loads((product/'Evidence_Source_Catalogue_Final.json').read_text())['documents'],missing_previews=missing,coverage=dict(families=63,groups=len(groups),files=len(assets),preview_files=len(assets)-len(missing),previously_full_reviewed_groups=sum(g['earlier_full_group_review'] for g in groups),previously_full_reviewed_files=sum(g['files'] for g in groups if g['earlier_full_group_review'])))
(ev/'evidence_index.json').write_text(json.dumps(model,ensure_ascii=False))
print(json.dumps(dict(coverage=model['coverage'],missing_previews=missing,group_boards=(len(groups)+15)//16,manufacturing_boards=(len(refs)+15)//16)))
