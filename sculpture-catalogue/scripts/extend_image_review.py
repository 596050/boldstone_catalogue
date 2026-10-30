import concurrent.futures as cf
import hashlib,json,math,pickle,urllib.request
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw

project=Path(__file__).resolve().parents[1];ev=project/'evidence'
source=json.loads((ev/'catalogue_source_tables_2026-10-15.json').read_text())
inv=json.loads((ev/'wall_inventory_2026-10-16.json').read_text())
current={r['file_id']:r for r in inv['entries'] if r['object_type']=='file'}
cache=json.loads((ev/'image_review_cache_index.json').read_text())
media=Path('/Users/tprice/Library/Application Support/BoldstoneCatalogue/media');media.mkdir(parents=True,exist_ok=True)
refs=[]
for p in source['Matched Overview']:
    for r in source['Image Reference Links']:
        if r['Squarespace product ID']==p['Squarespace product ID']:
            refs.append(dict(pid=r['Squarespace product ID'],title=r['Title'],order=int(r['Image order in export']),url=r['Source URL'],families=[x.strip() for x in p['Dropbox family / families'].split(';')],local_path=str(media/(r['Squarespace product ID']+'-'+r['Image order in export']+'.image'))))
def download(r):
    try:
        p=Path(r['local_path'])
        if not p.exists():
            with urllib.request.urlopen(urllib.request.Request(r['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as response:p.write_bytes(response.read())
        with Image.open(p) as im:r['size']=list(im.size)
        r['ok']=True
    except Exception as exc:r.update(ok=False,error=str(exc))
    return r
with cf.ThreadPoolExecutor(max_workers=8) as pool:refs=list(pool.map(download,refs))
(ev/'established_offer_image_index.json').write_text(json.dumps(refs,ensure_ascii=False))

def feature(r):
    try:
        with Image.open(r['local_path']) as src:
            src.draft('RGB',(100,100));im=ImageOps.exif_transpose(src).convert('RGB');ratio=im.width/im.height
            px=list(im.convert('L').resize((17,16),Image.Resampling.LANCZOS).getdata());dh=0
            for y in range(16):
                for x in range(16):dh=(dh<<1)|int(px[y*17+x]>px[y*17+x+1])
            small=im.resize((32,32),Image.Resampling.LANCZOS).tobytes()
        return dict(record=r,dhash=dh,small=small,ratio=ratio)
    except Exception:return None
feature_file=ev/'current_cache_image_features.pickle'
if feature_file.exists():db=pickle.loads(feature_file.read_bytes())
else:
    selected=[{**r,**dict(id=fid,path=current[fid]['path'],name=current[fid]['name'],family=current[fid]['path'].split('01 Wall Sculptures/',1)[-1].split('/')[0])} for fid,r in cache.items() if fid in current and Path(r['local_path']).is_file()]
    with cf.ThreadPoolExecutor(max_workers=6) as pool:db=[x for x in pool.map(feature,selected) if x]
    feature_file.write_bytes(pickle.dumps(db))
print(json.dumps(dict(cache_features=len(db),source_images=len(refs),downloaded=sum(r['ok'] for r in refs))),flush=True)
with cf.ThreadPoolExecutor(max_workers=6) as pool:ref_features=[x for x in pool.map(feature,[r for r in refs if r['ok']]) if x]
results=[]
for f in ref_features:
    ranked=sorted(db,key=lambda c:(f['dhash']^c['dhash']).bit_count())[:25]
    candidates=[]
    for c in ranked:
        rms=(sum((a-b)**2 for a,b in zip(f['small'],c['small']))/len(f['small']))**.5
        candidates.append(dict(id=c['record']['id'],family=c['record']['family'],path=c['record']['path'],name=c['record']['name'],local_path=c['record']['local_path'],dhash=(f['dhash']^c['dhash']).bit_count(),rmse=round(rms,3),ratio_error=round(abs(math.log(f['ratio']/c['ratio'])),5)))
    candidates.sort(key=lambda c:c['rmse']+c['dhash']*.2+c['ratio_error']*10)
    results.append({**f['record'], 'matches':candidates[:5]})
(ev/'established_offer_image_matches.json').write_text(json.dumps(results,ensure_ascii=False))
summary=[]
for p in source['Matched Overview']:
    rr=[r for r in results if r['pid']==p['Squarespace product ID']]
    expected={x.casefold() for x in rr[0]['families']}
    same_family=[r for r in rr if r['matches'][0]['rmse']<2 and r['matches'][0]['family'].casefold() in expected]
    best=min(same_family,key=lambda r:r['order']) if same_family else min(rr,key=lambda r:r['matches'][0]['rmse'])
    summary.append(dict(pid=best['pid'],title=best['title'],image_order=best['order'],image_path=best['local_path'],candidate=best['matches'][0],expected_families=best['families']))
(ev/'established_offer_image_summary.json').write_text(json.dumps(summary,ensure_ascii=False))
for start in range(0,len(summary),8):
    chunk=summary[start:start+8];board=Image.new('RGB',(1100,len(chunk)*245),'white');draw=ImageDraw.Draw(board)
    for i,r in enumerate(chunk):
        for j,p in enumerate([r['image_path'],r['candidate']['local_path']]):
            with Image.open(p) as src:
                im=ImageOps.contain(ImageOps.exif_transpose(src).convert('RGB'),(530,182));board.paste(im,(j*550+(550-im.width)//2,i*245))
        draw.multiline_text((8,i*245+184),r['title']+'\nSS image '+str(r['image_order']),fill='black',spacing=3)
        c=r['candidate'];draw.multiline_text((558,i*245+184),f'{c["family"]} | RMS {c["rmse"]} | dh {c["dhash"]}\n{c["path"].split("/")[-2]}\n{c["id"]}',fill='black',spacing=3)
    board.save(project/'reviews'/f'established-comparison-{start//8+1}.jpg',quality=90)
for r in summary:print(r['title'],'=>',r['candidate']['family'],r['candidate']['rmse'],r['candidate']['dhash'],r['candidate']['id'],flush=True)
