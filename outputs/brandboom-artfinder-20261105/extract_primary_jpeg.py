"""Extract the unchanged primary JPEG codestream from a misnamed MPO container.

No crop, resampling, synthesis, colour change or recompression is performed.
Only the MPF container marker and the separate embedded thumbnail are omitted.
"""
import hashlib,json
from pathlib import Path
from PIL import Image
OUT=Path(__file__).parent
src=OUT/'artfinder-photo-candidates/textured-panels__textured-panel-tall-rust-and-blue-patina__001.jpg'
dst=src.with_name(src.stem+'-primary-jpeg.jpg')
data=src.read_bytes();assert data[:2]==b'\xff\xd8'
parts=[data[:2]];pos=2;removed=[];entropy=[]
while True:
 start=pos;assert data[pos]==255,(pos,data[pos]);pos+=1
 while data[pos]==255:pos+=1
 marker=data[pos];pos+=1
 if marker==0xd9:
  parts.append(data[start:pos]);break
 assert marker not in (0,0xd8) and not 0xd0<=marker<=0xd7
 length=int.from_bytes(data[pos:pos+2],'big');end=pos+length;assert length>=2
 payload=data[pos+2:end]
 if marker==0xe2 and payload.startswith(b'MPF\x00'):
  removed.append({'marker':'APP2 MPF','start':start,'end':end})
 else:parts.append(data[start:end])
 pos=end
 if marker==0xda:
  scan_start=pos
  while True:
   at=data.find(b'\xff',pos);assert at>=0
   q=at+1
   while data[q]==255:q+=1
   m=data[q]
   if m==0 or 0xd0<=m<=0xd7:pos=q+1;continue
   parts.append(data[scan_start:at]);entropy.append(data[scan_start:at]);pos=at;break
assert len(removed)==1 and data[pos-2:pos]==b'\xff\xd9'
body=b''.join(parts);dst.write_bytes(body)
a=Image.open(src);b=Image.open(dst)
assert a.format=='MPO' and b.format=='JPEG' and getattr(b,'n_frames',1)==1
assert a.size==b.size and a.mode==b.mode and a.getexif().get(274)==b.getexif().get(274)
raw_a=hashlib.sha256(a.tobytes()).hexdigest();raw_b=hashlib.sha256(b.tobytes()).hexdigest();assert raw_a==raw_b
receipt={'status':'PASS_LOSSLESS_CONTAINER_EXTRACTION_IDENTICAL_DECODED_PIXELS','source':str(src),'output':str(dst),
 'source_sha256':hashlib.sha256(data).hexdigest(),'output_sha256':hashlib.sha256(body).hexdigest(),
 'decoded_pixel_sha256':raw_a,'size':list(b.size),'exif_orientation':b.getexif().get(274),
 'removed_container_markers':removed,'source_bytes':len(data),'output_bytes':len(body),
 'primary_end_offset':pos,'pixel_edits':False,'crop_still_required':True}
(OUT/'artfinder-container-repair.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
