"""Create a compact review page from exact native social receipts and live audits."""
import html
import json
from pathlib import Path

OUT=Path(__file__).parent
load=lambda n:json.loads((OUT/n).read_text())
esc=lambda x:html.escape(str(x))
li=load('linkedin-ten-posts.json')
ig=load('instagram-publication-receipts.json')
master=load('catalogue/dropbox-receipt.json')
assert master['status']=='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert len(li)==10 and all(p['status']=='PUBLISHED_NATIVE_READBACK' for p in li)
assert len(ig)==5 and all(p['status']=='PUBLISHED_NATIVE_READBACK' and p['full_caption_readback'] and p['tag_saved_readback'] for p in ig)

def table(items, instagram=False):
    rows=[]
    for p in items:
        receipt=p if instagram else p['publication']
        title=p['tag_title'] if instagram else p['title']
        url=receipt['url']
        proof=(receipt.get('tag_price') or f'£{receipt["tag_price_gbp"]:.2f}') if instagram else 'Photo, alt text and tracked product link'
        rows.append(f'<tr><td>{esc(title)}</td><td><a href="{esc(url)}" target="_blank" rel="noopener">Open published post</a></td><td>{esc(proof)}</td></tr>')
    return '<table><thead><tr><th>Product</th><th>Native post</th><th>Verified</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'

body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Boldstone — published product posts and approval checks</title>
<style>body{{font:17px/1.6 system-ui,sans-serif;max-width:1100px;margin:45px auto;padding:0 24px;color:#25372c}}h1,h2{{font-family:Georgia,serif;line-height:1.2}}h1{{font-size:38px}}h2{{margin-top:45px}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:14px;border-bottom:1px solid #dce3d8}}th{{background:#eff3eb}}a{{color:#315f43}}.status{{background:#edf3e7;padding:18px;border-radius:10px}}img{{max-width:100%;border:1px solid #dce3d8}}small{{color:#536454}}</style>
<h1>Boldstone product posts and approval checks</h1><p>Verified 8 November 2026. The sculpture catalogue remains the product source of truth.</p>
<p class="status"><b>Published:</b> 10 LinkedIn posts and five Instagram posts. Each has a unique native receipt. All five Instagram captions and saved Commerce tags were checked after publication.</p>
<p>The existing <a href="https://www.dropbox.com/preview/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx">Dropbox master catalogue</a> has been updated with these receipts and per-product merchant-audit fields, then downloaded and byte-verified. All 181 records, existing prices and 32,776 formulas were preserved. Verified: {esc(master['verified_utc'])}. The private Google Sheets snapshot was not changed.</p>
<h2>LinkedIn — Sally Price</h2>{table(li)}
<h2>Instagram — @boldstonesculpture</h2>{table(ig,True)}
<p>The Frozen Fish Commerce product currently omits “Finish” from its native title. The exact Verdigris variant and £64.74 catalogue price were checked. Acanthus’s first caption required an edit to the existing post; it was corrected without creating a duplicate.</p>
<h2>Pinterest</h2><p>Merchant approval remains blocked by “minimum product requirements” and “minimum website quality requirements”. Zero products are approved. No appeal was submitted. The dialog currently offers an appeal as the account-review route, so resolving website issues alone is not proof of reinstatement.</p>
<p>The Pinterest profile’s shop URL is now boldstonesculpture.com, with a studio description and public business email saved and verified after reload.</p>
<p><a href="https://uk.pinterest.com/business/catalogs/4814500935893/diagnosticsv2/?dataSourceId=1536497259764&amp;subjectBusinessId=846254723639262523&amp;tab=DISTRIBUTION_ISSUES">Open account diagnostics</a> · <a href="https://policy.pinterest.com/en/merchant-guidelines">Pinterest merchant requirements</a></p>
<p>The actual feed, all 176 landing pages and primary image responses were checked. See the adjacent audit for exact image-resolution and title discrepancies. The website verification meta tag is present. A direct Pinterest tracking tag was not found in the public HTML; runtime tag and consent behaviour still need verification.</p>
<p>Live policy issues include conflicting dispatch times, generic returns text for goods Boldstone does not sell, a blanket sale-item exclusion and no clear refund-processing deadline. Corrections are prepared for review in <a href="pinterest-remediation-proposal.html">the remediation proposal</a>; the live policies have not been changed during this check.</p>
<h2>Genuine GTINs and Manufacturer Center</h2><p>No existing GS1 licence or allocation was found in the catalogue, searched local records, public results or targeted searches of info@boldstone.co.uk. This does not prove no licence exists under another business or email. Manufacturer Center account 5898308482 has no product variants.</p>
<p>Manufacturer Center requires an assigned GTIN for each product variant. An SKU or another brand’s barcode cannot substitute. At least 176 genuine identifiers are needed for the publication catalogue. Membership pricing depends on turnover, and additional GTIN capacity is licensed annually. No subscription has been purchased, no terms accepted and no identifier invented.</p>
<p><a href="https://support.google.com/manufacturers/answer/6124116?hl=en">Google requirements</a> · <a href="https://www.gs1uk.org/knowledge-hub/membership/how-much-does-gs1-uk-membership-cost">GS1 membership prices</a> · <a href="https://www.gs1uk.org/knowledge-hub/membership/how-do-i-purchase-more-gtinsnumbers2">Additional GTIN capacity</a></p>
<h2>Publication proof</h2><p>LinkedIn’s tenth published post:</p><img src="linkedin-10-published.png" alt="Sally Price’s published Azure product post on LinkedIn"><p>Instagram’s fifth published post and caption:</p><img src="instagram-05-published.png" alt="Published Brancusi Meander product post in Meta Business Suite"><p>Pinterest’s current merchant issues:</p><img src="pinterest-merchant-issues.png" alt="Pinterest showing minimum product and website quality issues">
<p><small>Receipts are dated observations, not a claim of reach, sales or platform approval.</small></p></html>'''
(OUT/'published-posts-and-approval-checks.html').write_text(body)
print(json.dumps(dict(linkedin_posts=10,instagram_posts=5,report=str(OUT/'published-posts-and-approval-checks.html'))))
