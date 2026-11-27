from pathlib import Path
from collections import Counter
import json,html
OUT=Path(__file__).resolve().parent
def read(name,default=None):
 p=OUT/name
 return json.loads(p.read_text()) if p.exists() else default
def h(v):return html.escape(str(v))
css='body{font:16px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;color:#26352e;background:#f7f8f3;margin:0}main{max-width:1120px;margin:auto;padding:30px 24px}h1,h2,h3{line-height:1.2}h1{font-size:32px}a{color:#205e49}p{max-width:900px}.muted{color:#56675f}nav{display:flex;gap:20px;flex-wrap:wrap;margin:20px 0}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #d9e2d8;vertical-align:top}.card{background:white;padding:20px;border:1px solid #d9e2d8;border-radius:10px;margin:20px 0}.photo{display:grid;grid-template-columns:220px 1fr;gap:24px}img{width:100%;height:280px;object-fit:contain;background:#f1f2ec}textarea{box-sizing:border-box;width:100%;height:180px;font:14px/1.4 monospace;padding:12px;border:1px solid #bac9bf;border-radius:5px}summary{cursor:pointer;padding:10px 0;font-weight:600}.warning{padding:12px;background:#fff0c8;border-radius:6px}@media(max-width:720px){.photo{display:block}td,th{padding:7px;font-size:13px}}'
posts=read('posts.json')['posts'];pub=max([read('publication-results.json',{'utc':'','results':[]}),read('publication-progress.json',{'utc':'','results':[]})],key=lambda d:d['utc'])['results'];drafts=read('native-draft-results.json',{'drafts':[]})['drafts']
pubmap={(r['post_key'],r['profile_id']):r for r in pub};draftmap={(r['post_key'],r['profile_id']):r for r in drafts}
def published(row):
 if not row:return 'In progress'
 label='Published · verified' if row['state']=='PUBLISHED' else 'Submitted · awaiting Google review' if row['state']=='OUTCOME_UNKNOWN' and row['profile_id']=='boldstone_google_business_profile' else row['state'].replace('_',' ').title()
 url=(row.get('receipt') or {}).get('native_url') or (row.get('native_pending_record') or {}).get('native_url')
 return '<a href="'+h(url)+'">'+h(label)+'</a>' if url else h(label)
def drafted(row):
 if not row:return 'In progress'
 if row['state']=='PREPARED_NOT_PUBLISHED':return 'Prepared · ready for review'
 if row['state']=='PREPARED_REQUIRES_CROP_REVIEW':return 'Prepared · framing review needed'
 return 'Held · '+h(row.get('code',row['state']))
review=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone · 27 November sculpture batch</title><style>'+css+'</style><main><p class="muted">BOLDSTONE · 27 NOVEMBER 2026</p><h1>Five more sculpture posts</h1><p>LinkedIn: Sally Price. Google: Boldstone Business Profile. Facebook + Instagram: five shared draft composers. Threads: five separate draft composers. Browser work is confined to reserved background tabs.</p><table><thead><tr><th>Sculpture</th><th>LinkedIn</th><th>Google</th><th>Facebook + Instagram</th><th>Threads</th></tr></thead><tbody>']
for post in posts:
 key=post['post_key'];review.append('<tr><td>'+h(post['title'])+'</td><td>'+published(pubmap.get((key,'sally_linkedin')))+'</td><td>'+published(pubmap.get((key,'boldstone_google_business_profile')))+'</td><td>'+drafted(draftmap.get((key,'boldstone_facebook')))+'</td><td>'+drafted(draftmap.get((key,'boldstone_threads')))+'</td></tr>')
review.append('</tbody></table><h2>Photographs and copy</h2>')
for post in posts:
 image=Path(post['media_path']).relative_to(OUT).as_posix();meta=draftmap.get((post['post_key'],'boldstone_facebook'),{})
 review.append('<article class="card photo"><div><a href="'+h(image)+'"><img src="'+h(image)+'" alt="'+h(post['alt_text'])+'"></a><p>£'+format(post['price_gbp'],'.2f')+'<br>'+h(post['dimensions'])+'<br><a href="'+h(post['website_url'])+'">Product page</a></p></div><div><h3>'+h(post['title'])+'</h3>')
 if meta.get('crop_warning'):review.append('<p class="warning">'+h(meta['crop_warning'])+'</p>')
 for label,key in [('Facebook + Instagram','facebook'),('Threads','threads'),('LinkedIn','linkedin'),('Google','google_business_profile')]:review.append('<details><summary>'+label+' copy</summary><textarea readonly aria-label="'+h(label+' '+post['title'])+'">'+h(post['captions'][key])+'</textarea></details>')
 review.append('</div></article>')
review.append('<p class="muted"><a href="publication-results.json">Publication receipts</a> · <a href="native-draft-results.json">Draft checks</a> · <a href="final-audit.json">Final validation</a> · <a href="background-audit.json">Background checks</a></p></main></html>')
(OUT/'review.html').write_text(''.join(review))
print(json.dumps({'review':str(OUT/'review.html'),'publication_states':dict(Counter(r['state'] for r in pub)),'draft_count':len(drafts)}))
