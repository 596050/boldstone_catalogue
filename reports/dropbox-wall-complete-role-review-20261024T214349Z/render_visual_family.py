import html,json,math,pathlib,re,sys
from PIL import Image,ImageOps,ImageDraw,ImageFont
P=pathlib.Path(__file__).resolve().parent
def natural(s):return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)',s)]
def wrap(s,n=47):
 out=[];line=''
 for word in s.split():
  if len(line+' '+word)>n:out.append(line);line=word
  else:line=(line+' '+word).strip()
 if line:out.append(line)
 return out
def run(family):
 rows=[r for r in json.loads((P/'all-current-6360-image-folder-links.json').read_text()) if r['family']==family];sources={r['file_id']:r for r in json.loads((P/'current-6360-visual-source-evidence.json').read_text())};rows.sort(key=lambda r:(r['folder_path'],natural(r['name'])));slug=re.sub('[^a-z0-9]+','-',family.lower()).strip('-');outdir=P/'families'/slug;outdir.mkdir(parents=True,exist_ok=True);thumb=outdir/'previews';thumb.mkdir(exist_ok=True)
 font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17);small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14);title=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',25)
 for i,r in enumerate(rows,1):r.update(review_index=i,visual_source=sources[r['file_id']])
 boards=[]
 for page,start in enumerate(range(0,len(rows),20),1):
  subset=rows[start:start+20];board=Image.new('RGB',(1600,50+365*math.ceil(len(subset)/4)),(237,237,237));d=ImageDraw.Draw(board);d.text((12,10),f'{family} | {start+1}-{start+len(subset)} of {len(rows)} | page {page}',fill='black',font=title)
  for j,r in enumerate(subset):
   x=(j%4)*400;y=50+(j//4)*365;src=r['visual_source']['source_image_path']
   if src:
    with Image.open(src) as im:
     im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((390,255));board.paste(im,(x+(400-im.width)//2,y+(255-im.height)//2));im.thumbnail((340,255));im.save(thumb/f'{r["review_index"]:03d}.jpg',quality=90)
   else:d.text((x+15,y+100),'UNAVAILABLE VISUAL SOURCE',fill='red',font=font)
   short=r['name'].split('__')[-1];d.text((x+7,y+258),f'#{r["review_index"]:03d} | '+short[:43],fill='black',font=font)
   for k,line in enumerate(wrap(r['folder_path'].split('/')[-1])[:4]):d.text((x+7,y+281+k*18),line,fill='black',font=small)
  dest=outdir/f'page-{page}.jpg';board.save(dest,quality=92);boards.append({'page':page,'path':str(dest),'indices':[r['review_index'] for r in subset]})
 (outdir/'indexed-current-images-and-links.json').write_text(json.dumps(rows,indent=2)+'\n');(outdir/'contact-board-index.json').write_text(json.dumps(boards,indent=2)+'\n')
 parts=['<!doctype html><meta charset="utf-8"><title>'+html.escape(family)+' current gallery</title><style>body{font:16px system-ui;margin:24px}article{display:inline-block;vertical-align:top;width:350px;padding:10px;margin:6px;border:1px solid #bbb;overflow-wrap:anywhere}img{width:340px;height:255px;object-fit:contain;background:#eee}</style><h1>'+html.escape(family)+': '+str(len(rows))+' current images</h1><p>Source cache provenance is recorded for every preview. Visual-role annotation is separate from native metadata and catalogue photo selections. No Dropbox changes.</p>']
 for r in rows:parts.append('<article><a href="'+html.escape(r['image_url'],quote=True)+'"><img loading="lazy" src="previews/'+str(r['review_index']).zfill(3)+'.jpg"></a><p>#'+str(r['review_index'])+' <a href="'+html.escape(r['image_url'],quote=True)+'">'+html.escape(r['name'])+'</a></p><p><a href="'+html.escape(r['folder_url'],quote=True)+'">'+html.escape(r['folder_path'].split('/')[-1])+'</a></p></article>')
 (outdir/'all-current-image-folder-links.html').write_text(''.join(parts));print(json.dumps({'family':family,'images':len(rows),'boards':len(boards),'directory':str(outdir)}),flush=True)
if __name__=='__main__':run(sys.argv[1])
