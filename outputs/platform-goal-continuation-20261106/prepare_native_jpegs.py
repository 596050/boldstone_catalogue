"""Losslessly expose primary JPEG codestreams from camera MPO containers.

Only the MPF marker and separate secondary frame are omitted. No pixel,
colour-profile, orientation, crop, size or JPEG-compression changes are made.
"""
from pathlib import Path
from PIL import Image
import json,hashlib

OUT=Path(__file__).parent;DEST=OUT/'native-upload-jpegs';DEST.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
files=['ammonite-upload-packet.json','moon-fish-upload-packet.json','lunar-phase-iv-upload-packet.json','context-upload-packets.json']
packets={name:json.loads((OUT/name).read_text()) for name in files}
proofs={p['photo']['image_id']:p['photo'] for ps in packets.values() for p in ps}
receipts={}
def extract(data):
    assert data[:2]==b'\xff\xd8'
    parts=[data[:2]];pos=2;removed=[]
    while True:
        start=pos;assert data[pos]==255;pos+=1
        while data[pos]==255:pos+=1
        marker=data[pos];pos+=1
        if marker==0xd9:
            parts.append(data[start:pos]);break
        assert marker not in (0,0xd8) and not 0xd0<=marker<=0xd7
        length=int.from_bytes(data[pos:pos+2],'big');end=pos+length;assert length>=2
        payload=data[pos+2:end]
        if marker==0xe2 and payload.startswith(b'MPF\x00'):removed.append(dict(marker='APP2 MPF',start=start,end=end))
        else:parts.append(data[start:end])
        pos=end
        if marker==0xda:
            scan_start=pos
            while True:
                at=data.find(b'\xff',pos);assert at>=0;q=at+1
                while data[q]==255:q+=1
                m=data[q]
                if m==0 or 0xd0<=m<=0xd7:pos=q+1;continue
                parts.append(data[scan_start:at]);pos=at;break
    assert len(removed)==1 and data[pos-2:pos]==b'\xff\xd9'
    return b''.join(parts),removed,pos
for aid,proof in proofs.items():
    src=Path(proof['local_path']);data=src.read_bytes();assert sha(data)==proof['sha256']
    with Image.open(src) as original:
        original.load();assert original.mode=='RGB'
        if original.format=='JPEG':
            assert getattr(original,'n_frames',1)==1
            receipts[aid]=dict(status='UNCHANGED_SINGLE_JPEG',source_path=str(src),upload_path=str(src),source_sha256=sha(data),upload_sha256=sha(data),size=list(original.size),pixel_edits=False)
            continue
        assert original.format=='MPO'
        body,removed,end=extract(data)
        target=DEST/(src.stem+'--primary-jpeg.jpg')
        if target.exists():assert target.read_bytes()==body
        else:target.write_bytes(body)
        with Image.open(target) as exported:
            exported.load();assert exported.format=='JPEG' and getattr(exported,'n_frames',1)==1
            assert exported.size==original.size and exported.mode==original.mode and exported.getexif().get(274)==original.getexif().get(274)
            decoded=sha(original.tobytes());assert decoded==sha(exported.tobytes())
        assert src.read_bytes()==data
        receipts[aid]=dict(status='PASS_LOSSLESS_CONTAINER_EXTRACTION_IDENTICAL_DECODED_PIXELS',source_path=str(src),upload_path=str(target),source_sha256=sha(data),upload_sha256=sha(body),decoded_pixel_sha256=decoded,size=list(original.size),source_bytes=len(data),upload_bytes=len(body),primary_end_offset=end,removed_markers=removed,pixel_edits=False,source_original_unchanged=True)
(OUT/'native-jpeg-container-verification.json').write_text(json.dumps(list(receipts.values()),ensure_ascii=False,indent=2)+'\n')
for name,ps in packets.items():
    for p in ps:
        r=receipts[p['photo']['image_id']]
        p['photo'].update(native_upload_path=r['upload_path'],native_upload_sha256=r['upload_sha256'],native_upload_format='JPEG',container_verification='native-jpeg-container-verification.json',native_image_upload_test_still_required=True)
    (OUT/name).write_text(json.dumps(ps,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(products=len([p for ps in packets.values() for p in ps]),distinct_photos=len(receipts),lossless_mpo_extractions=sum(r['status'].startswith('PASS_') for r in receipts.values()),pixel_changes=0,native_mutations=0)))
