"""Create a read-only findings report from retained public readbacks."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sys

def main(out):
    website=json.loads((out/'website-audit.json').read_text())
    saatchi=json.loads((out/'saatchi-audit.json').read_text())
    pointer=json.loads((out.parent/'source.json').read_text())
    assert hashlib.sha256(Path(pointer['path']).read_bytes()).hexdigest()==pointer['sha256']
    source_caps=saatchi['gallery_comparisons']
    cap_only=[r for r in source_caps if r['exceeds_capacity_only']]
    below_capacity=[r for r in source_caps if not r['exceeds_capacity_only']]
    assert len(source_caps)==82 and len(cap_only)==41 and len(below_capacity)==41
    counts=website['issue_counts']
    assert website['public_products_checked']==176
    assert counts.get('PRICE_DIFFERS',0)==counts.get('SKU_DIFFERS',0)==counts.get('PACKED_WEIGHT_DIFFERS',0)==0
    assert counts.get('GALLERY_SELECTION_DIFFERS',0)==counts.get('GALLERY_MAPPING_INCOMPLETE',0)==0
    summary={'checked_utc':datetime.now(timezone.utc).isoformat(),'public_product_checks':176,
        'public_title_mismatches':counts['TITLE_DIFFERS'],'public_description_model_mismatches':counts['DESCRIPTION_MODEL_DIFFERS'],
        'public_primary_mismatches':counts['PRIMARY_DIFFERS'],'public_shipping_dimensions_missing':counts['PACKED_DIMENSIONS_ZERO'],
        'public_description_dimensions_unclarified':counts.get('DESCRIPTION_FIELD_DIFFERS',0),
        'saatchi_snapshot_box_entries_above_crate_thresholds':len(saatchi['crate_mismatches']),
        'previous_82_saatchi_gallery_flags_at_native_capacity':len(cap_only),'remaining_gallery_count_candidates_not_confirmed_omissions':len(below_capacity),
        'prices_skus_packed_weights_and_gallery_sets_match':True,'workbook_source_sha256':pointer['sha256'],
        'workbook_and_app_changed':False,'live_store_changed':False,
        'qualification':'Public website data was read live. Saatchi findings use the supplied 3 November snapshot and the catalogue estimates, not a current authenticated Saatchi readback. Checkout charges were not tested.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    esc=lambda s:html.escape(str(s))
    app=lambda r:f'<a href="http://127.0.0.1:8767/#{esc(r["id"])}">{esc(r["name"])}</a>'
    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    parts=['<!doctype html><meta charset="utf-8"><title>Boldstone further catalogue checks</title><style>body{font:16px/1.5 system-ui;color:#25332d;background:#f8f7f3;margin:2rem}main{max-width:1450px;margin:auto}h1,h2{font-family:Georgia}table{border-collapse:collapse;width:100%;background:white}td,th{padding:.7rem;border-bottom:1px solid #ddd;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#e8eee6}a{color:#28563b}.scroll{overflow:auto}section{margin-top:2rem}input{font:inherit;padding:.6rem;width:min(40rem,90%)}</style><main><h1>Further catalogue checks</h1>',
        '<p>Checked '+esc(website['checked_utc'])+'. All 176 public store products were read and matched by their existing product and variant IDs. Two intentionally hidden records returned 404; they are not counted as broken public listings.</p>',
        '<p>'+esc(summary['qualification'])+' This audit did not change the app, workbook, Dropbox files or live store.</p>',
        '<p>All 176 prices, SKUs, packed shipping weights and selected gallery image sets match the catalogue. Every live gallery URL was resolved using retained exact image-ID/content-hash upload mappings. No gallery omission was inferred from a title or filename.</p>',
        '<label>Filter rows <input id="filter" type="search" placeholder="Sculpture, issue or value"></label>']
    for kind,title in [('TITLE_DIFFERS',str(counts['TITLE_DIFFERS'])+' public titles differ from the catalogue'),('DESCRIPTION_MODEL_DIFFERS',str(counts['DESCRIPTION_MODEL_DIFFERS'])+' public description model lines differ from the catalogue')]:
        rows=[r for r in website['issues'] if r['issue']==kind]
        parts+=['<section><h2>'+title+'</h2><p>These differences omit the catalogue’s applied-finish clarification.</p>',
            table(['Sculpture','Public listing','Current website value','Catalogue target'],[[app(r),f'<a href="{esc(r["url"])}">Open website</a>',esc(r['observed']),esc(r['expected'])] for r in rows]),'</section>']
    dimension_rows=[r for r in website['issues'] if r['issue']=='DESCRIPTION_FIELD_DIFFERS']
    assert len(dimension_rows)==3 and all(r['field']=='Dimensions' for r in dimension_rows)
    parts+=['<section><h2>Three dimension clarifications have not reached the website</h2><p>The catalogue now labels height, width and depth explicitly. The public descriptions retain the old unlabelled sequences; Palm Form Two lists 40 × 45 cm while the current specification explicitly says 45 cm high × 40 cm wide. This is an orientation/wording mismatch, not evidence of a new physical measurement.</p>',
        table(['Sculpture','Public dimensions line','Catalogue dimensions line'],[[app(r),esc(r['observed']),esc(r['expected'])] for r in dimension_rows]),'</section>']
    primary=[r for r in website['issues'] if r['issue']=='PRIMARY_DIFFERS']
    parts+=['<section><h2>Dune Ripple I – Verdigris: primary order differs</h2><p>The new selected primary is already in the gallery, in second position. The website instead leads with an in-situ photograph; its thumbnail/asset URL also points to that in-situ photograph. This is an ordering mismatch, not a missing upload.</p>',
        table(['Sculpture','Website','First website image ID','App primary image ID'],[[app(r),f'<a href="{esc(r["url"])}">Open website</a>',esc(r['observed']),esc(r['expected'])] for r in primary]),'</section>',
        '<section><h2>176 store variants have zero shipping dimensions</h2><p>All three native dimension fields are zero. Shipping weights match the app’s packed-weight estimates. Carrier-calculated rates require dimensions as well as weight; this audit did not test whether the current checkout uses such rates or is undercharging.</p><p><a href="https://support.squarespace.com/hc/en-us/articles/213022907-Set-up-carrier-calculated-shipping-for-your-store">Squarespace carrier-calculated shipping requirements</a></p>',
        table(['Sculpture','Website','Native length × width × height','App provisional packed dimensions (cm)'],[[app(r),f'<a href="{esc(r["url"])}">Open website</a>',esc(str(r['observed'])),esc(' × '.join(map(str,r['expected_estimate_cm'])))] for r in website['issues'] if r['issue']=='PACKED_DIMENSIONS_ZERO']),'</section>',
        '<section><h2>92 Saatchi snapshot packing entries need reconciliation</h2><p>The supplied snapshot records cardboard boxes for these sculptures. Their current catalogue estimated weight or height exceeds Saatchi’s sculpture crate threshold. This is a mismatch between recorded planning assumptions and platform guidance, not a new physical measurement or a verified live setting. Confirm the appropriate crate/exception and actual outer size before using these entries for shipping.</p><p><a href="https://support.saatchiart.com/hc/en-us/articles/115003365447-Packaging-Shipping">Saatchi sculpture packing guidance</a></p>',
        table(['Sculpture','Recorded packaging','Catalogue upper sculpture weight (kg)','Catalogue height (cm)','Source artwork ID'],[[app(r),esc(r['observed_packaging']),esc(r['weight_upper_kg']),esc(r['height_cm']),esc(r['native_artwork_id'])] for r in saatchi['crate_mismatches']]),'</section>',
        '<section><h2>Correction to the earlier 82 Saatchi gallery flags</h2><p>Saatchi allows one primary and five additional images. Of the 82 supplied galleries with fewer photos than the app selects, 41 already have the maximum six. Those 41 must not be called missing-photo errors just because the app selects more than six. The remaining 41 are candidates for an eligibility and exact-image check; a count comparison alone cannot prove that eligible images are missing.</p><p><a href="https://support.saatchiart.com/hc/en-us/articles/17737130295963-How-to-photograph-an-artwork">Saatchi image capacity and requirements</a></p>',
        table(['Sculpture','Current app selection count','Snapshot gallery count','Correct interpretation'],[[app(r),esc(r['selected']),esc(r['observed']),'At six-image capacity; no count shortfall' if r['exceeds_capacity_only'] else 'Below capacity; check image eligibility and IDs before declaring an omission'] for r in source_caps]),'</section>',
        '<script>document.querySelector("#filter").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script></main>']
    (out/'assessment.html').write_text(''.join(parts))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main(Path(sys.argv[1]).resolve())
