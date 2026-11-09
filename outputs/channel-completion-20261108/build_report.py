"""Create an owner review from retained readbacks, without publishing anything."""
from pathlib import Path
from html import escape
import json

OUT = Path(__file__).parent
load = lambda name: json.loads((OUT / name).read_text())
esc = lambda value: escape(str(value), quote=True)
link = lambda url, label: '<a target="_blank" rel="noopener" href="'+esc(url)+'">'+esc(label)+'</a>'
release_dir = next(d for d in ('catalogue-image-followup', 'catalogue-google-dates', 'catalogue-consent-followup', 'catalogue-followup', 'catalogue')
                   if (OUT/d/'dropbox-receipt.json').exists())
receipt = load(release_dir+'/dropbox-receipt.json')
assert receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
google_master = load(release_dir+'/google-refresh-verification.json')
assert google_master['status']=='PASS_GOOGLE_NATIVE_MASTER_FULL_EXPORT_READBACK'
assert google_master['source_master_sha256']==receipt['sha256_readback']
assert load('google-native-refresh-verification.json')['status'] == 'PASS_ALL_176_COMBINED_OFFERS'
assert load('app-task-readback-verification.json')['status'] == 'PASS'
products = load('social-five-products.json')
posts = {code: {p['catalogue_id']: p for p in load(code+'-publication-receipts.json')}
         for code in ('instagram', 'facebook', 'linkedin')}
for code, entries in posts.items():
    assert len(entries) == 5 and all(p['status']=='PUBLISHED_NATIVE_READBACK' for p in entries.values())
social_rows = []
for i, product in enumerate(products, 1):
    pid = product['catalogue_id']
    cells = ''.join('<td>'+link(posts[code][pid]['url'], 'Open '+code.title()+' post')+'</td>'
                    for code in ('instagram', 'facebook', 'linkedin'))
    social_rows.append('<tr><th>'+esc(product['title'])+'<small>'+esc(product['sku'])+' · £'+format(product['price_gbp'], '.2f')+'</small></th>'+cells+'</tr>')
prior = OUT.parent/'product-social-approval-20261108'
early_li = json.loads((prior/'linkedin-ten-posts.json').read_text())
early_ig = json.loads((prior/'instagram-publication-receipts.json').read_text())
assert len(early_li)==10 and len(early_ig)==5
li_urls = [p['publication']['url'] for p in early_li] + [p['url'] for p in posts['linkedin'].values()]
ig_urls = [p['url'] for p in early_ig] + [p['url'] for p in posts['instagram'].values()]
assert len(set(li_urls))==15 and len(set(ig_urls))==10
earlier_links = '<p>Earlier ten LinkedIn posts: '+', '.join(link(p['publication']['url'], str(i)) for i,p in enumerate(early_li,1))+'.</p>'
earlier_links += '<p>Earlier five Instagram posts: '+', '.join(link(p['url'],str(i)) for i,p in enumerate(early_ig,1))+'.</p>'
master = load('master-platform-values.json')
tasks = load('platform-task-evidence.json')
image_rows = []
for pid, entry in tasks['products'].items():
    p = entry['platforms']['pinterest']
    matching = [t for t in p['tasks'] if t['id']=='primary_image_size']
    if not matching: continue
    title = master[pid]['Retail / website name']
    task = matching[0]
    image_rows.append('<tr><th>'+link('http://127.0.0.1:8767/#'+pid,title)+'<small>'+esc(pid)+'</small></th><td>'+esc(task['detail'])+'</td><td>'+link(task['url'],'Measured photo')+'</td></tr>')
assert len(image_rows)==96
body = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Boldstone channel completion — 9 November 2026</title>
<style>body{font:16px/1.55 system-ui,sans-serif;color:#24352d;background:#f7f7f1;margin:0}main{max-width:1120px;margin:auto;padding:36px 22px}h1{font-size:2.2rem;line-height:1.2}h2{margin-top:2.5rem}a{color:#285f51}section,.notice{background:white;padding:20px 24px;border:1px solid #dbe1d5;border-radius:10px;margin:20px 0}table{width:100%;border-collapse:collapse;margin:18px 0}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dde2d8}thead{background:#eaf0e6}th{font-weight:600}small{display:block;color:#617067;font-weight:400}img{max-width:100%;height:auto;border:1px solid #d5dcd0}summary{cursor:pointer;font-weight:600;padding:12px 0}li{margin:10px 0}.waiting{background:#fff5df}.ok{color:#245c3b}input{padding:10px;width:min(95%,500px);font:inherit}figure{margin:18px 0}figcaption{color:#617067;font-size:14px}.scroll{overflow-x:auto}code{overflow-wrap:anywhere}footer{font-size:14px;color:#617067;margin:30px 0}</style>
<main><h1>Boldstone: saved channel changes and remaining gates</h1>
<p>Updated 9 November 2026; social publications were verified on 8 November. Product facts come from the sculpture catalogue app. A saved editor record, approved offer, customer-visible listing and completed purchase are separate outcomes.</p>
<section><h2>Verified changes</h2><div class="scroll"><table><thead><tr><th>Area</th><th>Actual result</th></tr></thead><tbody>
<tr><th>Website</th><td>62 Finish titles corrected, including homepage cards. All 176 current retail titles/prices/stock match. All 1,437 selected photo placements are in the main carousels, with the selected primary first. Twenty missing photos appended; one existing primary reordered.</td></tr>
<tr><th>Policies</th><td>Shipping, Returns and FAQ saved and publicly read back. Ten-working-day catalogue dispatch, bespoke timing separately agreed, customer pays actual change-of-mind return postage.</td></tr>
<tr><th>Google Merchant</th><td>325 Approved, 0 Limited, 0 Not approved. All 176 wall sculptures match final combined-offer export on the eleven supplement fields; no new products and no price changes. Registered Boldstone spelling aligned on those offers only.</td></tr>
<tr><th>Pinterest source</th><td>Only 21 additional-image cells refreshed in the existing public retail sheet. All 176 records and 46 fields read back. Daily 07:00 London schedule retained; ingestion remains disabled.</td></tr>
<tr><th>Pinterest tracking</th><td>Matched product view, add-to-cart and checkout-start received HTTP200 in a private browser. Fixed a separate-consent ordering defect; both grant orders and withdrawal verified live, with seventeen logic checks passing. One representative product tested; no purchase/order submitted.</td></tr>
<tr><th>Private Google master</th><td>Refreshed in the existing info@boldstone.co.uk document, still private. All 181 records, 905 columns, twelve sheets and 32,776 formulas independently read back across 570,285 cells. Corrected 1,832 UTC timestamps dropped by Google's initial typed-date conversion; every original instant is preserved. Existing Dropbox native backup refreshed and byte-verified.</td></tr>
<tr><th>Manufacturer brand</th><td>Found the low-image-quality rejection. Replaced the logo with the genuine verified 1,254 × 1,254 Dropbox original. Existing brand saved; status now Brand review pending. Zero variants and zero genuine GTIN assignments.</td></tr>
<tr><th>Brandboom</th><td>176 existing products/SKUs restored; zero added. All thirteen native fields matched across all 176 records: 2,288 comparisons, zero differences. Exact 50-SKU owner preview rebuilt, ordering disabled. Every gallery is checked:1,437 selected photo placements with primary first. Fourteen additional excess-photo cases were repaired, including three upright replacements of the same selected photos; all saved and reopened with exact IDs/count/primary/title/wholesale readback. Public Marketplace publication remains separately unverified.</td></tr>
<tr><th>App tasks</th><td>181 components, twenty platforms each; dated status/task badges and filters. Exactly 96 primary-image size checks. Relevant app changes or seven-day age invalidate old checks. 664 Python and 321 UI tests passed.</td></tr>
<tr><th>Social</th><td>Five new product posts each on Instagram, Facebook and LinkedIn, with unique native links and full caption readback. Exact Meta product tags and tracked LinkedIn destinations verified. Earlier ten LinkedIn and five Instagram posts retained without duplicates.</td></tr>
</tbody></table></div></section>
<section class="waiting"><h2>What is required for Pinterest approval</h2>
<p>The claimed website and connected Instagram account are confirmed. Native issues still say <strong>minimum product requirements</strong> and <strong>minimum website quality requirements</strong>. No individual failing product IDs are supplied. Zero distribution issues with zero ingested products does not mean approval.</p>
<ol><li>All 96 flagged primary originals are now measured below Pinterest's documented 1,000 × 1,500 dimensions. Twenty-eight products already have qualifying selected Listing alternatives at existing public image URLs. <a href="pinterest-photo-alternatives.html">Review these genuine choices side by side</a>. The other 68 have no qualifying alternative among currently selected Listing photos. No primary choice changed. These measurements are not Pinterest's confirmed individual rejection causes.</li>
<li>Tracking receipt tests are complete for product view, add-to-cart and checkout-start. Both consent grant orders and advertising withdrawal are verified. Browser protections remained unchanged. Completed purchase remains unverified; no test order was placed.</li>
<li>The inspected native reassessment route is <strong>Submit appeal</strong>; two remain. <strong>No appeals were used</strong>, respecting the owner's instruction. Website corrections alone cannot force this account gate to clear.</li>
<li>After approval, verify actual completed ingestion, accepted product count and live Product Pins. Do not create a replacement source to bypass the review.</li></ol>
<p><a href="https://help.pinterest.com/en/business/article/before-you-get-started-with-catalogs">Official catalogue requirements</a> · <a href="https://uk.pinterest.com/business/catalogs/4814500935893/diagnosticsv2/?dataSourceId=1536497259764&amp;subjectBusinessId=846254723639262523&amp;tab=DISTRIBUTION_ISSUES">Open the actual account issues</a> · <a href="http://127.0.0.1:8767/#specifications?platform=pinterest&amp;task=primary_image_size">Review the 96 app tasks</a></p>
<details><summary>Native Pinterest rejection evidence —9November</summary><img loading="lazy" src="continuation-2230/pinterest-merchant-issues-20261109.png" alt="Pinterest native merchant issues and appeal gate"></details></section>
<section class="waiting"><h2>Genuine GTINs and Manufacturer Center</h2><p>No assigned Boldstone codes were found in the checked records or targeted business-mailbox searches. Codes cannot be obtained by borrowing another product's barcode or making a checksum-valid number.</p>
<ol><li>Supply the existing Boldstone GS1 membership/allocation, including an allocation under another email if one exists; otherwise establish the turnover-based licence and approve its purchase.</li><li>Assign a genuine unique GTIN to each sellable component/finish, verify licensee/assignment and record it in the master register.</li><li>Await brand approval, supply the same identifiers to website, Merchant and Manufacturer records, then verify the actual daily import. The correct account link is already Active.</li></ol>
<p><a href="https://support.google.com/manufacturers/answer/7494888?hl=en">Google requires a GTIN for every Manufacturer product</a>. No licence purchased and no identifiers invented.</p>
<details><summary>Saved logo correction and pending brand review</summary><img loading="lazy" src="manufacturer-brand-after-logo.png" alt="Existing Boldstone brand now shows Brand review pending"></details></section>
<section><h2>Fifteen follow-up posts published on 8 November</h2><p>Five products, each posted once to each platform on8November. Meta product tags and title/price readbacks are saved; LinkedIn purchase-link destinations are verified.</p><div class="scroll"><table><thead><tr><th>Product</th><th>Instagram</th><th>Facebook</th><th>LinkedIn</th></tr></thead><tbody>'''
body += ''.join(social_rows)+'</tbody></table></div><details><summary>Earlier 8 November posts — retained, not republished</summary>'+earlier_links+'</details>'
body += '<details><summary>Publication proof</summary><img loading="lazy" src="instagram-05-published.png" alt="Published Instagram product post"><img loading="lazy" src="facebook-05-published.png" alt="Published Facebook product post"><img loading="lazy" src="linkedin-05-published.png" alt="Published LinkedIn product post"></details></section>'
body += '''<section><h2>Google, Brandboom and Microsoft</h2><figure><img loading="lazy" src="continuation-2230/google-rendition-processed.png" alt="Google processed 176 existing products with all matched and no issues"><figcaption>Native existing-supplement processing:176updated/matched, no issues. The dated account check still shows325approved. Approval does not guarantee impressions or sales.</figcaption></figure>
<p><a href="brandboom-gallery-audit/verification.json">Read the full176-gallery verification</a>. All removed media remains recoverable. <a href="https://www.brandboom.com/app/a/8BB0EB70AC2">Open the restored 50-product Brandboom owner preview</a>. It is not a public Marketplace presentation. Wholesale prices only, prepacks off, ordering disabled; no public share links created. The native preview retains a blank future-shipping heading when ordering is disabled.</p>
<p>Microsoft store50112622 is populated from the correct Google account: <strong>325 imported, 0 Active, 308 Pending, 17 Rejected</strong>. Fifteen native image-download errors plus two editorial rejections remain in the latest report. Lunar Wave White is misclassified as a health product; the other editorial rejection is an unrelated greetings card. Thirteen sculptures have manual adult-content review flags; those are pending. All217oversized Google feed URLs now use qualified renditions of the same selected photos, below1.5MB. Google processed176matched products without issues; all325Google offers remain approved. One Microsoft refresh was acknowledged, but its completed timestamp and per-offer recovery have not advanced. No all-product review or additional import was submitted.</p></section>'''
body += '<section><h2>Master workbook and verification</h2><p>Existing Dropbox master updated, downloaded again and matched byte-for-byte. All 181 records, twelve sheets and 32,776 formulas preserved; costs, prices, labour and selection decisions unchanged. This follow-up adds seventeen gallery/feed-evidence fields to the existing master, for905totalcolumns. Actual saved observations remain separate from proposals.</p>'
body += '<p>'+link('https://www.dropbox.com/preview/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx','Open the existing Dropbox catalogue')+' · '+link(release_dir+'/catalogue_wall_sculptures.xlsx','Open the local workbook')+'</p>'
body += '<p>Dropbox revision <code>'+esc(receipt['current']['rev'])+'</code>; SHA-256 <code>'+esc(receipt['sha256_readback'])+'</code>; verified '+esc(receipt['verified_utc'])+'.</p><p>'+link(google_master['native_url'],'Open the current private Google master')+'. All twelve native sheets visually inspected. Only three existing Faire planning formulas round one penny differently in the Google engine; their exact upward mathematical rounding was independently checked. Adopted retail prices match. Faire protected-RRP proposals remain unapproved and were not applied.</p><p>The private master is separate from the public retail Pinterest source. Costs and private audit fields were not projected into the public feed.</p></section>'
body += '<section><h2>96 primary-image checks</h2><p>Every original dimension is now known. <a href="pinterest-photo-alternatives.html">Open the 28-product visual review with larger selected choices</a>. No downloaded originals are retained and no owner selection changed. These remain review tasks.</p><input id="filter" aria-label="Filter photo checks" placeholder="Find a component or finish…"><div class="scroll"><table id="checks"><thead><tr><th>Component</th><th>Required review</th><th>Photo</th></tr></thead><tbody>'+''.join(image_rows)+'</tbody></table></div></section>'
body += '<section><h2>Four more photo opportunities</h2><p>Twenty-one genuinely larger unselected originals were identified for Bone Spiral II White, Lunar Phase II White, Lunar Phase IV Silver Finish and Lunar Water Catcher White. Shadows and orientation need review. <a href="pinterest-photo-alternatives.html#unselected">Review the contact sheets and exact files</a>. These are proposals; purpose and primary selections remain unchanged.</p></section>'
body += '<section><h2>Live consent verification</h2><p>The shared-view-key defect was reproduced, repaired and saved. GA4 and Pinterest now track their first consented view independently. Both category orders and withdrawal were checked; no browser security protections were weakened. <a href="consent-fix/verification.json">Read the bounded verification receipt</a>.</p><figure><img loading="lazy" src="consent-fix/late-advertising-network.png" alt="Native browser Network panel shows the matched Pinterest product view after advertising consent is granted later"><figcaption>Two Pinterest endpoints deliver one logical matched product-view event. Purchase tracking and merchant approval are separate outstanding checks.</figcaption></figure></section>'
body += '<footer>Receipts are retained beside this review. No Pinterest appeal, GTIN purchase, paid upgrade, fake purchase, duplicate product creation or unapproved pricing proposal was applied.</footer></main><script>document.querySelector("#filter").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("#checks tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))});</script></html>'
for name in ('instagram-05-published.png','facebook-05-published.png','linkedin-05-published.png','pinterest-merchant-issues-final.png','manufacturer-brand-after-logo.png','google-merchant-overview-final.png'):
    assert (OUT/name).is_file(), name
(OUT/'review.html').write_text(body)
print(json.dumps(dict(status='BUILT_FROM_VERIFIED_RECEIPTS',social_posts=15,earlier_linkedin_posts=10,earlier_instagram_posts=5,pinterest_image_tasks=96,dropbox_revision=receipt['current']['rev'])))
