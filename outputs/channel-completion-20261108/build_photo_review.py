"""Owner review of genuine selected alternatives; photo links, no copied media."""
from pathlib import Path
from html import escape
import json

OUT = Path(__file__).parent
load = lambda n: json.loads((OUT / n).read_text())
review = load('pinterest-original-resolution-review.json')
public = load('current-public-images-verified.json')
unselected = load('pinterest-unselected-photo-options.json')
esc = lambda v: escape(str(v), quote=True)
dim = lambda d: ' × '.join(map(str, d)) + ' px' if d else 'Unknown'


def photo(image, candidate=False):
    hosted = image.get('hosted_check') or public.get(image['id'], {})
    url = hosted.get('url')
    picture = ('<img loading="lazy" decoding="async" src="' + esc(url)
               + '" alt="' + esc(image['name']) + '">') if url else '<p>No public preview</p>'
    extra = ('<p>Hosted image: <strong>' + esc(dim(hosted.get('dimensions')))
             + '</strong></p>') if candidate else ''
    return ('<figure>' + picture + '<figcaption><strong>'
            + ('Selected listing alternative' if candidate else 'Current primary — unchanged')
            + '</strong><p>Original: <strong>' + esc(dim(image['original']['dimensions']))
            + '</strong></p>' + extra + '<p class="filename">' + esc(image['name'])
            + '</p><a href="' + esc(image['url'])
            + '" target="_blank" rel="noopener">Open exact Dropbox file</a></figcaption></figure>')


cards = []
no_alternative = []
for p in review['products']:
    candidates = [a for a in p['higher_resolution_listing_candidates']
                  if a['hosted_check']['meets_documented_dimensions']]
    app = 'http://127.0.0.1:8767/#' + p['catalogue_id']
    if not candidates:
        no_alternative.append('<tr><th><a href="' + esc(app) + '">' + esc(p['title'])
                              + '</a><small>' + esc(p['catalogue_id']) + '</small></th><td>'
                              + esc(dim(p['primary']['original']['dimensions']))
                              + '</td><td><a href="' + esc(p['primary']['url'])
                              + '">Current original</a></td></tr>')
        continue
    cards.append('<article data-title="' + esc(p['title'].lower()) + '"><h2>'
                 + esc(p['title']) + '</h2><p><a href="' + esc(app)
                 + '">Review image choices in the catalogue app</a> · '
                 + esc(p['catalogue_id']) + '</p><div class="photos">'
                 + photo(p['primary']) + ''.join(photo(a, True) for a in candidates)
                 + '</div></article>')
assert len(cards) == 28 and len(no_alternative) == 68
html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pinterest photo choices — Boldstone</title><style>
body{font:16px/1.5 system-ui,sans-serif;color:#263c30;background:#f6f7f2;margin:0}main{max-width:1300px;margin:auto;padding:30px 20px}h1{line-height:1.2}article,.notice{background:white;padding:20px;margin:22px 0;border:1px solid #d5dfd1;border-radius:12px}h2{margin-top:0}.photos{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}figure{margin:0;max-width:420px}img{width:100%;height:340px;object-fit:contain;background:#f1f0ea}figcaption{padding:10px 0}figcaption p{margin:6px 0}.filename{font-size:13px;overflow-wrap:anywhere;color:#677067}a{color:#285e4a}input{padding:12px;font:inherit;width:min(90%,500px)}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd;vertical-align:top}small{display:block;color:#677067;font-weight:400}summary{font-weight:600;cursor:pointer;padding:20px 0}[hidden]{display:none!important}@media(max-width:600px){main{padding:20px 12px}article{padding:15px}.photos{grid-template-columns:1fr}img{height:300px}}
</style><main><h1>Pinterest: photo choices for 28 products, plus four unselected opportunities</h1>
<p>8 November 2026. All 96 flagged primary originals have now been checked, including two exact Dropbox revisions streamed into memory. None reaches both documented dimensions. No original copies were retained and no image selection was changed.</p>
<div class="notice"><p><strong>28 products already have a larger selected Listing photograph available.</strong> The 41 candidate placements use 39 distinct photographs; all their existing public image URLs also meet Pinterest's documented minimum of 1,000 pixels wide and 1,500 pixels high. The current primary is shown beside each alternative so the correct sculpture, finish and presentation can be reviewed.</p>
<p>The other <strong>68 products</strong> have no qualifying photograph among their currently selected Listing images. This does not prove that a suitable unselected or new photograph cannot be found. These size checks are separate from Pinterest's account-level rejection; Pinterest has not named individual failing products.</p>
<p>A further review found <a href="#unselected">21 qualifying unselected originals for four more products</a>. Those are separate proposals requiring lighting/orientation and purpose review; the selected-photo counts above have not been inflated.</p>
<p>Changing the app's primary also changes the intended website primary. Keep the owner's choices until reviewed, then refresh the existing platform records using the same product identifiers. Do not make duplicate products or artificially upscale images as a substitute for detail.</p>
<p><a href="https://help.pinterest.com/en/business/article/before-you-get-started-with-catalogs">Official Pinterest image specification</a> · <a href="review.html">Channel status and publication receipts</a></p></div>
<label for="search">Find a product</label><p><input id="search" type="search" placeholder="Component or finish…"></p>
<div id="choices">'''
html += ''.join(cards)
html += '<section id="unselected"><h2>Four additional unselected-photo opportunities</h2><p>Current exact Dropbox revisions and bounded original headers checked. Full original copies were not retained and their full hash was not recomputed. These contact sheets use small provider thumbnails; open the exact original before making a selection.</p>'
for p in unselected['products']:
    rows = []
    for c in p['qualifying_candidates']:
        rows.append('<tr><td><a target="_blank" rel="noopener" href="'+esc(c['url'])+'">'+esc(c['name'])+'</a><small>'+esc(c['id'])+'</small></td><td>'+esc(dim(c['header_check']['dimensions']))+'</td></tr>')
    html += ('<article data-title="'+esc(p['title'].lower())+'"><h3>'+esc(p['title'])+'</h3><p>'+esc(p['visual_review_note'])+'</p>'
             '<p><a href="http://127.0.0.1:8767/#'+esc(p['catalogue_id'])+'">Open component choices</a></p>'
             '<a href="'+esc(Path(p['contact_sheet']).name)+'"><img style="height:auto;max-height:none" loading="lazy" src="'+esc(Path(p['contact_sheet']).name)+'" alt="Reviewed small contact sheet for '+esc(p['title'])+'"></a>'
             '<table><thead><tr><th>Unselected original</th><th>Original dimensions</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></article>')
html += '</section>'
html += '</div><details><summary>68 products still needing a suitable larger selected photograph</summary><table><thead><tr><th>Product</th><th>Current original</th><th>File</th></tr></thead><tbody>'
html += ''.join(no_alternative) + '</tbody></table></details>'
html += '''<script>document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.title.includes(q))});</script></main></html>'''
(OUT / 'pinterest-photo-alternatives.html').write_text(html)
print(json.dumps({'products_with_alternatives': len(cards),
                  'without_selected_alternative': len(no_alternative),
                  'image_sources': 'Existing verified public URLs; no photo copies stored'}))
