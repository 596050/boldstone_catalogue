import collections,datetime,html,json,math,pathlib,re,urllib.parse
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=pathlib.Path(__file__).parent
def dump(n,x):(ROOT/n).write_text(json.dumps(x,indent=2)+'\n')
def natural(s):return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',s)]
def fq(s):return re.sub(r'^ns:\d+/','',s)
def url(s):return 'https://www.dropbox.com/home'+urllib.parse.quote(s,safe='/')
def wrap(s,n):
    words=s.split();out=[];line=''
    for word in words:
        if len(line+' '+word)>n:out.append(line);line=word
        else:line=(line+' '+word).strip()
    if line:out.append(line)
    return out
def main():
    source=json.loads((ROOT/'fresh-complete-native-listings.json').read_text())
    rows=[r for p in sorted(ROOT.glob('original-batch-*.json')) for r in json.loads(p.read_text())]
    assert len(rows)==337 and len({r['id'] for r in rows})==337
    assert all('sha256' in r for r in rows)
    folders={fq(e['path']):e['file_id'] for fam in source['listings'] for e in fam['result']['entries'] if e['object_type']=='folder'}
    rows.sort(key=lambda r:(r['family'],fq(r['path']).rsplit('/',1)[0],natural(r['name'])))
    for i,r in enumerate(rows,1):
        r['review_index']=i;r['path_display']=fq(r['path']);r['folder_path']=r['path_display'].rsplit('/',1)[0]
        r['folder_id']=folders[r['folder_path']];r['folder_url']=url(r['folder_path']);r['image_url']=r['folder_url']+'?preview='+urllib.parse.quote(r['name'],safe='')
    dump('verified-original-downloads.json',rows)
    dump('all337-current-image-and-folder-links.json',rows)
    (ROOT/'thumbnails').mkdir(exist_ok=True)
    fonts='/System/Library/Fonts/Supplemental/Arial.ttf'
    font=ImageFont.truetype(fonts,17);small=ImageFont.truetype(fonts,14);title=ImageFont.truetype(fonts,25)
    boards=[]
    for family in sorted({r['family'] for r in rows}):
        rr=[r for r in rows if r['family']==family]
        slug=family.lower().replace(' ','-')
        for page,start in enumerate(range(0,len(rr),20),1):
            subset=rr[start:start+20];board=Image.new('RGB',(1600,50+365*math.ceil(len(subset)/4)),(235,235,235));d=ImageDraw.Draw(board)
            d.text((12,10),f'{family} | page {page} | {start+1}-{start+len(subset)} of {len(rr)} originals',fill='black',font=title)
            for j,r in enumerate(subset):
                x=(j%4)*400;y=50+(j//4)*365
                with Image.open(r['local_path']) as im:
                    im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((390,255));board.paste(im,(x+(400-im.width)//2,y+(255-im.height)//2))
                    thumb=im.copy();thumb.thumbnail((320,240));thumb.save(ROOT/'thumbnails'/f"{r['review_index']:03d}.jpg",quality=85)
                label=f"#{r['review_index']:03d} | "+r['name'].split('__')[-1]
                d.text((x+8,y+258),label[:48],fill='black',font=font)
                for k,line in enumerate(wrap(r['folder_path'].rsplit('/',1)[-1],43)[:4]):d.text((x+8,y+281+k*18),line,fill='black',font=small)
            path=ROOT/f'{slug}-page-{page}.jpg';board.save(path,quality=90);boards.append({'family':family,'page':page,'path':str(path),'indices':[r['review_index'] for r in subset]})
    dump('contact-board-index.json',boards)
    pages=[]
    for family in sorted({r['family'] for r in rows}):
        rr=[r for r in rows if r['family']==family]
        parts=['<!doctype html><meta charset="utf-8"><title>'+html.escape(family)+' current image and folder links</title><style>body{font:16px system-ui;margin:25px}article{display:inline-block;width:340px;vertical-align:top;min-height:360px;border:1px solid #bbb;padding:10px;margin:5px;overflow-wrap:anywhere}img{width:320px;height:240px;object-fit:contain}</style>',f'<h1>{html.escape(family)}: {len(rr)} current originals</h1><p>Fresh native paths and content hashes checked; EXIF orientation respected. This report records filing review, not physical stock or manufactured finish confirmation.</p>']
        for r in rr:
            parts.append(f'<article><a href="{html.escape(r["image_url"],quote=True)}"><img src="thumbnails/{r["review_index"]:03d}.jpg"></a><p>#{r["review_index"]:03d} <a href="{html.escape(r["image_url"],quote=True)}">{html.escape(r["name"])}</a></p><p>Folder: <a href="{html.escape(r["folder_url"],quote=True)}">{html.escape(r["folder_path"].rsplit("/",1)[-1])}</a></p></article>')
        filename=family.lower().replace(' ','-')+'-all-image-folder-links.html';(ROOT/filename).write_text('\n'.join(parts));pages.append((family,filename))
    (ROOT/'all337-current-image-and-folder-links.html').write_text('<!doctype html><meta charset="utf-8"><h1>337 current image and folder links</h1>'+''.join(f'<p><a href="{n}">{html.escape(f)}</a></p>' for f,n in pages))
    (ROOT/'all337-current-image-and-folder-links.tsv').write_text('review_index\tfamily\tfilename\timage_url\tfolder_url\n'+''.join(f'{r["review_index"]}\t{r["family"]}\t{r["name"]}\t{r["image_url"]}\t{r["folder_url"]}\n' for r in rows))
    summary={f:{'files':sum(r['family']==f for r in rows),'bytes':sum(r['size'] for r in rows if r['family']==f),'folders':dict(collections.Counter(r['folder_path'].rsplit('/',1)[-1] for r in rows if r['family']==f))} for f in sorted({r['family'] for r in rows})}
    dump('family-folder-counts.json',summary)
    print(json.dumps({'families':summary,'originals':len(rows),'bytes':sum(r['size'] for r in rows),'reused':sum(r['reused_native_identical_local_bytes'] for r in rows),'contact_boards':len(boards)}),flush=True)
if __name__=='__main__':main()
