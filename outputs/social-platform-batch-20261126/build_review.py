"""Create a local review pack from recorded platform outcomes and frozen copy."""
from pathlib import Path
from collections import Counter
import json,html
OUT=Path(__file__).resolve().parent
def read(name,default=None):
 p=OUT/name
 return json.loads(p.read_text()) if p.exists() else default
def h(value):return html.escape(str(value))
posts=read('posts.json')['posts'];design=read('design-platform-drafts.json')
access=read('design-platform-status.json',{'platforms':[]})
byplatform={r['platform']:r for r in access['platforms']}
pack=OUT/'design-drafts';pack.mkdir(exist_ok=True)
for draft in design['drafts']:
 status=byplatform.get(draft['platform'],{})
 draft['status']='CONTENT_PREPARED_ACCOUNT_ACTION_REQUIRED'
 draft['native_draft_created']=False
 draft['account_blocker']=status.get('blocker','Account publishing access must be completed.')
 target=pack/draft['platform'].lower();target.mkdir(exist_ok=True)
 text=(draft['title']+'\n\n'+draft['description']+'\n\n'+
       'Price: £'+format(draft['price_gbp'],'.2f')+'\nSKU: '+draft['sku']+'\n\n'+
       'Photo: '+draft['media_path']+'\nAlt text: '+draft['alt_text']+'\n')
 (target/(draft['catalogue_id']+'.txt')).write_text(text)
 (target/(draft['catalogue_id']+'.json')).write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n')
(OUT/'design-platform-drafts.json').write_text(json.dumps(design,ensure_ascii=False,indent=2)+'\n')
pub=max([read('publication-results.json',{'utc':'','results':[]}),read('publication-progress.json',{'utc':'','results':[]})],key=lambda x:x['utc'])['results']
drafts=read('native-draft-results.json',{'drafts':[]})['drafts']
pubmap={(r['post_key'],r['profile_id']):r for r in pub}
draftmap={(r['post_key'],r['profile_id']):r for r in drafts}
counts=Counter(r['state'] for r in pub)
lines=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
 '<title>Boldstone · 26 November sculpture posts</title>',
 '<style>body{font:16px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;color:#25332f;background:#f7f7f2;margin:0}main{max-width:1100px;margin:auto;padding:32px 24px}h1,h2,h3{line-height:1.2}h1{font-size:32px}.muted{color:#53645d}a{color:#215d4a}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #dce1da;vertical-align:top}article{display:grid;grid-template-columns:220px 1fr;gap:26px;background:white;border:1px solid #dce1da;border-radius:12px;padding:22px;margin:24px 0}img{width:100%;height:300px;object-fit:contain;background:#f3f3ef}textarea{box-sizing:border-box;width:100%;height:190px;font:14px/1.4 monospace;border:1px solid #bac7bf;border-radius:6px;padding:12px}summary{cursor:pointer;padding:10px 0;font-weight:600}.pill{display:inline-block;background:#e9f1e9;border-radius:5px;padding:3px 8px}.warning{background:#fff3ce;padding:12px;border-radius:6px}.accounts{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.account{padding:18px;background:white;border:1px solid #dce1da;border-radius:8px}@media(max-width:750px){article,.accounts{display:block}article img{height:240px}.account{margin:12px 0}th,td{padding:8px;font-size:14px}}</style><main>',
 '<p class="muted">BOLDSTONE · 26 NOVEMBER 2026</p><h1>Five new sculpture posts</h1>',
 '<p>LinkedIn: Sally Price. Google: Boldstone Business Profile. Facebook, Instagram and Threads: prepared for review in retained background tabs.</p>',
 '<p class="pill">'+h(str(counts.get('PUBLISHED',0)))+' verified publications</p>',
 '<table><thead><tr><th>Sculpture</th><th>LinkedIn</th><th>Google</th><th>Facebook + Instagram</th><th>Threads</th></tr></thead><tbody>']
def publication_cell(row):
 if not row:return 'Awaiting worker'
 state=row['state'];url=(row.get('receipt') or {}).get('native_url')
 label='Published · verified' if state=='PUBLISHED' else 'Submitted · Google review pending' if state=='OUTCOME_UNKNOWN' and row['profile_id']=='boldstone_google_business_profile' else state.replace('_',' ').title()
 return '<a href="'+h(url)+'">'+h(label)+'</a>' if url else h(label)
def draft_label(row):
 if not row:return 'Awaiting preparation'
 if row['state']=='PREPARED_NOT_PUBLISHED':return 'Prepared · ready for review'
 if row['state']=='PREPARED_REQUIRES_CROP_REVIEW':return 'Prepared · framing review needed'
 return 'Held · '+h(row.get('code',row['state']))
for post in posts:
 key=post['post_key']
 lines.append('<tr><td>'+h(post['title'])+'</td><td>'+publication_cell(pubmap.get((key,'sally_linkedin')))+'</td><td>'+publication_cell(pubmap.get((key,'boldstone_google_business_profile')))+'</td><td>'+draft_label(draftmap.get((key,'boldstone_facebook')))+'</td><td>'+draft_label(draftmap.get((key,'boldstone_threads')))+'</td></tr>')
lines.append('</tbody></table><h2>Design platforms</h2><p>Five copy-and-photo entries are prepared for each platform. Native publishing access is still gated by the account steps below.</p><div class="accounts">')
for platform in ['Archiproducts','Architonic','Archilovers']:
 row=byplatform.get(platform,{})
 lines.append('<div class="account"><h3>'+platform+'</h3><p>'+h(row.get('account_status','Access checked'))+'</p><p>'+h(row.get('blocker','Account action required'))+'</p><p>'+h(row.get('prepared_native_state','Background account page retained.'))+'</p></div>')
lines.append('</div><h2>Photographs and prepared copy</h2>')
for post in posts:
 image=Path(post['media_path']).relative_to(OUT).as_posix();key=post['post_key'];meta=draftmap.get((key,'boldstone_facebook'),{})
 lines.append('<article><div><a href="'+h(image)+'"><img src="'+h(image)+'" alt="'+h(post['alt_text'])+'"></a><p><a href="'+h(post['website_url'])+'">Product page</a><br>£'+format(post['price_gbp'],'.2f')+'<br>'+h(post['dimensions'])+'</p></div><div><h3>'+h(post['title'])+'</h3>')
 if meta.get('crop_warning'):lines.append('<p class="warning">'+h(meta['crop_warning'])+'</p>')
 for label,text in [('Facebook + Instagram',post['captions']['facebook']),('Threads',post['captions']['threads']),('LinkedIn',post['captions']['linkedin']),('Google',post['captions']['google_business_profile'])]:
  lines.append('<details><summary>'+label+' copy</summary><textarea readonly aria-label="'+h(label+' '+post['title'])+'">'+h(text)+'</textarea></details>')
 for platform in ['Archiproducts','Architonic','Archilovers']:
  draft=next(r for r in design['drafts'] if r['platform']==platform and r['catalogue_id']==key)
  rel='design-drafts/'+platform.lower()+'/'+key+'.txt'
  lines.append('<details><summary>'+platform+' prepared entry</summary><textarea readonly aria-label="'+h(platform+' '+post['title'])+'">'+h(draft['title']+'\n\n'+draft['description'])+'</textarea><a href="'+h(rel)+'">Open full entry with price, SKU and photo path</a></details>')
 lines.append('</div></article>')
lines.append('<p class="muted">Verification records: <a href="publication-results.json">publication receipts</a> · <a href="native-draft-results.json">draft checks</a> · <a href="design-platform-status.json">account gates</a> · <a href="background-audit.json">background audit</a></p></main></html>')
(OUT/'review.html').write_text(''.join(lines))
print(json.dumps({'review':str(OUT/'review.html'),'design_entries':len(design['drafts']),'publication_counts':dict(counts)},ensure_ascii=False))
