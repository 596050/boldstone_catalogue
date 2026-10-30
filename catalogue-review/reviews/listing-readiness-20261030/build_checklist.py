"""Create a read-only, per-item completion checklist from the current app snapshot."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape as e
from urllib.parse import quote
import csv,json
out=Path(__file__).resolve().parent
spec=json.loads((out/'specifications.json').read_text())
coverage=json.loads((out/'coverage.json').read_text())
export=json.loads((out/'export-result.json').read_text());root=Path(export['path'])
def read_csv(name):
    with (root/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
products={p['product_id']:p for p in read_csv('all-product-decisions.csv')}
media=defaultdict(list)
for r in read_csv('image-decisions-and-tags.csv'):
    if r['use']=='listing':media[r['product_id']].append(r)
rows=[]
for p in spec['products']:
    pid=p['id'];x=products[pid];photos=p['photos'];selected=media[pid]
    blockers=json.loads(x['review_blockers'])
    missing_alt=[r for r in selected if not r['alt'].strip()]
    missing_dims=[r for r in selected if not r['original_dimensions'].strip()]
    required=[];support=[]
    if p['listing_decision']=='exclude':required.append('Intentionally excluded. No upload work unless reinstated.')
    else:
        for b in blockers:
            required.append('Reconcile the saved name review with the renamed catalogue source.' if b=='Source changed since field review: Product name' else b)
        if photos['in_situ']['missing']:
            support.append(f"Add or associate {photos['in_situ']['missing']} more in-situ image(s) to reach 2. Existing count: {photos['in_situ']['count']}.")
        if missing_alt:support.append(f"Write alt text for {len(missing_alt)} selected listing-image association(s).")
        if missing_dims:support.append(f"Read original pixel dimensions for {len(missing_dims)} selected image(s). Missing metadata does not mean the original image is absent.")
    row={'id':pid,'name':p['name'],'family':p['family'],'decision':p['listing_decision'],'review_status':p['review_status'],'passes_app_export_checks':x['ready_for_listing']=='True','listing_image_count':photos['listing']['count'],'primary':photos['primary_listing']['status'],'in_situ_count':photos['in_situ']['count'],'in_situ_missing':photos['in_situ']['missing'],'blank_alt_selections':len(missing_alt),'missing_original_dimensions':len(missing_dims),'app_blockers':blockers,'export_work':required,'image_work':support,'app_url':'http://127.0.0.1:8767/#'+pid,'spec_url':'http://127.0.0.1:8767/#'+pid+'?tab=specs','listing_url':'http://127.0.0.1:8767/#'+pid+'?tab=listing','folder_url':p['folder_url'],'price':x['Price'],'cost':p['costing']['total_cost'],'specifications':{f['label']:f['value'] for f in p['fields']},'image_links':[{'name':r['file_name'],'url':r['source_url'],'folder_url':r['folder_url'],'alt_missing':not r['alt'].strip(),'dimensions_missing':not r['original_dimensions'].strip()} for r in selected]}
    rows.append(row)
summary={'checked_utc':datetime.now(timezone.utc).isoformat(),'snapshot_checked_at':spec['checked_at'],'total':len(rows),'included':sum(p['decision']=='include' for p in rows),'passes_app_checks':sum(p['passes_app_export_checks'] for p in rows),'pending':sum(p['decision']=='pending' for p in rows),'excluded':sum(p['decision']=='exclude' for p in rows),'included_name_review_flags':sum(p['decision']=='include' and any(b=='Source changed since field review: Product name' for b in p['app_blockers']) for p in rows),'included_missing_listing_images':sum(p['decision']=='include' and not p['listing_image_count'] for p in rows),'included_situ_missing':sum(p['in_situ_missing'] for p in rows if p['decision']=='include'),'included_situ_items':sum(p['in_situ_missing']>0 for p in rows if p['decision']=='include'),'specification_blanks':spec['totals']['missing'],'listing_copy_blanks':sum(not (f['value'] or '').strip() for p in spec['products'] for f in p['listing_fields'])}
(out/'per-item-checklist.json').write_text(json.dumps({'summary':summary,'products':rows},ensure_ascii=False,indent=2)+'\n')
parts=[]
for p in rows:
    active=p['decision']!='exclude'
    facets=['all']+(['export'] if active and not p['passes_app_export_checks'] else [])+(['situ'] if active and p['in_situ_missing'] else [])+(['metadata'] if active and (p['blank_alt_selections'] or p['missing_original_dimensions']) else [])+(['pending'] if p['decision']=='pending' else [])+(['excluded'] if not active else [])
    status='Passes app export checks' if p['passes_app_export_checks'] else 'Excluded' if not active else 'App checks need attention'
    tasks='<p>No current app export blocker.</p>' if not p['export_work'] else '<ul>'+''.join('<li>'+e(t)+'</li>' for t in p['export_work'])+'</ul>'
    image_tasks='<p>No tracked image-preparation gap.</p>' if not p['image_work'] else '<ul>'+''.join('<li>'+e(t)+'</li>' for t in p['image_work'])+'</ul>'
    image_links=''.join(f'<li><a href="{e(a["url"],quote=True)}">{e(a["name"])}</a>'+(' - alt text missing' if a['alt_missing'] else '')+(' - original dimensions unknown' if a['dimensions_missing'] else '')+'</li>' for a in p['image_links'])
    specs=''.join(f'<dt>{e(k)}</dt><dd>{e(v or "Omitted")}</dd>' for k,v in p['specifications'].items())
    parts.append(f'''<article data-kind="{' '.join(facets)}" data-search="{e((p['name']+' '+p['family']+' '+p['id']).lower(),quote=True)}"><div class="title"><div><small>{e(p['family'])} · {e(p['id'])}</small><h2>{e(p['name'])}</h2></div><span class="badge {'good' if p['passes_app_export_checks'] else 'hold'}">{e(status)}</span></div><p class="counts">Listing: {e(p['decision'])} · Review: {e(p['review_status'])} · Primary: {e(p['primary'])} · {p['listing_image_count']} listing images · {p['in_situ_count']}/2 in situ · Price {e(p['price'])}</p><p><a href="{p['app_url']}">Review images</a> · <a href="{p['spec_url']}">Specifications & pricing</a> · <a href="{p['listing_url']}">Listing & notes</a> · <a href="{e(p['folder_url'],quote=True)}">Dropbox folder</a></p><div class="columns"><section><h3>App export checks</h3>{tasks}</section><section><h3>Supporting image work</h3>{image_tasks}</section></div><details><summary>Current specifications</summary><dl>{specs}</dl></details>{'<details><summary>Selected listing images and remaining metadata</summary><ul>'+image_links+'</ul></details>' if image_links else ''}</article>''')
html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone - work remaining by sculpture</title><style>body{margin:0;background:#f5f5ef;color:#26302a;font:16px/1.5 system-ui}main{max-width:1200px;margin:40px auto;padding:0 24px}h1{font:42px Georgia;margin-bottom:8px}h2{font:26px Georgia;margin:8px 0}h3{font-size:16px}a{color:#466747}article{background:white;padding:24px;margin:16px 0;border:1px solid #d7ddcf;border-radius:12px}.title,.filters{display:flex;justify-content:space-between;gap:20px;align-items:center}.columns{display:grid;grid-template-columns:1fr 1fr;gap:30px}.badge{padding:8px 12px;border-radius:7px;white-space:nowrap;font-size:14px}.good{background:#e5eddf}.hold{background:#f5ebce}.counts,small{color:#657165}input,select{font:inherit;padding:12px;border:1px solid #c9d2c1;border-radius:7px;background:white}input{flex:1}.filters{position:sticky;top:0;background:#f5f5ef;padding:16px 0;z-index:2}details{margin-top:12px}summary{cursor:pointer;color:#466747}dl{display:grid;grid-template-columns:160px 1fr;gap:8px}dt{font-weight:600}dd{margin:0}article[hidden]{display:none}.note{background:#e9eee3;padding:20px;border-radius:10px}@media(max-width:720px){.columns{grid-template-columns:1fr;gap:0}.title,.filters{display:block}.badge{display:inline-block}input{width:90%;margin-bottom:8px}}</style><main><p>BOLDSTONE · CURRENT APP CHECKLIST</p><h1>Work remaining by sculpture</h1>'''
html+=f'<p>Snapshot: {e(spec["checked_at"])}. All {len(rows)} active component records are included. This is a read-only report; it does not change reviews, files or online listings.</p>'
html+='<div class="note"><strong>149 of 172 included items pass the app\'s current export checks.</strong> The other 23 comprise 22 saved-name review flags after source changes and one item without listing photographs. Six items are undecided and three are intentionally excluded. All specification and listing-copy fields are filled. The two-in-situ target is separate: 27 included items need 38 more image associations.<p>Passing app checks is not proof of publication or final platform matching. Image alt text, original resolution checks, platform product/variant/SKU mapping and upload review remain separate. Blank private notes and captions are optional.</p><p>Prices use 100% markup on the current manufacturing-cost model, including editable labour. Packaging, delivery, selling fees, installation and pump/plumbing are outside that model. Existing physical-material specifications are retained separately from the chosen production-cost scenario. The Dropbox workbook predates the markup change and needs refreshing before the final upload.</p></div>'
html+='''<div class="filters"><input id="search" aria-label="Search sculptures" placeholder="Find a sculpture, family or ID"><select id="filter" aria-label="Filter remaining work"><option value="all">All 181 items</option><option value="export">App export blockers / decisions</option><option value="situ">In-situ target gaps</option><option value="metadata">Image metadata preparation</option><option value="pending">Undecided listings</option><option value="excluded">Intentionally excluded</option></select><span id="count"></span></div>'''+''.join(parts)+'''</main><script>const search=document.querySelector('#search'),filter=document.querySelector('#filter'),cards=[...document.querySelectorAll('article')];function update(){const q=search.value.trim().toLowerCase(),kind=filter.value;let n=0;for(const card of cards){card.hidden=!(card.dataset.search.includes(q)&&card.dataset.kind.split(' ').includes(kind));if(!card.hidden)n++;}document.querySelector('#count').textContent=n+' of '+cards.length+' items';}search.addEventListener('input',update);filter.addEventListener('change',update);update();</script></html>'''
assert html.count('<article ')==181
(out/'per-item-checklist.html').write_text(html)
print(json.dumps(summary,indent=2))
print(out/'per-item-checklist.html')
