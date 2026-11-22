"""Reconcile actual native album parent links with reviewed source and Google records."""
import collections,json,sys
from pathlib import Path
from urllib.parse import urlparse,parse_qs
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
# Use the exact normalization used by the original source audit, without importing it.
import re,unicodedata
def norm(s):
 s=re.sub(r'https?://\S+','',s);s=re.sub(r'#\w+','',s);s=re.sub(r'(?i)\bsee (?:less|more)\s*$','',s)
 return ' '.join(unicodedata.normalize('NFKC',s).casefold().replace('\u200b','').replace('\ufeff','').split()).rstrip(' .…')
def canon(s):
 p=urlparse(s)
 if p.path in ['/photo.php','/photo/']:return 'facebook-photo:'+parse_qs(p.query).get('fbid',[''])[0]
 return 'https://www.facebook.com'+p.path.rstrip('/')
groups=json.loads((OUT/'history-audit.json').read_text())['groups'];sources={};bycaption=collections.defaultdict(set);byurl=collections.defaultdict(set);byid=collections.defaultdict(set)
for r in groups:
 sources[r['source_key']]=r
 if norm(r['caption']):bycaption[norm(r['caption'])].add(r['source_key'])
 for s in r['sources']:
  if s['platform']=='facebook':byurl[canon(s['url'])].add(r['source_key']);byid[str(s['post_id'])].add(r['source_key'])
photos=json.loads((OUT/'facebook-native-photo-history.json').read_text());parents={r['photo_id']:r for r in json.loads((OUT/'facebook-native-photo-parent-records.json').read_text())};manual={r['photo_id']:r['meta_source_key'] for r in json.loads((OUT/'facebook-album-photo-associations.json').read_text())['associations']}
visual={r['photo_id']:r for r in json.loads((OUT/'facebook-photo-review-decisions.json').read_text())['decisions']};pairs={r['photo_id']:r for r in json.loads((OUT/'facebook-paired-photo-visual-confirmation.json').read_text())['confirmations']}
prepared=[]
for f in OUT.glob('history-*/prepared-posts.json'):
 if (f.parent/'delivery-prepared-posts.json').exists():f=f.parent/'delivery-prepared-posts.json'
 prepared+=json.loads(f.read_text())
keys=collections.defaultdict(set)
for r in prepared:keys[r['source_key']].add(r['google_post_key'])
# The catalogue records are keyed by their immutable catalogue IDs.
import sqlite3
c=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True);catalogue={}
for raw, in c.execute("SELECT payload FROM jobs WHERE channel_key='google_business_profile:15009857378722117958'"):
 r=json.loads(raw);catalogue[r['catalogue_id']]=r['post_key']
c.close()
for r in groups:
 for k in r['catalogue_matches']:
  if k in catalogue:keys[r['source_key']].add(catalogue[k])
parentkeys=collections.defaultdict(set);parentgroups=collections.defaultdict(set);rows=[]
for r in photos:
 group=set(bycaption[norm(r['caption'])] if norm(r['caption']) else [])|byurl[r['canonical_parent']]|byid[r['photo_id']]
 if r['photo_id'] in manual:group.add(manual[r['photo_id']])
 native=parents.get(r['photo_id']);parent=canon(native['parent_post_url']) if native and native['parent_post_url'] else r['canonical_parent']
 group|=byurl[parent];google=set(pairs.get(r['photo_id'],{}).get('google_post_keys',[]))|set(visual.get(r['photo_id'],{}).get('google_post_keys',[]))
 for k in group:google|=keys[k]
 parentgroups[parent]|=group;parentkeys[parent]|=google
 rows.append({'photo_id':r['photo_id'],'native_parent':parent,'native_parent_verified':bool(native),'source_group_keys':sorted(group),'google_post_keys':sorted(google),'caption':r['caption'],'date':r['date']['text'],'scope_review':visual.get(r['photo_id'],{}).get('decision'),'evidence_path':native.get('evidence_path') if native else r['evidence_path'],'evidence_sha256':native.get('evidence_sha256') if native else r['evidence_sha256']})
for row in rows:
 row['source_group_keys']=sorted(parentgroups[row['native_parent']]);row['google_post_keys']=sorted(parentkeys[row['native_parent']]);row['excluded']=row['scope_review']=='EXCLUDE_NON_SCULPTURE'
 if not row['excluded'] and row['source_group_keys']:
  row['excluded']=all(not keys[k] for k in row['source_group_keys'])
 row['coverage_status']='EXCLUDED_NON_SCULPTURE' if row['excluded'] else 'GOOGLE_COUNTERPART_IDENTIFIED' if row['google_post_keys'] else 'REVIEW_REQUIRED'
missing=[r for r in rows if r['coverage_status']=='REVIEW_REQUIRED']
atomic_json(OUT/'facebook-photo-parent-reconciliation.json',{'utc':utc(),'native_photo_count':len(rows),'native_album_parent_records':len(parents),'all_album_parent_links_read':len(parents)==len(rows),'unresolved_photo_count':len(missing),'rows':rows})
print(json.dumps({'native_photos':len(rows),'parents_read':len(parents),'coverage_counts':dict(collections.Counter(r['coverage_status'] for r in rows)),'unresolved':[(r['photo_id'],r['date'],r['caption'][:50]) for r in missing[:25]]}))
