"""Verify published shortlinks and assemble the final publication receipt."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
import hashlib
import json
import re
import urllib.request

OUT=Path(__file__).resolve().parent
stamp=lambda:datetime.now(timezone.utc).isoformat()
posts=json.loads((OUT/'posts.json').read_text())
platforms=['linkedin','facebook','instagram']
receipts={platform:json.loads((OUT/(platform+'-publication-receipts.json')).read_text()) for platform in platforms}
for platform,rows in receipts.items():
    assert len(rows)==5 and len({r['url'] for r in rows})==5
    assert {r['catalogue_id'] for r in rows}=={p['catalogue_id'] for p in posts}
    assert all(r['status']=='PUBLISHED_NATIVE_READBACK' for r in rows)
    assert all(r.get('full_caption_readback') or r.get('full_product_text_readback') for r in rows)

def verify_link(pair):
    i,r=pair
    file=OUT/f'linkedin-{i:02d}-shortlink.html'
    if file.exists():body=file.read_text()
    else:
        request=urllib.request.Request(r['published_purchase_shortlink'],headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request,timeout=30) as response:
            assert response.status==200
            body=response.read().decode()
        file.write_text(body)
    destinations=re.findall(r'data-tracking-control-name="external_url_click"[^>]*href="([^"]+)"',unescape(body))
    assert r['expected_purchase_url'] in destinations,(r['title'],destinations)
    return {'catalogue_id':r['catalogue_id'],'shortlink':r['published_purchase_shortlink'],
            'destination':r['expected_purchase_url'],'verified_utc':stamp(),
            'source_html_sha256':hashlib.sha256(body.encode()).hexdigest()}
with ThreadPoolExecutor(max_workers=4) as pool:
    verified_links=list(pool.map(verify_link,enumerate(receipts['linkedin'],1)))
(OUT/'linkedin-purchase-link-verification.json').write_text(json.dumps(verified_links,ensure_ascii=False,indent=2)+'\n')
by_platform={platform:{r['catalogue_id']:r for r in rows} for platform,rows in receipts.items()}
rows=[]
for p in posts:
    urls={platform:by_platform[platform][p['catalogue_id']]['url'] for platform in platforms}
    rows.append({'catalogue_id':p['catalogue_id'],'sku':p['sku'],'title':p['title'],'urls':urls})
summary={'status':'COMPLETE_PUBLISHED_AND_VERIFIED','completed_utc':stamp(),
         'new_posts':15,'counts':{p:5 for p in platforms},'products':rows,
         'verification':{'original_photos_hash_verified':5,'product_pages_verified':5,
            'native_post_captions_verified':15,'linkedin_photo_previews_verified':5,
            'linkedin_purchase_destinations_verified':5,
            'exact_meta_product_tags_selected_and_saved':5,
            'meta_crossposted_pairs_observed_in_published_inventory':5},
         'account_names':{'linkedin':'Sally Price','facebook':'Boldstone Sculpture','instagram':'boldstonesculpture'}}
(OUT/'final-status.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
table=''
for r in rows:
    cells=''.join(f'<td><a href="{escape(r["urls"][p])}">Open {escape(p.title())} post</a></td>' for p in platforms)
    table+=f'<tr><td><strong>{escape(r["title"])}</strong><br><small>{escape(r["sku"])}</small></td>{cells}</tr>'
cards=''.join(f'<figure><img src="media/{p["catalogue_id"]}.png" alt="{escape(p["alt_text"])}"><figcaption>{escape(p["title"])}</figcaption></figure>' for p in posts)
html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone — 14 November social posts</title><style>body{{font:17px/1.5 system-ui,sans-serif;max-width:1200px;margin:45px auto;padding:0 22px;background:#faf9f5;color:#252522}}h1{{font-size:32px}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:16px;text-align:left;border-bottom:1px solid #ddd}}a{{color:#245e71}}small{{color:#666}}.photos{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-top:32px}}figure{{margin:0}}img{{width:100%;height:230px;object-fit:contain;background:white}}figcaption{{margin-top:8px;font-size:14px}}</style><h1>Five new sculptures across three platforms</h1><p>Published and verified on 14 November 2026: <strong>15 posts — five each on LinkedIn, Facebook and Instagram.</strong></p><p>LinkedIn: Sally Price. Facebook: Boldstone Sculpture. Instagram: @boldstonesculpture. Original photographs and current product pages checked. All 15 saved captions read back; all five LinkedIn purchase-link destinations verified.</p><table><thead><tr><th>Sculpture</th><th>LinkedIn</th><th>Facebook</th><th>Instagram</th></tr></thead><tbody>{table}</tbody></table><div class="photos">{cards}</div></html>'''
(OUT/'published-posts.html').write_text(html)
release=json.loads((OUT/'release-record.json').read_text());release.update(summary)
(OUT/'release-record.json').write_text(json.dumps(release,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':summary['status'],'new_posts':15,'counts':summary['counts'],'verified_link_destinations':len(verified_links),'report':str(OUT/'published-posts.html')},indent=2))
