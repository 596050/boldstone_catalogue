#!/usr/bin/env python3
"""Bounded anonymous public asset reads; no collection fetch or writes upstream."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,urllib.request
from PIL import Image
O=Path(__file__).resolve().parent;B=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
fpath=B/'worker-01/FRESH_PUBLIC_INVENTORY.json';f=json.loads(fpath.read_text());assert sha(fpath)=='4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd'
gate=f['fake_adapter_gate'];assert sha(gate['path'])==gate['sha256'];assert gate['reported']['status']=='PASS' and gate['reported']['tests_passed']==74
p=next(x for x in f['products'] if x['native_product_id']=='68dc0a35a7ac865209b39248')
(O/'native-gallery-images').mkdir(exist_ok=True);receipts=[]
for i,m in enumerate(p['native_media_items'][:4]):
 out=O/'native-gallery-images'/(m['id']+'.webp');at=datetime.now(timezone.utc).isoformat()
 if out.exists():raise RuntimeError('No replay: already cached '+str(out))
 req=urllib.request.Request(m['assetUrl'],headers={'User-Agent':'Boldstone-local-readonly-review/1.0','Accept':'image/*'})
 with urllib.request.urlopen(req,timeout=30) as r:
  data=r.read();status=r.status;ctype=r.headers.get('Content-Type');final=r.url;headers={k:r.headers.get(k) for k in ['Content-Length','Content-Type','ETag','Last-Modified','Date','Cache-Control']}
 assert status==200 and ctype.startswith('image/');out.write_bytes(data)
 with Image.open(out) as im:sz=list(im.size);mode=im.mode;pixelsha=hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest()
 receipts.append({'media_index':i,'native_media_id':m['id'],'native_title':m['title'],'request_url':m['assetUrl'],'final_url':final,'request_utc':at,'completed_utc':datetime.now(timezone.utc).isoformat(),'anonymous':True,'status':status,'response_headers':headers,'path':str(out),'sha256':sha(out),'bytes':len(data),'pixels':sz,'mode':mode,'decoded_rgba_sha256':pixelsha,'fresh_inventory_ref':{'path':str(fpath),'sha256':sha(fpath),'json_pointer':'/products/'+str(f['products'].index(p))+'/native_media_items/'+str(i)}})
 result={'schema':'boldstone.bounded-public-native-gallery-assets.v1','fake_adapter_gate':gate,'fresh_public_inventory':{'path':str(fpath),'sha256':sha(fpath)},'count':len(receipts),'reads':receipts,'collection_reads':0,'dropbox_calls':0,'remote_mutations':0,'shared_writes':0,'live_sandbox_tests_run':False,'scope':'Four public gallery assets only; separate from fake tests and physical-object evidence.'}
 (O/'NATIVE_GALLERY_ASSET_RECEIPTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'COMPLETE','count':len(receipts),'receipt_sha256':sha(O/'NATIVE_GALLERY_ASSET_RECEIPTS.json')},indent=2))
