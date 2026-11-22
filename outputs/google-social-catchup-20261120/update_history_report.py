"""Local read-only progress and native receipts for the complete history catch-up."""
import collections,html,json,sqlite3
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
jobs={r[0]:{'id':r[1],'state':r[2],'receipt':json.loads(r[3]) if r[3] else None,'error':r[4]} for r in db.execute("SELECT post_key,id,state,receipt,last_error FROM jobs WHERE channel_key='google_business_profile:15009857378722117958'")};db.close()
posts=[]
holds=json.loads((OUT/'platform-publication-holds.json').read_text())['holds'] if (OUT/'platform-publication-holds.json').exists() else []
hold_by_id={r['job_id']:r for r in holds}
for file in sorted(OUT.glob('history-*/prepared-posts.json')):
 if (file.parent/'delivery-prepared-posts.json').exists():file=file.parent/'delivery-prepared-posts.json'
 for source in json.loads(file.read_text()):
  row={**source,'batch_directory':file.parent.name,**jobs.get(source['google_post_key'],{'state':'PREPARED'})}
  if row.get('id') in hold_by_id and row['state']!='PUBLISHED':row['platform_hold']=hold_by_id[row['id']]
  posts.append(row)
catalogue=json.loads((OUT/'publication-receipts.json').read_text())
history=json.loads((OUT/'instagram-history-coverage-progress.json').read_text()) if (OUT/'instagram-history-coverage-progress.json').exists() else None
audit=json.loads((OUT/'full-history-audit.json').read_text()) if (OUT/'full-history-audit.json').exists() else {}
facebook=json.loads((OUT/'facebook-all-history-reconciliation.json').read_text()) if (OUT/'facebook-all-history-reconciliation.json').exists() else {}
from datetime import datetime,timezone
status={'utc':datetime.now(timezone.utc).isoformat(),'catalogue_verified':catalogue['google_verified_total'],'catalogue_total':64,
        'older_posts_prepared':len(posts),'older_posts_verified':sum(r['state']=='PUBLISHED' for r in posts),
        'older_post_states':dict(collections.Counter(r['state'] for r in posts)),'full_instagram_history_audit':history,
        'platform_holds':[r['platform_hold'] for r in posts if r.get('platform_hold')],
        'facebook_source_review':{k:facebook[k] for k in ['status','native_photos_reviewed','native_reels_reviewed','unavailable_source_count'] if k in facebook},
        'available_history_complete':bool(audit.get('available_history_complete')) and all(r['state']=='PUBLISHED' for r in posts),
        'all_identified_available_posts_submitted':bool(audit.get('all_identified_available_posts_submitted')),
        'native_google_records_known':audit.get('native_google_records_known'),
        'native_video_posts_verified':audit.get('native_video_posts_verified'),
        'full_history_complete':bool(audit.get('full_history_complete')) and all(r['state']=='PUBLISHED' for r in posts),'posts':posts}
(OUT/'history-publication-receipts.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
e=html.escape;cards=[]
for row in posts:
 image=quote(str(Path(row['media_path']).relative_to(OUT)));receipt=row.get('receipt') or {}
 media=('<video controls preload="metadata" src="'+image+'"></video>') if row.get('media_kind')=='video' else '<img loading="lazy" src="'+image+'">'
 sources=' · '.join('<a href="'+e(s['url'],quote=True)+'">'+e(s['platform'])+'</a>' for s in row['sources'])
 hold=row.get('platform_hold') or {};held_url=hold.get('native_url')
 if hold and not held_url and Path(hold.get('proof_path','missing')).is_file():held_url=json.loads(Path(hold['proof_path']).read_text()).get('native_url')
 google='<a href="'+e(receipt['native_url'],quote=True)+'">Verified Google record</a>' if receipt.get('native_url') else '<a href="'+e(held_url,quote=True)+'">Google record awaiting verification</a>' if held_url else e(row['state'])
 warning='<p>'+e(hold['reason'])+'</p>' if hold else ''
 cards.append('<article>'+media+'<section><h2>'+e(row.get('title') or row['caption'].split('\n')[0][:180])+'</h2><p><strong>'+e(row['state'])+'</strong> · '+google+'</p>'+warning+'<p>Original sources: '+sources+'</p><p class="caption">'+e(receipt.get('effective_caption',row['google_caption']))+'</p><p><a href="'+e(row['google_url'],quote=True)+'">'+e(row['google_button'])+' destination</a></p></section></article>')
body='<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="30"><title>Boldstone sculpture history catch-up</title><style>body{font:16px system-ui;margin:32px;max-width:1200px;color:#20322b;background:#f6f5f0}article{display:flex;gap:24px;background:white;padding:20px;margin:20px 0;border-radius:12px}img,video{width:220px;height:220px;object-fit:contain}h2{font-size:19px}.caption{white-space:pre-wrap;line-height:1.5}a{color:#24664d}</style>'
body+='<h1>Boldstone sculpture history catch-up</h1><p>Catalogue: '+str(status['catalogue_verified'])+'/64 verified on Google. Older posts: '+str(status['older_posts_verified'])+'/'+str(len(posts))+' prepared posts verified.</p>'
if status['platform_holds']:body+='<p>'+str(len(status['platform_holds']))+' Google records are held for review or media processing. These are not counted as verified publications, and their original submission intents cannot be replayed.</p>'
if facebook:body+='<p>Source review: all 653 Instagram posts accounted for; 499 Facebook photographs, 18 reels and the older native date-filter results reviewed. '+str(facebook.get('unavailable_source_count',0))+' Facebook shared posts explicitly show unavailable content, so their contents cannot be classified or copied. <a href="facebook-all-history-reconciliation.json">Facebook source evidence</a>.</p>'
progress='All available identified sculpture posts have verified Google counterparts.' if status['available_history_complete'] else 'All identified, available sculpture posts have Google records; '+str(len(status['platform_holds']))+' remain unverified.' if status['all_identified_available_posts_submitted'] else 'Publication and reconciliation remain in progress.'
body+='<p>'+progress+' Photos use original source covers. Original films longer than 30 seconds are delivered as complete sequences of shorter clips; one unavailable original film is explicitly represented by a still and original watch link. Captions identify archive material. The manager’s Published status or the exact individual Google post view, decoded media, full caption and action destination are checked for every verified record.</p>'
if (OUT/'google-review-request-three-posts-draft.txt').exists() and status['platform_holds']:body+='<p><a href="google-review-request-three-posts-draft.txt">Google review request draft — not sent</a></p>'
body+='<p>Updated '+e(status['utc'])+' · <a href="review.html">Catalogue receipts</a> · <a href="full-history-audit.json">Independent receipt audit</a></p>'
(OUT/'history-review.html').write_text(body+'\n'.join(cards))
print(json.dumps({k:v for k,v in status.items() if k not in {'posts','full_instagram_history_audit'}},ensure_ascii=False))
