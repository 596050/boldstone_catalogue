import collections,html,json,math,pathlib,re,sys,urllib.parse
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=pathlib.Path(__file__).parent
def fq(s):return re.sub(r'^ns:\d+/','',s)
def home(s):return 'https://www.dropbox.com/home'+urllib.parse.quote(s,safe='/')
def natural(s):return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',s)]
def wrap(s,n):
    words=s.split();out=[];line=''
    for word in words:
        if len(line+' '+word)>n:out.append(line);line=word
        else:line=(line+' '+word).strip()
    if line:out.append(line)
    return out
def run(family):
    listing=json.loads((ROOT/'fresh-complete-native-listings.json').read_text());native=next(r for r in listing['listings'] if r['name']==family);files={e['file_id']:e for e in native['result']['entries'] if e['object_type']=='file'};folders={fq(e['path']):e['file_id'] for e in native['result']['entries'] if e['object_type']=='folder'}
    rows=[r for p in ROOT.glob('original-batch-*.json') for r in json.loads(p.read_text()) if r.get('family')==family];assert len(rows)==len(files) and {r.get('id') for r in rows}==set(files);assert all('sha256' in r for r in rows)
    rows.sort(key=lambda r:(fq(r['path']).rsplit('/',1)[0],natural(r['name'])));slug=family.lower().replace(' ','-');thumbs=ROOT/'thumbnails'/slug;thumbs.mkdir(parents=True,exist_ok=True)
    for i,r in enumerate(rows,1):
        e=files[r['id']];assert e['path']==r['path'] and e['file']['size']==r['size'];r.update(review_index=i,path_display=fq(r['path']));parent=r['path_display'].rsplit('/',1)[0];r.update(folder_id=folders[parent],folder_path=parent,folder_url=home(parent),image_url=home(parent)+'?preview='+urllib.parse.quote(r['name'],safe=''))
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17);small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14);title=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',25);boards=[]
    for page,start in enumerate(range(0,len(rows),20),1):
        subset=rows[start:start+20];board=Image.new('RGB',(1600,50+365*math.ceil(len(subset)/4)),(237,237,237));d=ImageDraw.Draw(board);d.text((12,10),f'{family} | page {page} | {start+1}-{start+len(subset)} of {len(rows)} originals',fill='black',font=title)
        for j,r in enumerate(subset):
            x=(j%4)*400;y=50+(j//4)*365
            with Image.open(r['local_path']) as im:
                im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((390,255));board.paste(im,(x+(400-im.width)//2,y+(255-im.height)//2));im.thumbnail((320,240));im.save(thumbs/f'{r["review_index"]:03d}.jpg',quality=88)
            label=f'#{r["review_index"]:03d} | '+r['name'].split('__')[-1];d.text((x+8,y+258),label[:48],fill='black',font=font)
            for k,line in enumerate(wrap(r['folder_path'].rsplit('/',1)[-1],43)[:4]):d.text((x+8,y+281+k*18),line,fill='black',font=small)
        path=ROOT/f'{slug}-page-{page}.jpg';board.save(path,quality=92);boards.append({'family':family,'page':page,'path':str(path),'indices':[r['review_index'] for r in subset]})
    (ROOT/f'{slug}-verified-originals-and-links.json').write_text(json.dumps(rows,indent=2)+'\n');(ROOT/f'{slug}-contact-board-index.json').write_text(json.dumps(boards,indent=2)+'\n')
    out=['<!doctype html><meta charset="utf-8"><title>'+html.escape(family)+' all current image and folder links</title><style>body{font:16px system-ui;margin:25px}article{display:inline-block;width:340px;vertical-align:top;min-height:360px;border:1px solid #bbb;padding:10px;margin:5px;overflow-wrap:anywhere}img{width:320px;height:240px;object-fit:contain}</style>',f'<h1>{html.escape(family)}: {len(rows)} current originals</h1><p>Actual original bytes checked against fresh native content hashes. EXIF orientation respected in previews. No native changes applied.</p>']
    for r in rows:out.append(f'<article><a href="{html.escape(r["image_url"],quote=True)}"><img src="thumbnails/{slug}/{r["review_index"]:03d}.jpg"></a><p>#{r["review_index"]:03d} <a href="{html.escape(r["image_url"],quote=True)}">{html.escape(r["name"])}</a></p><p>Folder: <a href="{html.escape(r["folder_url"],quote=True)}">{html.escape(r["folder_path"].rsplit("/",1)[-1])}</a></p></article>')
    (ROOT/f'{slug}-all-image-folder-links.html').write_text('\n'.join(out));print(json.dumps({'family':family,'originals':len(rows),'bytes':sum(r['size'] for r in rows),'folders':dict(collections.Counter(r['folder_path'].rsplit('/',1)[-1] for r in rows)),'boards':len(boards)}),flush=True)
if __name__=='__main__':run(sys.argv[1])
