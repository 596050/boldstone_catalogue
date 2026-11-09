"""Prepare exact merchant remediation and reviewable policy copy; no live writes."""
import html
import json
from pathlib import Path

OUT=Path(__file__).parent
audit=json.loads((OUT/'pinterest-public-audit.json').read_text())
esc=lambda x:html.escape(str(x))
bad_titles=[p for p in audit['products'] if not p['exact_title_match']]
bad_images=[p for p in audit['products'] if not p['image']['meets_pinterest_documented_1000x1500']]
assert len(bad_titles)==62 and len(bad_images)==96

returns='''Returns and refunds

For standard catalogue sculptures bought online, you may contact us within 30 days of delivery to request a change-of-mind return. Email info@boldstone.co.uk with your order number. We will provide the return address and packing instructions. Please send the sculpture back within 14 days of telling us you wish to return it, carefully protected against damage.

For change-of-mind returns, you pay the actual return postage. You may inspect the sculpture as you would in a shop; please avoid installing, altering or using it before deciding to keep it. A deduction may apply for handling beyond what is needed to inspect it, where permitted by law.

We will refund the original payment method within 14 days of receiving the returned sculpture. For a qualifying cancellation, the refund includes the standard outbound delivery charge. Extra charges for a premium delivery option are not refundable. Your bank may take additional time to display the credit.

Contact us promptly if a sculpture arrives damaged, faulty or incorrect. Include your order number and photographs where possible. We will arrange the appropriate remedy and necessary return postage; your statutory rights are unaffected.

Personalised or bespoke commissions made to your specifications may be excluded from change-of-mind returns. We will identify this before the order is agreed. A standard catalogue design is not automatically excluded just because it is cast after ordering. Sale items retain the same statutory consumer rights.
'''
shipping='''Dispatch and delivery

Standard wall sculptures are ready to dispatch within 10 working days of order confirmation, unless a different deadline is clearly agreed for your order. Working days exclude weekends and UK public holidays. Bespoke commissions and large projects have a separately agreed production and dispatch schedule.

Dispatch is the date a parcel leaves the studio. Carrier transit time is additional. We will send shipment confirmation and tracking details when available. Contact info@boldstone.co.uk with your order number if you need an update.

UK delivery charges for eligible orders are shown at checkout before payment. Large, unusually heavy or specially packed orders may require a separate quote. For international delivery, or a destination that is unavailable at checkout, contact us for a confirmed shipping quote before ordering. The quotation will specify the service, estimated transit time and any relevant packing charges. Applicable import duties and local taxes will be explained for the chosen service.

Returns and refunds are governed by the Return and Refund Policy. Customers pay actual return postage for eligible change-of-mind returns. Faulty, damaged or incorrect items are handled separately; contact us before arranging shipment.
'''
proposal=dict(status='PREPARED_FOR_REVIEW_NOT_APPLIED',basis='Current 30-day website return offer, owner actual-return-postage choice and app 10-working-day dispatch policy; UK statutory guidance',returns=returns,shipping=shipping,
              dependencies=['Apply consistently to Returns, Shipping and FAQ pages; remove conflicting product lead-time promises',
                            'Owner review of commercial and consumer policy before publication',
                            'Recheck checkout shipping destinations and rates before promising any particular international service'])
(OUT/'policy-copy-proposal.json').write_text(json.dumps(proposal,indent=2)+'\n')

rows_titles=''.join(f'<tr><td><a href="{esc(p["link"])}">{esc(p["landing_product_title_without_site_suffix"])}</a></td><td>{esc(p["title"])}</td></tr>' for p in bad_titles)
rows_images=''.join(f'<tr><td><a href="{esc(p["link"])}">{esc(p["title"])}</a></td><td>{p["image"]["width"]} × {p["image"]["height"]}</td><td><a href="{esc(p["image_link"])}">View current image</a></td></tr>' for p in bad_images)
page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Pinterest approval — exact remediation proposal</title>
<style>body{{font:17px/1.6 system-ui;max-width:1050px;margin:45px auto;padding:0 24px;color:#24362b}}h1,h2{{font-family:Georgia,serif}}h1{{font-size:38px;line-height:1.2}}h2{{margin-top:38px}}table{{width:100%;border-collapse:collapse;font-size:15px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #ddd}}th{{background:#edf2e8}}a{{color:#315c41}}pre{{white-space:pre-wrap;font:17px/1.7 system-ui;background:#f5f5ee;padding:24px}}.status{{background:#fff0d5;padding:20px;border-radius:9px}}details{{padding:14px 0}}summary{{font-weight:bold;cursor:pointer}}</style>
<h1>Pinterest approval: exact remediation proposal</h1><p>8 November 2026. Account 846254723639262523; catalogue 4814500935893.</p>
<p class="status"><b>Not approved.</b> Pinterest reports minimum product and website quality requirements. The following are independently verified discrepancies and prepared corrections. Pinterest has not identified which individual issue caused its decision. No appeal has been submitted.</p>
<h2>Completed</h2><ul><li>The profile now uses the already claimed <b>boldstonesculpture.com</b>, replacing the displayed boldstone.co.uk address. A public studio description and business email were saved and reloaded.</li><li>All 176 public product pages and main image URLs returned HTTP 200. All 176 prices, GBP currencies and in-stock states matched the feed.</li><li>The homepage’s Pinterest ownership-verification meta tag is present.</li></ul>
<h2>Product data to correct</h2><p><b>62 titles:</b> the feed uses the catalogue’s explicit “Finish” wording while the current website omits it. Update the existing website products to the catalogue’s names, keeping product URLs and variant IDs stable. Then refresh Google/Meta and check the existing Pinterest feed. Do not create replacement products.</p>
<details><summary>Show all 62 title differences</summary><table><thead><tr><th>Current website</th><th>Catalogue / Pinterest target</th></tr></thead><tbody>{rows_titles}</tbody></table></details>
<p><b>96 main images:</b> measured width or height is below Pinterest’s published 1,000 × 1,500 primary-image specification. The audit uses width ≥1,000 and height ≥1,500; this is a documented-dimension check, not a platform rejection report. Review genuine higher-resolution originals or a suitable selected product photograph. No image was changed or upscaled during this check.</p>
<details><summary>Show all 96 image checks</summary><table><thead><tr><th>Product</th><th>Actual pixels</th><th>Primary photo</th></tr></thead><tbody>{rows_images}</tbody></table></details>
<h2>Website policies</h2><p>The current Shipping page says “within a working week”, “1–8 weeks” and “within 7 business days”, while the app specifies 10 working days by default. The Returns page includes irrelevant food/beauty/hazardous-goods wording, excludes all sale items and gives no clear refund deadline. The FAQ repeats inconsistent timing and exclusions. The replacement copy below is prepared for owner review; it has not been published.</p>
<h3>Proposed returns copy</h3><pre>{esc(returns)}</pre><h3>Proposed shipping copy</h3><pre>{esc(shipping)}</pre>
<p>Apply approved wording consistently to the Shipping, Returns and FAQ pages. Confirm actual checkout coverage before promising a specific international route.</p>
<h2>Tracking and final review</h2><p>Ownership verification and an Instagram connection are already present. A direct Pinterest tracking script was not found in the public HTML; a runtime check is still required because a tag could be injected through another system. Verify a consent-aware Pinterest tag and exact product IDs.</p>
<p>After corrections, validate the existing daily CSV feed and check all seven mandatory fields, current product images, price and availability. Pinterest’s current account dialog offers an appeal for reassessment. Your instruction not to use appeals remains in force, so this account-review step is left untouched. Normal RSS or Instagram auto-publishing is separate from catalogue approval.</p>
<p><a href="https://policy.pinterest.com/en/merchant-guidelines">Pinterest merchant requirements</a> · <a href="https://help.pinterest.com/en/business/article/before-you-get-started-with-catalogs">Pinterest feed and image requirements</a> · <a href="https://www.gov.uk/accepting-returns-and-giving-refunds">UK returns guidance</a></p></html>'''
(OUT/'pinterest-remediation-proposal.html').write_text(page)
print(json.dumps(dict(title_differences=len(bad_titles),images_below_documented_spec=len(bad_images),policies='PREPARED_NOT_APPLIED')))
