"""Replace only published catalogue card primary image URLs in the current layout."""
from pathlib import Path
import json,re,html,hashlib
OUT=Path(__file__).resolve().parent
plan=json.loads((OUT/'website-final-plan.json').read_text());products={p['catalogue_id']:p for p in plan['products'] if p.get('public')}
old=(OUT/'homepage-code-before.html').read_text();seen=[];changes=[]
def update(m):
 card=m[0];cid=re.search(r'data-catalogue-id="([^"]+)"',card)[1];p=products[cid];seen.append(cid)
 assert html.unescape(re.search(r'href="([^"]+)"',card)[1])==p['website_url']
 assert html.unescape(re.search(r'<h3>(.*?)</h3>',card)[1])==p['retail_name']
 prior=re.search(r'<img src="([^"]+)"',card)[1];wanted=html.escape(p['primary_url'].split('?')[0]+'?format=750w',quote=True)
 if prior!=wanted:changes.append({'catalogue_id':cid,'old':html.unescape(prior),'new':html.unescape(wanted)})
 return card.replace('<img src="'+prior+'"','<img src="'+wanted+'"',1)
new=re.sub(r'<a class="sculpture-card"[^>]*>.*?</a>',update,old,flags=re.S)
assert len(seen)==len(set(seen))==176 and set(seen)==set(products)
(OUT/'homepage-catalogue-block.html').write_text(new)
(OUT/'homepage-prepared.json').write_text(json.dumps({'status':'PREPARED','products':176,'changed_images':len(changes),'changes':changes,'code_sha256':hashlib.sha256(new.encode()).hexdigest(),'layout_preserved':True},indent=2))
print({'products':176,'changed_images':len(changes)})
