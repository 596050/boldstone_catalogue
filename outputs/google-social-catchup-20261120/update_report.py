"""Read-only progress and coverage for the Google sculpture catch-up."""
import html,json,os,sqlite3
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
coverage=json.loads((OUT/'coverage-inventory.json').read_text())
prepared={p['catalogue_id']:p for p in json.loads((OUT/'prepared-posts.json').read_text())}
db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
jobs={}
for job_id,payload,state,error,receipt in db.execute('SELECT id,payload,state,last_error,receipt FROM jobs'):
 p=json.loads(payload)
 if p['platform']=='google_business_profile' and p['catalogue_id'] in {r['catalogue_id'] for r in coverage['sculptures']}:
  jobs[p['catalogue_id']]={'job_id':job_id,'state':state,'error':error,'payload':p,'receipt':json.loads(receipt) if receipt else None}
db.close()
published=sum(j['state']=='PUBLISHED' for j in jobs.values())
new_published=sum(j['state']=='PUBLISHED' and j['payload']['batch_id']=='google-social-catchup-20261120' for j in jobs.values())
audit=json.loads((OUT/'history-audit.json').read_text()) if (OUT/'history-audit.json').exists() else {'status':'IN_PROGRESS'}
report={'utc':datetime.now(timezone.utc).isoformat(),'target_sculptures':coverage['distinct_meta_sculptures'],
        'already_google_before_catchup':coverage['already_google'],'new_posts_requested':coverage['missing_google'],
        'google_verified_total':published,'new_google_posts_verified':new_published,'remaining_google_posts':coverage['distinct_meta_sculptures']-published,
        'publication_complete':published==coverage['distinct_meta_sculptures'],'history_audit':audit,
        'states':dict(Counter(j['state'] for j in jobs.values())),
        'posts':[{**r,**{k:v for k,v in jobs.get(r['catalogue_id'],{}).items() if k!='payload'}} for r in coverage['sculptures']]}
(OUT/'publication-receipts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
esc=html.escape;cards=[]
for row in sorted(coverage['sculptures'],key=lambda r:r['title']):
 pid=row['catalogue_id'];job=jobs.get(pid,{});receipt=job.get('receipt') or {};p=prepared.get(pid) or job.get('payload',{})
 url=receipt.get('native_url');media=p.get('media_path');caption=p.get('captions',{}).get('google_business_profile') or p.get('caption','')
 thumbnail=OUT/'thumbnails'/(pid+'.png')
 display=str(thumbnail) if thumbnail.exists() else media
 image='<img loading="lazy" src="'+esc(os.path.relpath(display,OUT),quote=True)+'" alt="'+esc(p.get('alt_text',row['title']),quote=True)+'">' if display else ''
 google='<a href="'+esc(url,quote=True)+'">Open Google post record</a>' if url else 'Awaiting verified Google record'
 sources=[]
 for platform in ['facebook','instagram']:
  links=sorted({s['url'] for s in row['meta_sources'] if s['platform']==platform})
  sources.extend('<a href="'+esc(url,quote=True)+'">'+esc(platform.title())+' source</a>' for url in links)
 shop='Published status, photo, description and Buy link verified' if receipt.get('purchase_links') else 'Pending native readback'
 cards.append('<article><h2>'+esc(row['title'])+'</h2>'+image+'<p><strong>'+esc(job.get('state',row['status']))+'</strong> · '+google+'</p><p>'+shop+'</p><p>'+' · '.join(sources)+'</p><details><summary>Google description</summary><pre>'+esc(caption)+'</pre></details></article>')
page='<!doctype html><html lang="en"><meta charset="utf-8"><title>Boldstone Google sculpture catch-up</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;background:#faf9f5;color:#243739}article{background:#fff;border:1px solid #ddd;padding:24px;margin:24px 0;border-radius:10px}img{max-width:360px;max-height:320px;object-fit:contain}a{color:#176473}pre{font:inherit;white-space:pre-wrap}h1,h2{line-height:1.2}</style><h1>Google sculpture catch-up</h1><p><strong>'+str(published)+' of '+str(coverage['distinct_meta_sculptures'])+' sculptures verified on Google.</strong> '+str(new_published)+' new catch-up posts; '+str(coverage['already_google'])+' already verified before this batch.</p><p>Updated '+esc(report['utc'])+'. Facebook and Instagram copies are matched by catalogue identity and posted to Google once. Google links open the unique managed post record. Larger source photographs have proportional Google-size copies; originals are retained.</p>'+''.join(cards)+'</html>'
if not report['publication_complete']:page=page.replace('<meta charset="utf-8">','<meta charset="utf-8"><meta http-equiv="refresh" content="30">')
(OUT/'review.html').write_text(page)
print(json.dumps({k:report[k] for k in ['google_verified_total','target_sculptures','new_google_posts_verified','remaining_google_posts','states']}))
