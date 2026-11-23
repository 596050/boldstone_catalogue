from pathlib import Path
import json,html
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
posts=json.loads((OUT/'posts.json').read_text())['posts']
plan=json.loads((OUT/'tab-plan.json').read_text());bindings={(r['profile_id'],r['post_key']):r for r in plan['bindings']}
proofs={}
for directory in [OUT/'tabs',ROOT/'social-publisher/state/drafts/component-sculptures-drafts-20261123-remaining-d10b634f']:
 for f in directory.glob('*/preparation-result.json'):
  p=json.loads(f.read_text());proofs[(p['profile_id'],p['post_key'])]={**p,'proof_path':str(f)}
ready=sum(p['state']=='PREPARED_NOT_PUBLISHED' for p in proofs.values())
sections=[]
for i,p in enumerate(posts,1):
 tabs=[]
 for platform in ['facebook','instagram','threads']:
  name='boldstone_'+platform;k=(name,p['post_key']);proof=proofs.get(k,{});b=bindings[k];status='Ready for review' if proof.get('state')=='PREPARED_NOT_PUBLISHED' else 'Preparation in progress'
  tabs.append(f'<section class="platform"><h3>{platform.title()} <span>{html.escape(status)}</span></h3><p>Chrome tab {b["tab_id"]} · window {b["window_id"]}</p><textarea readonly aria-label="{platform.title()} caption">{html.escape(p["captions"][platform])}</textarea><button type="button" onclick="copyCaption(this)">Copy caption</button></section>')
 sections.append(f'<article><div class="photo"><img src="media/{p["catalogue_id"]}.png" alt="{html.escape(p["alt_text"],quote=True)}"></div><div><h2>{i}. {html.escape(p["title"])}</h2><p><a href="{html.escape(p["website_url"],quote=True)}" target="_blank" rel="noopener">Product details</a> · {html.escape(p["sku"])}</p>{"".join(tabs)}</div></article>')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Boldstone — five sculpture drafts</title><style>body{font:16px/1.5 system-ui;margin:0;background:#f4f3ee;color:#21352e}main{max-width:1250px;margin:35px auto;padding:0 24px}h1{font-size:2rem}article{display:grid;grid-template-columns:minmax(200px,32%) 1fr;gap:28px;background:white;border:1px solid #d7dcd4;border-radius:16px;margin:28px 0;padding:24px}.photo img{width:100%;max-height:650px;object-fit:contain;position:sticky;top:24px}textarea{box-sizing:border-box;width:100%;height:180px;border:1px solid #bac8c0;border-radius:8px;padding:12px;font:14px/1.45 system-ui;resize:vertical;background:#fafbf8}.platform{border-top:1px solid #ddd;margin-top:18px;padding-top:4px}h3{font-size:1rem;margin-bottom:2px}h3 span{font-weight:400;color:#63796b;margin-left:8px}p{margin:8px 0}button{background:#244d3c;color:#fff;border:0;border-radius:7px;padding:8px 14px;cursor:pointer}a{color:#256448}.status{padding:18px;background:#e1ebe3;border-radius:10px}@media(max-width:750px){article{grid-template-columns:1fr}.photo img{max-height:400px;position:static}}code{font-size:.9em}</style><main><h1>Five new Boldstone sculpture posts</h1>'''
page+=f'<p class="status"><strong>{ready}/15 platform drafts checked.</strong> Prepared for Facebook, Instagram and Threads. Nothing has been published or added to the publishing queue.</p>'
page+='<p>The native drafts are in the Chrome window named <strong>Boldstone sculpture drafts — Facebook, Instagram and Threads</strong>, with the Spice Texture Instagram draft in a separate background tab of your existing Chrome window. Keep those tabs open until you have reviewed and posted them. This page retains the captions and original photos.</p><p>Script directory: <code>/Users/tprice/Documents/boldstone/social-publisher</code>. Preparation mode: <code>publisher.py prepare MANIFEST --tabs TAB_PLAN</code>.</p>'
page+=''.join(sections)+'''<p>Original photographs and exact product URLs checked on 23 November 2026. Instagram uses its native portrait crop for tall photos; the original files are retained. The live drafts, rather than these source thumbnails, show the posting previews.</p></main><script>async function copyCaption(button){const field=button.previousElementSibling;try{await navigator.clipboard.writeText(field.value);button.textContent='Copied';setTimeout(()=>button.textContent='Copy caption',1200)}catch(e){field.focus();field.select();button.textContent='Selected — copy with ⌘C'}}</script></html>'''
(OUT/'review.html').write_text(page)
print({'ready':ready,'expected':15,'review':str(OUT/'review.html')})
