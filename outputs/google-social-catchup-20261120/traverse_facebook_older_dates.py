"""Follow native ending-date controls when background timeline pagination stalls."""
import calendar,datetime,json,re,sys,time
from pathlib import Path
from urllib.parse import urlparse,parse_qs
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path[:0]=[str(ROOT/'social-publisher'),str(OUT)]
from source_chrome import SourceChrome
from google_fast import GoogleFastChrome
from settings import Settings
from common import atomic_json,digest,utc
c=SourceChrome(Settings(),OUT/'instagram-source-reader-state');name='verification'
folder=OUT/'facebook-older-date-evidence';folder.mkdir(exist_ok=True)
def canon(u):
 p=urlparse(u)
 if p.path in ['/photo/','/photo.php']:return 'facebook-photo:'+parse_qs(p.query).get('fbid',[''])[0]
 return 'https://www.facebook.com'+p.path.rstrip('/')
known=set()
for r in json.loads((OUT/'facebook-native-photo-history.json').read_text()):known.add(r['canonical_parent']);known.add('facebook-photo:'+r['photo_id'])
for r in json.loads((OUT/'facebook-native-photo-parent-records.json').read_text()):
 if r['parent_post_url']:known.add(canon(r['parent_post_url']))
for r in json.loads((OUT/'history-audit.json').read_text())['groups']:
 for s in r['sources']:
  if s['platform']=='facebook':known.add(canon(s['url']))
for r in json.loads((OUT/'facebook-reel-reconciliation.json').read_text())['reels']:known.add(canon(r['reel_url']))
feature='https://www.facebook.com/BoldstoneSculpture/posts/pfbid02DT6Zo3neXxNEERJMq9Je4Qdw1V5RXUKZN4v2N27CRFdHJSoiJbjayaKgBGUudRT2l'
date_re=r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) \d{1,2} [A-Za-z]+ \d{4} at \d{1,2}:\d{2}'
def feed(s):
 assert s['url']=='https://www.facebook.com/BoldstoneSculpture/' and 'Boldstone Sculpture' in s['text']
 text=s['text'].split('\nPosts\nFilters\n',1)[1].split('\nPost filters\n',1)[0]
 dates=re.findall(date_re,text);day=datetime.datetime.strptime(dates[0],'%A %d %B %Y at %H:%M').date() if dates else None
 urls={canon(x['href']) for x in s['links'] if re.match(r'https://www\.facebook\.com/(?:BoldstoneSculpture/(?:posts|videos)/|reel/)',x['href'])}-{feature}
 return day,text,sorted(urls)
def select(field,value,option):
 s=c.call(name,{'op':'snapshot','fullDocument':True});prefix='Edit ending date '+field+'. Current selection is ';combos=[r for r in s['controls'] if r['role']=='combobox' and r['name'].startswith(prefix)];assert len(combos)==1
 if combos[0]['name']==prefix+str(value):return
 GoogleFastChrome.call(c,name,{'op':'click','locator':[{'selector':'[role=combobox]','name':combos[0]['name']}]})
 GoogleFastChrome.call(c,name,{'op':'click','locator':[{'selector':'[role=option]','name':option}]})
f=OUT/'facebook-older-date-records.json';rows=json.loads(f.read_text()) if f.exists() else [];seen={r['day'] for r in rows}
s=c.call(name,{'op':'snapshot','fullDocument':True})
for step in range(200):
 day,text,urls=feed(s)
 if day is None:
  assert re.search(r'(?i)no posts (?:available|to show|found)|nothing to show|hasn.t posted',text),text
  atomic_json(OUT/'facebook-older-date-progress.json',{'utc':utc(),'status':'EXPLICIT_NATIVE_NO_POSTS_BEFORE_CURSOR','days_read':len(rows),'last_snapshot':s});break
 if day.isoformat() not in seen:
  proof=folder/(day.isoformat()+'-'+digest(s)[:12]+'.json');atomic_json(proof,s)
  record={'day':day.isoformat(),'native_post_urls':urls,'unmatched_urls':[u for u in urls if u not in known],'native_text':text,'evidence_path':str(proof.resolve()),'evidence_sha256':digest(proof.read_bytes())};rows.append(record);seen.add(day.isoformat());atomic_json(f,rows);print(json.dumps({k:record[k] for k in ['day','native_post_urls','unmatched_urls']}),flush=True)
 target=day-datetime.timedelta(days=1)
 select('year',target.year,str(target.year));select('month',target.month,calendar.month_name[target.month]);select('day',target.day,str(target.day))
 GoogleFastChrome.call(c,name,{'op':'click','locator':[{'selector':'[role=button]','name':'Done'}]})
 deadline=time.monotonic()+30
 while True:
  s=c.call(name,{'op':'snapshot','fullDocument':True});updated,body,_=feed(s)
  if updated and updated<=target:break
  if not updated and re.search(r'(?i)no posts (?:available|to show|found)|nothing to show|hasn.t posted',body):break
  if time.monotonic()>deadline:
   atomic_json(OUT/'facebook-older-date-cursor-stall.json',{'utc':utc(),'requested_ending_date':target.isoformat(),'snapshot':s});raise RuntimeError('The native ending-date query did not advance; do not infer source absence')
  time.sleep(.3)
 atomic_json(OUT/'facebook-older-date-progress.json',{'utc':utc(),'status':'IN_PROGRESS','days_read':len(rows),'ending_date':target.isoformat()})
else:raise RuntimeError('Native date-cursor bound reached; not complete')
