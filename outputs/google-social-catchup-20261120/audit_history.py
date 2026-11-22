"""Match exported source posts, with explicit review buckets for older work."""
import hashlib,json,re,sqlite3,unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
coverage=json.loads((OUT/'coverage-inventory.json').read_text());known={r['catalogue_id'] for r in coverage['sculptures']}
def url_identity(url):
 p=urlparse(url)
 if 'instagram.com' in (p.hostname or ''):
  match=re.search(r'/(?:p|reel)/([^/?#]+)',p.path)
  return 'instagram:'+match.group(1) if match else url
 return 'facebook:'+p.path.rstrip('/').split('/')[-1]
def core(caption):
 text=re.sub(r'https?://\S+','',caption)
 text=re.sub(r'#\w+','',text)
 text=re.sub(r'(?im)[^\n.!?]*\b(?:product tag|tagged product|link in (?:our |the )?bio)\b[^\n.!?]*(?:[.!?]|$)','',text)
 text='\n\n'.join(p for p in text.split('\n\n') if not re.match(r'(?i)^\s*(?:Shop this sculpture|View this sculpture and order|For homes, gardens and design projects\. View|For homes, gardens and design projects\. View the individual sculpture|See the sculpture, current price)',p))
 return ' '.join(unicodedata.normalize('NFKC',text).casefold().split()).strip()
known_urls={url_identity(s['url']):row['catalogue_id'] for row in coverage['sculptures'] for s in row['meta_sources']}
known_captions={}
for p in json.loads((OUT/'prepared-posts.json').read_text()):known_captions[core(p['source_meta_caption'])]=p['catalogue_id']
db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
for raw,state in db.execute('SELECT payload,state FROM jobs'):
 p=json.loads(raw)
 if p['platform'] in ['facebook','instagram'] and p['catalogue_id'] in known and state in ['PUBLISHED','HISTORICAL_VERIFIED']:
  known_captions[core(p['caption'])]=p['catalogue_id']
db.close()
groups={};matched=set();counts={}
for platform in ['facebook','instagram']:
 rows=json.loads((OUT/('meta-'+platform+'-2026-rows.json')).read_text())
 rows=[r for r in rows if re.fullmatch(r'\d+',r['Post ID'])];counts[platform]=len(rows)
 for row in rows:
  caption=row.get('Title') or row.get('Description') or '';key=core(caption)
  pid=known_urls.get(url_identity(row['Permalink'])) or known_captions.get(key)
  if pid:matched.add(pid)
  identity=hashlib.sha256(key.encode()).hexdigest() if key else platform+':'+row['Post ID']
  group=groups.setdefault(identity,{'source_key':identity,'caption':caption,'sources':[],'catalogue_matches':[]})
  group['sources'].append({'platform':platform,'post_id':row['Post ID'],'url':row['Permalink'],'post_type':row['Post type'],'publish_time':row['Publish time']})
  if pid and pid not in group['catalogue_matches']:group['catalogue_matches'].append(pid)
for group in groups.values():
 text=core(group['caption']);head=text.split('\n')[0][:150]
 if group['catalogue_matches']:bucket='CATALOGUE_COVERED_BY_CURRENT_QUEUE'
 elif re.search(r'\b(?:profile picture|magnolias begin|spring has really sprung|balloon portraits)\b',text):bucket='OTHER_CONTENT_REVIEW'
 elif re.search(r'\b(?:wall (?:relief|sculpture|panel|installation)|relief|sculptural (?:wall|diptych|installation)|sculpture among|garden (?:sculpture|relief)|hand.formed relief)\b',text):bucket='OLDER_SCULPTURE_REVIEW'
 elif re.search(r'\b(?:lamp|table|chair|bowl|mirror|bookend|coaster|tray|cabinet|sconce)\w*\b',head):bucket='FUNCTIONAL_FURNISHING_REVIEW'
 elif re.search(r'\b(?:sculpture|sculptures|cast panels|sculptural panels|spiral|moonshadow|shellmoon)\b',text):bucket='OLDER_SCULPTURE_REVIEW'
 else:bucket='IMAGE_REVIEW_NEEDED'
 group['review_bucket']=bucket
report={'scope':'All sculpture posts requested; older work undergoing source review','export_period':'1 Jan 2026 - 20 Nov 2026',
        'source_post_counts':counts,'distinct_caption_groups':len(groups),'catalogue_ids_found_in_exports':len(matched),
        'catalogue_ids_not_matched_by_source_url_or_caption':sorted(known-matched),
        'review_buckets':{b:sum(g['review_bucket']==b for g in groups.values()) for b in {g['review_bucket'] for g in groups.values()}},
        'groups':list(groups.values()),'status':'OLDER_HISTORY_REVIEW_IN_PROGRESS'}
(OUT/'history-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='groups'},ensure_ascii=False,indent=2))
