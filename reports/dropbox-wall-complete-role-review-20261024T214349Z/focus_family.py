import hashlib,json,pathlib,sys
from PIL import Image,ImageOps,ImageDraw,ImageFont
from prepare_visual_sources import hashes
P=pathlib.Path(__file__).resolve().parent
def run(slug,indices):
 d=P/'families'/slug;assert not(d/'family-role-seal.json').exists(),'Use a separate correction packet for a sealed family'
 rows={r['review_index']:r for r in json.loads((d/'indexed-current-images-and-links.json').read_text())};cache=json.loads((P/'candidate-current-image-cache-paths.json').read_text())['candidates'];native={r['id']:r for r in json.loads((P/'fresh-all-6360-native-hash-metadata.json').read_text())['entries']};chosen=[]
 extras={}
 for receipt in P.glob('verified-*-originals.json'):
  data=json.loads(receipt.read_text())
  if isinstance(data,list):
   for item in data:
    if isinstance(item,dict) and item.get('id') and item.get('local_path'):extras.setdefault(item['id'],[]).append(item['local_path'])
 for i in indices:
  r=rows[i];n=native[r['file_id']];source=r['visual_source']['source_image_path'];kind=r['visual_source']['visual_source_kind'];original=False
  for candidate in cache[r['file_id']]['originals']+extras.get(r['file_id'],[]):
   path=pathlib.Path(candidate)
   if path.is_file() and path.stat().st_size==r['size']:
    sh,dh=hashes(path)
    if dh==n['content_hash']:source=str(path);kind='EXISTING_ORIGINAL_REHASHED_AGAINST_CURRENT_NATIVE_HASH';original=True;break
  chosen.append({'review_index':i,'file_id':r['file_id'],'name':r['name'],'source_path':source,'source_kind':kind,'original_current_rehash':original,'native_content_hash':n['content_hash'],'actual_visual_source_sha256':hashlib.sha256(pathlib.Path(source).read_bytes()).hexdigest()})
 font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',22)
 for page,start in enumerate(range(0,len(chosen),4),1):
  b=Image.new('RGB',(1600,1760),(237,237,237));draw=ImageDraw.Draw(b)
  for k,r in enumerate(chosen[start:start+4]):
   x=(k%2)*800;y=(k//2)*880
   with Image.open(r['source_path']) as im:
    im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((780,800));b.paste(im,(x+(800-im.width)//2,y+(800-im.height)//2))
   draw.text((x+8,y+810),str(r['review_index']).zfill(3)+' '+r['name'].split('__')[-1][:45],font=font,fill='black')
  b.save(d/f'focus-page-{page}.jpg',quality=94)
 (d/'focus-check-originals.json').write_text(json.dumps(chosen,indent=2)+'\n');print('FOCUSED',len(chosen),'REHASHED_ORIGINALS',sum(r['original_current_rehash'] for r in chosen),flush=True)
if __name__=='__main__':run(sys.argv[1],[int(x) for x in sys.argv[2].split(',')])
