import concurrent.futures, hashlib, html, json, re, urllib.request
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

root=Path(__file__).resolve().parents[1]; ev=root/'evidence'; out=root/'reviews'
source=json.loads((root.parent/'evidence/catalogue_source_tables_2026-10-15.json').read_text())
product=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
cache={}
for r in json.loads(Path('/tmp/boldstone-match-review-20261016/ss_image_index.json').read_text()):
    if r.get('ok') and Path(r['local_path']).exists():cache[r['url']]=r['local_path']
for r in json.loads((product/'Public_Gallery_References.json').read_text())['records']:
    if Path(r.get('image_path','')).is_file():cache[r['image_url']]=r['image_path']
(ev/'public-pages').mkdir(exist_ok=True);(ev/'offer-images').mkdir(exist_ok=True)
def get(url,path):
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as response:path.write_bytes(response.read())
    return path.read_bytes()
def one(args):
    n,r=args;pid=r['Product ID [Non Editable]'];url='https://boldstonesculpture.com/buy/p/'+r['Product URL']; record={'ref':f'O{n:03d}','pid':pid,'title':r['Title'],'sku':r['SKU'],'source_row':r['_row'],'url':url,'images':[]}
    try:
        path=ev/'public-pages'/(pid+'.html');body=get(url,path);markup=body.decode('utf-8','replace')
        ld=[]
        for script in re.findall(r'<script[^>]*type=[\"\x27]application/ld\+json[\"\x27][^>]*>(.*?)</script>',markup,re.S|re.I):
            try:ld.append(json.loads(script))
            except Exception:pass
        match=re.search(r'<main\b[^>]*>(.*?)</main>',markup,re.S|re.I);main=match.group(1) if match else markup
        main=re.sub(r'<(script|style|nav|header|footer)\b[^>]*>.*?</\1>','',main,flags=re.S|re.I)
        text='\n'.join(t.strip() for t in html.unescape(re.sub(r'<[^>]+>','\n',main)).splitlines() if t.strip());(ev/'public-pages'/(pid+'.txt')).write_text(text)
        record.update(page_sha256=hashlib.sha256(body).hexdigest(),page_text=str(ev/'public-pages'/(pid+'.txt')),structured=ld,page_status='READ')
    except Exception as error:record.update(page_status='UNAVAILABLE',page_error=str(error))
    urls=re.findall(r'https?://\S+',r.get('Hosted Image URLs',''))[:3]
    for order,u in enumerate(urls,1):
        try:
            path=Path(cache.get(u,'')) if u in cache else ev/'offer-images'/(pid+f'-{order:02d}.image')
            data=get(u,path)
            with Image.open(path) as im:
                thumb=out/(pid+f'-{order:02d}.jpg');ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'),(500,500)).save(thumb,quality=92)
            record['images'].append(dict(order=order,url=u,path=str(path),thumb=str(thumb),sha256=hashlib.sha256(data).hexdigest()))
        except Exception as error:record['images'].append(dict(order=order,url=u,error=str(error)))
    return record
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: records=list(pool.map(one,enumerate(source['SS Wall Products'],1)))
(ev/'offer_review_index.json').write_text(json.dumps(records,ensure_ascii=False))
for start in range(0,len(records),12):
    rows=records[start:start+12];board=Image.new('RGB',(1560,((len(rows)+3)//4)*300),'white');draw=ImageDraw.Draw(board)
    for i,r in enumerate(rows):
        x=i%4*390;y=i//4*300
        for j,im in enumerate([v for v in r['images'] if 'thumb'in v][:2]):
            with Image.open(im['thumb']) as src:
                pic=ImageOps.contain(src,(188,212));board.paste(pic,(x+j*195+(195-pic.width)//2,y))
        title=r['title'];lines=[title[a:a+54] for a in range(0,len(title),54)]
        draw.multiline_text((x+3,y+215),r['ref']+' '+r['sku']+'\n'+'\n'.join(lines),fill='black',spacing=3)
    board.save(out/f'offers-{start//12+1:02d}.jpg',quality=94)
print(json.dumps(dict(offers=len(records),pages=sum(r['page_status']=='READ' for r in records),images=sum('path'in x for r in records for x in r['images']))))
