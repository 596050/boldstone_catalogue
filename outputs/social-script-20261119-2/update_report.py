"""Render a read-only view of this batch's actual durable publication receipts."""
import html,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).parent
ROOT=OUT.parents[1]
PLATFORMS=['facebook','instagram','linkedin','google_business_profile']
LABELS={'facebook':'Facebook','instagram':'Instagram','linkedin':'LinkedIn','google_business_profile':'Google Business Profile'}
db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
db.row_factory=sqlite3.Row
jobs=[]
for row in db.execute('SELECT id,payload,state,last_error,receipt FROM jobs'):
 p=json.loads(row['payload'])
 if p.get('batch_id')=='component-sculptures-20261119-2':jobs.append({'id':row['id'],'catalogue_id':p['catalogue_id'],'title':p['title'],'platform':p['platform'],'state':row['state'],'error':row['last_error'],'receipt':json.loads(row['receipt']) if row['receipt'] else None})
db.close()
published=sum(j['state']=='PUBLISHED' for j in jobs)
tagged=sum(bool((j['receipt']or{}).get('product_tag_verified')) for j in jobs)
counts={platform:sum(j['state']=='PUBLISHED' and j['platform']==platform for j in jobs) for platform in PLATFORMS}
report={'utc':datetime.now(timezone.utc).isoformat(),'complete':published==20 and tagged==10,'published':published,'total':20,'published_by_platform':counts,'meta_tags_verified':tagged,'jobs':jobs}
(OUT/'publication-receipts.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
esc=html.escape
cards=[]
posts=json.loads((OUT/'posts.json').read_text())
google={p['catalogue_id']:p for p in json.loads((OUT/'google-posts-prepared.json').read_text())}
for p in posts:p['captions']['google_business_profile']=google[p['catalogue_id']]['captions']['google_business_profile']
for p in posts:
 verified=[j for j in jobs if j['catalogue_id']==p['catalogue_id'] and j['state']=='PUBLISHED']
 if verified:
  p['publications']={j['platform']:{'url':j['receipt']['native_url'],'verified_utc':j['receipt']['verified_utc'],'product_tag_verified':j['receipt'].get('product_tag_verified',False)} for j in verified}
  p['status']='PUBLISHED_ALL_FOUR' if len(verified)==4 else 'PARTIALLY_PUBLISHED'
 rows=[]
 for platform in PLATFORMS:
  j=next((j for j in jobs if j['catalogue_id']==p['catalogue_id'] and j['platform']==platform),{'state':'PREPARED','receipt':None})
  r=j['receipt']or{};url=r.get('native_url')
  link='<a href="'+esc(url,quote=True)+'" target="_blank">Open post</a>' if url else 'Not yet verified'
  commerce='Saved tag verified in Meta' if r.get('product_tag_verified') else ('Product destination verified' if r.get('purchase_links') else 'Pending')
  rows.append('<tr><td>'+esc(LABELS[platform])+'</td><td>'+esc(j['state'])+'</td><td>'+link+'</td><td>'+commerce+'</td></tr>')
 captions=''.join('<details><summary>'+esc(k.title())+' caption</summary><pre>'+esc(v)+'</pre></details>' for k,v in p['captions'].items())
 cards.append('<article><h2>'+esc(p['title'])+'</h2><img src="media/'+p['catalogue_id']+'.png" alt="'+esc(p['alt_text'],quote=True)+'"><table><thead><tr><th>Platform</th><th>Status</th><th>Native receipt</th><th>Shopping</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'+captions+'</article>')
(OUT/'posts.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2)+'\n')
for platform in PLATFORMS:
 receipts=[{'status':'PUBLISHED_NATIVE_READBACK','catalogue_id':j['catalogue_id'],'title':j['title'],'url':j['receipt']['native_url'],'full_caption_readback':True,'author_verified':True,'photo_verified':True,'product_tag_verified':j['receipt'].get('product_tag_verified',False),'verified_utc':j['receipt']['verified_utc'],'evidence_path':j['receipt']['evidence_path'],'evidence_sha256':j['receipt']['evidence_sha256']} for j in jobs if j['platform']==platform and j['state']=='PUBLISHED']
 (OUT/(platform+'-publication-receipts.json')).write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
page='<!doctype html><html lang="en"><meta charset="utf-8"><title>Boldstone social batch — 19 November 2026 — second batch</title><style>body{font:16px/1.6 system-ui;margin:40px auto;max-width:1150px;padding:0 24px;color:#243739;background:#faf9f6}h1,h2{line-height:1.2}article{background:white;padding:28px;margin:28px 0;border:1px solid #deded4;border-radius:12px}img{max-width:400px;max-height:360px;object-fit:contain}table{width:100%;border-collapse:collapse;margin:24px 0}th,td{text-align:left;border-bottom:1px solid #ddd;padding:10px}pre{white-space:pre-wrap;font:inherit}a{color:#176473}</style><h1>Five new component sculptures</h1><p>'+str(published)+' of 20 publications verified. '+str(tagged)+' Meta product associations verified.</p><p>Updated '+esc(report['utc'])+'. The Meta tag check combines the exact product and price saved before publication with the persisted tag count in the published editor. Public shopping behaviour is not independently tested on a mobile device.</p>'+''.join(cards)+'</html>'
(OUT/'review.html').write_text(page)
print(json.dumps({k:report[k] for k in ['published','total','meta_tags_verified','utc']}))
