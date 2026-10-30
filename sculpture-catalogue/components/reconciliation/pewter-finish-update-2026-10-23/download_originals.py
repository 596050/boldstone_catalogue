import json, hashlib, urllib.request, struct, sys, subprocess, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
request_path = Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/boldstone-pewter-download-2026-10-23.json')
request = json.loads(request_path.read_text())
out = HERE / 'originals'
out.mkdir(exist_ok=True)
records = []
for item in request['entries']:
    target = out / (item['id'].split(':',1)[1] + Path(item['name']).suffix.lower())
    if target.exists():
        data = target.read_bytes()
    else:
        with urllib.request.urlopen(item['download_url'], timeout=60) as response:
            data = response.read()
        target.write_bytes(data)
    blocks = [hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304)]
    dbhash = hashlib.sha256(b''.join(blocks)).hexdigest()
    assert len(data) == item['size'], (item['id'], 'size mismatch')
    assert dbhash == item['content_hash'], (item['id'], 'Dropbox hash mismatch')
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        dimensions = list(struct.unpack('>II', data[16:24]))
    else:
        info = subprocess.check_output(['sips','-g','pixelWidth','-g','pixelHeight',str(target)],text=True)
        dimensions = [int(re.search(key+r': (\d+)',info).group(1)) for key in ['pixelWidth','pixelHeight']]
    records.append({k:item[k] for k in ['id','name','size','content_hash','path_display'] if k in item} | {'sha256':hashlib.sha256(data).hexdigest(),'dimensions_px':dimensions,'local_original':str(target),'pixels_edited':False})
(HERE/(sys.argv[2] if len(sys.argv)>2 else 'original-verification.json')).write_text(json.dumps({'status':'PASS','files':records},indent=2)+'\n')
request_path.unlink()
print(json.dumps({'status':'PASS','files':records},indent=2))
