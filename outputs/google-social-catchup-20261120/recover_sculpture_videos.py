"""Retain the source MP4 exposed by each original post's public embed video tag."""
import json,sys,urllib.request,subprocess
from pathlib import Path
from urllib.parse import urlparse
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from settings import Settings
from common import atomic_json,digest,utc
rows=json.loads((OUT/'history-review-decisions-legacy.json').read_text())['decisions']
selected=[r for r in rows if r['decision']=='INCLUDE_SCULPTURE' and r['sources'][0]['post_type']=='IG reel']
groups=json.loads((OUT/'history-audit.json').read_text())['groups']
for code in ['Df2FuDyA9kQ','DdL9Jx_ApkK']:
 g=next(g for g in groups if any(code in s['url'] for s in g['sources']));selected.append({**g,'shortcode':code})
c=SourceChrome(Settings(),OUT/'instagram-reader-state');name='verification'
file=OUT/'source-video-receipts.json';receipts=json.loads(file.read_text()) if file.exists() else []
done={r['source_key'] for r in receipts if r['status']=='SOURCE_VIDEO_VERIFIED'}
for row in selected:
 if row['source_key'] in done:continue
 code=row['shortcode'];url='https://www.instagram.com/p/'+code+'/embed/captioned/'
 try:
  if c.bindings[name]['url']!=url:c.navigate(name,url,recovery=True)
  snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True})
  assert any(urlparse(l['href']).path=='/boldstonesculpture/' and l['text']=='boldstonesculpture' for l in snap['links'])
  assert any(urlparse(l['href']).path in {'/p/'+code+'/','/reel/'+code+'/'} for l in snap['links'])
  assert ' '.join(row['caption'].split()) in ' '.join(snap['text'].split())
  assert len(snap['videos'])==1
  video=snap['videos'][0];parsed=urlparse(video['src'])
  assert parsed.scheme=='https' and (parsed.hostname or '').endswith('.cdninstagram.com') and parsed.path.endswith('.mp4')
  request=urllib.request.Request(video['src'],headers={'User-Agent':'Mozilla/5.0','Referer':snap['url']})
  with urllib.request.urlopen(request,timeout=60) as response:raw=response.read(100_000_001)
  assert len(raw)<=100_000_000 and raw[4:8]==b'ftyp'
  path=OUT/'history-media'/('instagram-original-'+code+'.mp4');path.write_bytes(raw)
  probe=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,text=True,check=True)
  metadata=json.loads(probe.stdout);streams=metadata['streams'];assert any(s['codec_type']=='video' for s in streams)
  evidence=OUT/'embed-source-evidence'/('video-'+code+'-'+digest(snap)[:12]+'.json')
  atomic_json(evidence,{'utc':utc(),'source':row['sources'],'snapshot':snap,'selected_native_video':video,'metadata':metadata})
  result={'utc':utc(),'status':'SOURCE_VIDEO_VERIFIED','source_key':row['source_key'],'shortcode':code,'sources':row['sources'],'caption':row['caption'],'media_path':str(path.resolve()),'sha256':digest(raw),'bytes':len(raw),'duration':float(metadata['format']['duration']),'streams':streams,'evidence_path':str(evidence.resolve()),'evidence_sha256':digest(evidence.read_bytes()),'method':'Original MP4 URL observed on public Instagram embed video element; exact author, source permalink and caption checked'}
 except Exception as error:result={'source_key':row['source_key'],'shortcode':code,'status':'SOURCE_REVIEW_REQUIRED','error':str(error)}
 receipts=[r for r in receipts if r['source_key']!=row['source_key']]+[result];atomic_json(file,receipts)
 print(json.dumps({k:v for k,v in result.items() if k in {'shortcode','status','error','bytes','duration'}}),flush=True)
