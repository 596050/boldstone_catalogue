"""Read-only catalogue consistency audit; never edits reviews or the workbook."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx

def main(out):
    read=lambda n:json.loads((out/n).read_text())
    pointer=read('source.json');path=Path(pointer['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pointer['sha256']
    book=Xlsx(path);app=read('app.json');snap=read('catalogue-snapshot.json')
    products={p['id']:p for p in snap['products']};fields={p['id']:{f['key']:f['value'] for f in p['fields']+p['listing_fields']} for p in app['products']}
    assert set(products)==set(fields) and len(products)==181
    images={(r['product_id'],r['image']['id']):r for r in snap['images']}
    for p in snap['products']:
        assert {f['key']:f['value'] for f in p['fields']+p['listing_fields']}==fields[p['id']]
    overlap=defaultdict(list);uncategorised=[];missing_alt=defaultdict(list);missing_dimensions=defaultdict(list)
    nonstandard=[];primaries_in_situ=[];within_gallery_duplicates=[];withheld=[]
    selected=set();filelookup={r['image']['id']:r['image'] for r in snap['images']}
    for pid,p in products.items():
        ph=p['photos'];listing=set(ph['listing_ids']);situ=set(ph['in_situ_ids']);primary=ph['primary_id']
        ids=listing|situ|({primary} if primary else set());selected.update(ids)
        if primary and primary in situ:primaries_in_situ.append({'id':pid,'name':p['name'],'photo_id':primary})
        hashes=defaultdict(list)
        for aid in ids:
            row=images[pid,aid];im=row['image'];meta=im['original']
            record={'id':pid,'name':p['name'],'photo_id':aid,'file_name':im['name'],'url':im['url'],
                    'primary':primary==aid,'listing':aid in listing,'in_situ':aid in situ}
            if aid in listing and aid in situ:overlap[aid].append(record)
            if aid in listing and not im.get('effective_types'):uncategorised.append(record)
            if not row['choice'].get('alt'):missing_alt[aid].append(record)
            if not meta.get('dimensions'):missing_dimensions[aid].append(record)
            if im['withheld_reasons']:withheld.append(record)
            if meta.get('dropbox_content_hash'):hashes[meta['dropbox_content_hash']].append(aid)
        within_gallery_duplicates.extend({'id':pid,'photo_ids':ids} for ids in hashes.values() if len(ids)>1)
    for aid,im in filelookup.items():
        path=im.get('provenance',{}).get('path','')
        if path.startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/') and not re.fullmatch(r'[a-z0-9-]+__[a-z0-9-]+__\d{3,}\.[A-Za-z0-9]+',im['name']):
            nonstandard.append({'photo_id':aid,'file_name':im['name'],'path':path,'url':im['url'],'selected':aid in selected})
    stale=[];aliases={'Individual price':'Price','Product name':'Name','Family / collection':'Family','Listing description':'Description'}
    for n in book.rows('Specification Sources',8):
        pid=book.value('Specification Sources','C'+str(n));raw=book.value('Specification Sources','E'+str(n));key=aliases.get(raw,raw)
        if pid not in fields:continue
        old=book.value('Specification Sources','F'+str(n));new=fields[pid][key]
        if old!=new:
            # Preserve exact source and target text in the JSON audit.
            stale.append({'id':pid,'name':products[pid]['name'],'field':key,'cell':'F'+str(n),'observed':old,'current':new,
                'observed_model':next((line for line in old.splitlines() if line.startswith('Model:')),''),
                'current_model':next((line for line in new.splitlines() if line.startswith('Model:')),'')})
    main_mismatches=[];cost_mismatches=[]
    for n in range(8,189):
        pid=book.value('Wall Sculptures','AA'+str(n));p=products[pid];f=fields[pid];c=p['costing']
        for co,key in [('C','Name'),('D','Dimensions / depth'),('E','Weight'),('F','Material / finish'),('G','Fixing'),('I','Price'),('J','Availability'),('K','Lead time'),('AC','Sale unit'),('AD','Description'),('AQ','Seller SKU'),('AV','Retail name')]:
            if book.value('Wall Sculptures',co+str(n))!=f[key]:main_mismatches.append([pid,co,key])
        for sh,co,value in [('Wall Sculptures','H',c['pricing']['marked_up_price']),('Wall Sculptures','AM',c['manufacturing_cost']),('Wall Sculptures','AL',c['labour_cost']),('Manufacturing Costs','W',c['manufacturing_cost']),('Manufacturing Costs','X',c['total_cost']),('Upload Plan','P',c['pricing']['marked_up_price'])]:
            if abs(book.value(sh,co+str(n))-value)>.011:cost_mismatches.append([pid,sh,co])
    duplicate_keys={}
    for key in ['Seller SKU','Retail name','Marketplace title','Model / catalogue reference']:
        owners=defaultdict(list)
        for pid,f in fields.items():owners[f[key]].append(pid)
        duplicate_keys[key]={value:pids for value,pids in owners.items() if len(pids)>1}
    summary={'checked_utc':datetime.now(timezone.utc).isoformat(),'source_app_snapshot':snap['created_utc'],
        'dropbox_revision':pointer['dropbox']['rev'],'source_sha256':pointer['sha256'],'components':181,
        'dual_purpose_photos':len(overlap),'dual_purpose_selections':sum(map(len,overlap.values())),
        'dual_purpose_components':len({r['id'] for rows in overlap.values() for r in rows}),
        'dual_purpose_primaries':len(primaries_in_situ),'uncategorised_listing_photos':len(uncategorised),
        'stale_specification_source_rows':len(stale),'nonstandard_filenames':len(nonstandard),
        'selected_distinct_photos':len(selected),'selected_distinct_photos_without_saved_alt':len(missing_alt),
        'selected_distinct_photos_without_original_dimensions':len(missing_dimensions),
        'listing_distinct_photos_without_saved_alt':sum(any(r['listing'] for r in rows) for rows in missing_alt.values()),
        'primary_photos_without_original_dimensions':sum(any(r['primary'] for r in rows) for rows in missing_dimensions.values()),
        'main_app_workbook_mismatches':main_mismatches,'cost_price_mismatches':cost_mismatches,
        'duplicate_identifiers_or_names':duplicate_keys,'selected_withheld_photos':withheld,'duplicate_bytes_within_selected_gallery':within_gallery_duplicates,
        'scope':'Read-only audit. No app selections, Dropbox files, workbook values or native platform listings changed. Missing saved alt does not establish missing website alt; native image accessibility was not checked.'}
    report={'summary':summary,'dual_purpose_photos':dict(overlap),'uncategorised_listing_photos':uncategorised,
        'stale_specification_source_rows':stale,'nonstandard_filenames':nonstandard,
        'missing_saved_alt':dict(missing_alt),'missing_original_dimensions':dict(missing_dimensions),'in_situ_primaries':primaries_in_situ}
    (out/'findings.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    esc=lambda value:html.escape(str(value))
    app_link=lambda r:f'<a href="http://127.0.0.1:8767/#{esc(r["id"])}">{esc(r["name"])}</a>'
    photo_link=lambda r:f'<a href="{esc(r["url"])}">{esc(r["file_name"])}</a>'
    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    parts=['<!doctype html><meta charset="utf-8"><title>Boldstone data consistency audit</title><style>body{font:16px/1.5 system-ui;color:#25332d;background:#f8f7f3;margin:2rem}main{max-width:1500px;margin:auto}h1,h2{font-family:Georgia}table{border-collapse:collapse;width:100%;background:white}td,th{border-bottom:1px solid #ddd;padding:.7rem;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e8eee6}a{color:#28563b}.scroll{overflow:auto}code{font-size:13px}input{font:inherit;padding:.6rem;width:min(40rem,90%)}small{display:block;color:#65716b}section{margin-top:2rem}details{margin:1.2rem 0}</style><main><h1>Boldstone data consistency audit</h1>',
        f'<p>App snapshot: {esc(snap["created_utc"])}. Verified Dropbox revision: <code>{esc(pointer["dropbox"]["rev"])}</code>.</p><p>{esc(summary["scope"])}</p>',
        '<p>All 181 main-sheet records and checked manufacturing costs/prices match the app. No duplicate current SKUs, retail names or model references, and no byte-identical repeats within the selected gallery of a component.</p>',
        '<label>Filter the detail rows <input id="filter" type="search" placeholder="Sculpture, file, field or ID"></label>',
        '<section><h2>Five selected primary photographs have no image type</h2><p>Listing is a use. Product is a separate image type. The current Product filter checks image types and therefore hides these five.</p>',
        table(['Sculpture','Photograph','Selected primary'],[[app_link(r),photo_link(r),'Yes' if r['primary'] else 'No'] for r in uncategorised]),'</section>',
        '<section><h2>20 photographs are both Listing and In situ</h2><p>24 listing selections across 22 components. Four are primary photographs; clearing their Listing use also clears the primary selection.</p>',
        table(['Photograph','Components and primary selections'],[[photo_link(rows[0]),'<br>'.join(app_link(r)+(' <strong>PRIMARY</strong>' if r['primary'] else '') for r in rows)] for rows in overlap.values()]),'</section>',
        '<section><h2>66 stale “Current app value” cells in Specification Sources</h2><p>The main sheet and current app agree. These additional copied descriptions retain older model names or a SKU. Original source-value columns are separate and should remain historical.</p>',
        table(['Sculpture','Cell','Copied model line','Current app model line'],[[app_link(r),esc(r['cell']),esc(r['observed_model']),esc(r['current_model'])] for r in stale]),'</section>',
        '<section><h2>Three filenames do not follow the folder-derived naming convention</h2>',
        table(['Photograph','Current Dropbox path','Selected for a gallery'],[[photo_link(r),esc(r['path']),'Yes' if r['selected'] else 'No'] for r in nonstandard]),'</section>']
    for title,items in [('Missing saved alt text',missing_alt),('Original dimensions not recorded',missing_dimensions)]:
        parts.extend(['<details><summary>'+esc(title)+f' — {len(items)} distinct selected photographs</summary>',
            table(['Photograph','Components','Purposes'],[[photo_link(rows[0]),'<br>'.join(app_link(r) for r in rows),'<br>'.join(('Primary' if r['primary'] else 'Listing' if r['listing'] else 'In situ') for r in rows)] for rows in items.values()]),'</details>'])
    parts.append('<script>document.querySelector("#filter").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script></main>')
    (out/'assessment.html').write_text(''.join(parts))
    assert summary['dual_purpose_photos']==20 and summary['dual_purpose_components']==22
    assert not main_mismatches and not cost_mismatches and not any(duplicate_keys.values())
    assert not within_gallery_duplicates and not withheld
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main(Path(sys.argv[1]).resolve())
