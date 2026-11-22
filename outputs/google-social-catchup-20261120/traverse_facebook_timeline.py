"""Read own public Page timeline links to catch posts outside photo/reel collections."""
import json,re,sys,time
from pathlib import Path
from urllib.parse import urlparse
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from settings import Settings
from common import atomic_json,digest,utc
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification';assert c.bindings[name]['url']=='https://www.facebook.com/BoldstoneSculpture/'
proofs=OUT/'facebook-timeline-native-evidence';proofs.mkdir(exist_ok=True)
f=OUT/'facebook-native-timeline-posts.json';rows=json.loads(f.read_text()) if f.exists() else [];seen={r['url'] for r in rows};stable=0;previous=None
for step in range(1500):
 s=c.call(name,{'op':'snapshot','fullDocument':True});probe=c.call(name,{'op':'probe'});assert 'Boldstone Sculpture' in s['text']
 post_links={r['href'].split('?')[0].rstrip('/') for r in s['links'] if re.fullmatch(r'https://www\.facebook\.com/BoldstoneSculpture/posts/[^/?]+/?',r['href'].split('?')[0])}
 new=post_links-seen
 proof=proofs/('%04d-%s.json'%(step,digest({'posts':sorted(post_links),'scroll':probe['scroll']})[:12]));atomic_json(proof,{'utc':utc(),'snapshot':s,'probe':probe,'source_post_links':sorted(post_links)})
 for u in sorted(new):rows.append({'url':u,'first_seen_step':step,'source_evidence_path':str(proof.resolve()),'source_evidence_sha256':digest(proof.read_bytes())})
 seen|=new;atomic_json(f,rows)
 current=(probe['scroll']['y'],probe['scroll']['height'],tuple(sorted(post_links)))
 stable=stable+1 if not new and current==previous and probe['scroll']['at_bottom'] else 0;previous=current
 end_message=bool(re.search(r'(?i)no more posts|no posts available|nothing more to show|you.re all caught up',s['text']))
 status='NATIVE_END_MESSAGE' if end_message and probe['scroll']['at_bottom'] else 'STABLE_NATIVE_TIMELINE_END' if stable>=12 else 'IN_PROGRESS'
 progress={'utc':utc(),'status':status,'steps':step+1,'unique_native_post_links':len(rows),'scroll':probe['scroll'],'stable_end_reads':stable,'end_message':end_message,'last_visible_text':s['text'][-4500:],'last_evidence_path':str(proof.resolve()),'last_evidence_sha256':digest(proof.read_bytes())};atomic_json(OUT/'facebook-native-timeline-progress.json',progress)
 print(json.dumps({k:progress[k] for k in ['status','steps','unique_native_post_links','scroll','stable_end_reads']}),flush=True)
 if status!='IN_PROGRESS':break
 c.call(name,{'op':'scroll_page'});time.sleep(.5 if not probe['scroll']['at_bottom'] else 2)
else:raise RuntimeError('Native timeline safety bound reached; coverage is not complete')
