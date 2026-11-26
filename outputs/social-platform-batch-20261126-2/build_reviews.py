"""Write the batch review and a sourced comparison of five additional platforms."""
from pathlib import Path
from collections import Counter
import json,html
OUT=Path(__file__).resolve().parent
def read(name,default=None):
 p=OUT/name
 return json.loads(p.read_text()) if p.exists() else default
def h(v):return html.escape(str(v))
platforms=[
 {'name':'Pinterest','priority':1,'url':'https://business.pinterest.com/en-gb/how-to-make-pins/','format':'Static image Pins linked to individual sculpture pages.',
  'confirmed':'Pins can contain images and link directly to a website. Organic content can be published free; product feeds and scheduling are also supported.',
  'fit':'First choice for reusing sculpture photographs as visual inspiration and sending interested viewers to the product page. This is a recommendation based on the format, not a measured Boldstone conversion result.',
  'example':'One original sculpture image, a specific title such as White botanical wall relief, a short description and the exact product-page link. Group into boards for wall reliefs and garden sculpture.',
  'gate':'Account access and website/catalogue setup need checking before publication; an ordinary Pin can already carry a website link.'},
 {'name':'Homify','priority':2,'url':'https://www.homify.co.uk/signup_expert','format':'A professional presence showing sculpture and installation photography.',
  'confirmed':'Homify offers a professional directory and a free registration route; Premium is separately promoted. Its own professional page addresses architects, design businesses and potential customers.',
  'fit':'The closest additional fit to Houzz in this shortlist. Present Boldstone as a source of reliefs and water features for home and garden projects.',
  'example':'Use real installation photographs, with product details and captions identifying exactly what is supplied. Keep an individual product image distinct from a completed client project.',
  'gate':'The professional category, account access and available portfolio tools need checking. Confirm any Premium terms before choosing paid visibility.'},
 {'name':'Behance','priority':3,'url':'https://help.behance.net/hc/en-us/articles/204483684-Guide-Create-Publish-A-Project','format':'Image-led portfolio projects with descriptions, cover images and creative fields.',
  'confirmed':'Projects support uploaded files and text, a title, cover image, creative fields and tags. Work can be saved as a draft or published. The editor does not auto-save.',
  'fit':'Suitable for showing Sally Price’s sculptural design language and related series to a creative professional audience. Treat each entry as a portfolio story.',
  'example':'A single cohesive project about botanical reliefs or lunar forms, with original photographs, close-ups, materials and dimensions, rather than five near-identical sales captions.',
  'gate':'Account access needs checking. Preserve drafts explicitly, and choose project fields that truthfully describe sculpture or product design.'},
 {'name':'ArtMajeur','priority':4,'url':'https://www.artmajeur.com/en/sell-art-online','sources':['https://www.artmajeur.com/en/artmajeur-for-artists','https://www.artmajeur.com/en/artmajeur-for-interior-designers'],
  'format':'Artist gallery and individual sculpture listings.',
  'confirmed':'The platform supports sculpture, offers an artist gallery route and has a dedicated service for interior designers and architects sourcing artworks.',
  'fit':'A relevant route for reaching art buyers as well as designers. This is artwork discovery and catalogue presentation, with a sales workflow if enabled.',
  'example':'Create a sculpture entry with original photographs, dimensions, material, an accurate sale unit and documented edition details where requested.',
  'gate':'Check current commission/plan terms and listing eligibility. Artwork year, edition and provenance must come from evidence; those details are not established for this social batch.'},
 {'name':'Saatchi Art','priority':5,'url':'https://www.saatchiart.com/whysell','format':'Artist portfolio and sculpture listings, including multiple views.',
  'confirmed':'Sculpture is supported, and the platform describes art-advisory access to designers and architects. Its current seller route requires an application with three sample works, approval and verification. It states a 40% commission on original-art sales.',
  'fit':'A secondary option for selected artworks and commissions, with more setup and a different sales margin from ordinary social posting.',
  'example':'Use a carefully documented selection with several views, precise dimensions and truthful original/edition information.',
  'gate':'Complete the artist application and verification, confirm the works meet listing rules, and review pricing for the stated commission before enabling sales.'}]
(OUT/'additional-platforms.json').write_text(json.dumps({'checked_date':'2026-11-26','scope':'Five additional platforms for Boldstone static content; research only','ranking_basis':'Fit to sculpture imagery, interior/design audiences, website referrals and practical publishing format; not measured traffic or conversion.','platforms':platforms},ensure_ascii=False,indent=2)+'\n')
css='body{font:16px/1.5 -apple-system,BlinkMacSystemFont,sans-serif;color:#26352e;background:#f7f8f3;margin:0}main{max-width:1120px;margin:auto;padding:30px 24px}h1,h2,h3{line-height:1.2}h1{font-size:32px}a{color:#205e49}p{max-width:900px}.muted{color:#56675f}nav{display:flex;gap:20px;flex-wrap:wrap;margin:20px 0}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #d9e2d8;vertical-align:top}.card{background:white;padding:20px;border:1px solid #d9e2d8;border-radius:10px;margin:20px 0}.photo{display:grid;grid-template-columns:220px 1fr;gap:24px}img{width:100%;height:280px;object-fit:contain;background:#f1f2ec}textarea{box-sizing:border-box;width:100%;height:180px;font:14px/1.4 monospace;padding:12px;border:1px solid #bac9bf;border-radius:5px}summary{cursor:pointer;padding:10px 0;font-weight:600}.warning{padding:12px;background:#fff0c8;border-radius:6px}@media(max-width:720px){.photo{display:block}td,th{padding:7px;font-size:13px}}'
brief=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone · Five additional static-content platforms</title><style>'+css+'</style><main>',
 '<p class="muted">BOLDSTONE · CHECKED 26 NOVEMBER 2026</p><h1>Five additional platforms for static content</h1><nav><a href="#overview">Overview</a><a href="#platforms">Platforms</a><a href="#guidance">Guidance</a><a href="#sources">Sources</a></nav>',
 '<section id="overview"><h2>Overview</h2><p>Prioritise Pinterest for linked image discovery and Homify for a professional interiors presence. Use Behance for cohesive portfolio projects. ArtMajeur and Saatchi Art are artwork-listing routes with additional commercial setup.</p><p>Boldstone’s current material includes original sculpture photographs, verified product links, dimensions and gypsum-based material descriptions. The recommendations below assess fit to those assets; account access and performance on these five services have not been tested.</p></section>',
 '<section id="platforms"><h2>Platforms</h2><table><thead><tr><th>Priority</th><th>Platform</th><th>Static format</th><th>Setup consideration</th></tr></thead><tbody>']
for p in platforms:brief.append('<tr><td>'+str(p['priority'])+'</td><td><a href="'+h(p['url'])+'">'+h(p['name'])+'</a></td><td>'+h(p['format'])+'</td><td>'+h(p['gate'])+'</td></tr>')
brief.append('</tbody></table>')
for p in platforms:
 brief.append('<article class="card"><h3>'+h(p['name'])+'</h3><p><strong>Verified capability:</strong> '+h(p['confirmed'])+' <a href="'+h(p['url'])+'">Official source</a></p><p><strong>Recommendation for Boldstone:</strong> '+h(p['fit'])+'</p><p><strong>Suggested content:</strong> '+h(p['example'])+'</p></article>')
brief.append('</section><section id="guidance"><h2>Guidance</h2><p>Reuse the original photography and product facts, then adapt the presentation to the destination. Pins need a useful destination link; portfolio projects need a coherent story; artwork listings need accurate sales and edition details. Give individual panels their own descriptions and make companion pieces and background settings clear.</p><p>Begin with Pinterest and Homify. Assess artwork-marketplace eligibility and margins before investing time in sale listings. This research does not establish a current Boldstone account on any of the five services.</p></section><section id="sources"><h2>Sources</h2><p>Official platform pages checked on 26 November 2026. User instructions and the current catalogue establish the Boldstone use case. CRM, internal messaging and meeting records were not needed for this comparison. Platform fit and ordering are recommendations; no audience-size or revenue forecast is claimed.</p><ul>')
for p in platforms:
 for url in [p['url']]+p.get('sources',[]):brief.append('<li><a href="'+h(url)+'">'+h(p['name']+' — '+url)+'</a></li>')
brief.append('</ul></section><p><a href="review.html">Open the sculpture-posting review</a></p></main></html>')
(OUT/'additional-platforms.html').write_text(''.join(brief))
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
review=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone · 26 November second sculpture batch</title><style>'+css+'</style><main><p class="muted">BOLDSTONE · 26 NOVEMBER 2026 · SECOND BATCH</p><h1>Five more sculpture posts</h1><p>LinkedIn: Sally Price. Google: Boldstone Business Profile. Facebook + Instagram: five shared draft composers. Threads: five separate draft composers. Browser work is confined to reserved background tabs.</p><p><a href="additional-platforms.html">Five additional platforms: sourced comparison and recommendations</a></p><table><thead><tr><th>Sculpture</th><th>LinkedIn</th><th>Google</th><th>Facebook + Instagram</th><th>Threads</th></tr></thead><tbody>']
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
print(json.dumps({'review':str(OUT/'review.html'),'recommendations':str(OUT/'additional-platforms.html'),'publication_states':dict(Counter(r['state'] for r in pub)),'draft_count':len(drafts)}))
