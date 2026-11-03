# Required verification

Test every changed product's data and media. Use representative products for the checkout journey: a single panel, a paired/group photograph, a finish alternative, a heavy/oversized sculpture and a product with few in situ images. Record exact IDs, time and evidence.

| Test | Required result | Evidence |
|---|---|---|
| Identity after rename/move | Same Dropbox ID/content and catalogue component; new path/name; no duplicate product | Inventory + catalogue mapping |
| Content replacement | New bytes reviewed; stale approval not silently reused | Hash/revision and image choices |
| Missing original | Correct absence state; no resurrection from stale cache/feed | Complete inventory and public readback |
| Component merge | One intended active listing; historical IDs retained as aliases; no loss of image choices | Before/after mapping |
| Source snapshot consistency | Register/gallery hashes and review event cutoff coherent | Release manifest |
| Cost model | Manufacturing excludes labour; total includes labour once; zero labour retained | Effective costs and computed price |
| Material/finish scenario | Changing selected scenario changes cost where rates differ; public copy remains appropriate | App calculation and export |
| Public material wording | Each wall sculpture states gypsum-based material once; applied decorative finishes have a surface-effect point; no contradictory base-material or solid-metal/stone claims | App description, native export and public/channel readback |
| Complete channel information | Brand, product type/model, SKU, colour, quantity, material, dimensions and sale scope agree; category-specific mandatory facts are supported | Channel Details, platform native fields, required-field report |
| Dispatch consistency | Native handling and public copy use 10 working days by default, three where required; shorter unconfirmed deadlines prevent activation | Platform setting and draft/live copy readback |
| TikTok images and content | Real product images meet 800-pixel minimum on both axes; correct main photo, maximum nine; no off-platform purchase steering | Native saved draft and original image dimensions |
| US delivery planning | Physical and dimensional weight, destination zone, tariff/surcharge date and oversize rules checked; budget is not advertised as a guaranteed quote | Calculation tests, workbook and dated carrier source |
| Cross-platform duplicate safety | One record for each intended account/component/sale unit; existing IDs, drafts and pending imports reconciled before creation | Platform ID and SKU ledger, before/after counts |
| Publication-state preservation | Copy-only edit retains live/draft/inactive status; import flags alone are insufficient | Before/after product state and native list counts; pilot one item first |
| Interrupted update recovery | Reopen the exact existing ID/SKU; compare saved copy before another mutation; never recreate an uncertain item | Reopened editor/export and durable per-item receipt |
| Main carousel | Primary first; all selected listing/in situ photos; no ads-only/excluded photos or duplicates | Ordered IDs/URLs + screenshot |
| Group photography | Correct components and finish; individual sale is unambiguous | Photo review + product copy |
| Image delivery | Public HTTPS URLs load without login, expiry or local cache dependency | Fresh browser/HTTP readback |
| Alt text | Describes the actual photo and component; no filename-only text | Public DOM |
| Homepage | Every intended listing appears through search/load-more; primary and link current | Search/count/link verification |
| Website price/stock | Public price/currency/availability equal frozen catalogue | Product + structured data + cart |
| Shipping | Packed weight >0; package limits considered; visible delivery total agrees with policy | Native record + checkout |
| Feed identity | Google offer ID and Meta content ID resolve to correct Squarespace variant/SKU | Item-level feed readback |
| Supplement precedence | Current images/text survive the next native feed refresh | Readback after subsequent refresh |
| Google eligibility | Account/product issues reviewed; pending distinct from approved | Diagnostics by exact changed IDs |
| Meta shop publication | Collections visible in both platform previews after Publish | Publication receipt + previews |
| Social product tag | Tap opens the exact finish/component and correct website listing | Tag → item → product recording |
| Mobile layout | Gallery, quantity, cart and checkout usable at phone width | Responsive browser screenshot |
| Real mobile app route | Instagram/Facebook tag, in-app browser, return navigation and checkout work | Physical-device test; desktop emulation alone is insufficient |
| Consent declined | Non-essential GA4/Meta tracking does not start before consent | Consent state and observed event diagnostics |
| Consent accepted | One expected page/product event with correct value/currency/ID | GA4 realtime/DebugView + Meta Test Events |
| Add to cart | One event per successful addition; correct quantity/value; failure does not emit success | Cart readback + event payload |
| Checkout | Cart persists, delivery appears and begin_checkout/InitiateCheckout matches contents | Checkout + event diagnostics |
| Purchase | One event after a successful authorised order; transaction ID, GBP value, shipping/tax and items correct | Order receipt + both analytics platforms |
| Purchase deduplication | Refresh/back does not duplicate revenue; browser/server events deduplicate if both enabled | Same order ID and event IDs |
| Failed/cancelled order | No purchase event or false revenue | Failure state + diagnostics |
| Refund | Correct refund handling if applicable; test order excluded from fulfilment | Refund receipt + reporting |
| Meta catalogue matching | ViewContent, AddToCart and Purchase content_ids match current catalogue IDs, with correct content_type | Meta Events/Catalogue diagnostics |
| Source attribution | Controlled UTM/referral click persists to checkout and authorised purchase; source/medium/campaign visible | GA4 acquisition + transaction attribution |
| Marketplace duplicate safety | One listing per intended SKU; uncertain publish reconciled before retry | Your listings + item permalink |
| Workbook | Opens, correct rows/formulas/prices/images, no local/expired links; Dropbox readback matches bytes | Validation + native revision/hash |

## Purchase-test boundary

Squarespace warns that test mode disables live checkout. More importantly, its native Meta integration suppresses purchase events for test orders. Test mode can check order mechanics, but cannot pass the Meta purchase-tracking test. Leave live mode unchanged for this work; reconcile a genuine completed order, or obtain specific authorisation for a charged purchase and its payment method before executing one. [Squarespace guidance](https://support.squarespace.com/hc/en-us/articles/115015760107-Using-Meta-Pixel-with-Squarespace), checked 31 October 2026.

Do not send a fabricated `purchase` event merely to make the analytics screen green. Configured tracking, a rendered checkout, an observed cart event and a verified purchase are four different results. If no test order has been completed, record purchase tracking as **UNVERIFIED**, not passed.

## Regression selection

- After image-only changes: identity, carousel, group imagery, links, homepage, feeds, tags and one cart/checkout smoke test.
- After price/cost changes: costs, public/structured prices, cart, shipping, feeds and conversion values.
- After ID/URL/merge changes: full identity/mapping, redirects, every existing tag/link, feeds and catalogue-event matching.
- After tracking/consent/checkout code changes: full funnel, both consent states, duplicate/failed-order tests and mobile route.
- After a deletion: complete-inventory confirmation, app/workbook/public/feed removal and Marketplace/social stale-link review.
