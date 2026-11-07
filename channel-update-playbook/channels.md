# Channels and link conventions

Verified account identifiers during setup on 31 October 2026; recheck identity before writes.

| Service | Account / location |
|---|---|
| Central review app | http://127.0.0.1:8767/#specifications |
| Sculpture collection | https://boldstonesculpture.com/ |
| Squarespace admin | https://caper-spinach-spcy.squarespace.com/config/commerce/selling-tools |
| Dropbox workbook | `/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx` |
| Google Merchant Center | 5664655454 — Boldstone Sculpture; https://merchants.google.com/mc/taskhub?a=5664655454 |
| Microsoft Merchant Center (verified 7 November 2026) | Boldstone Sculpture — store `50112622`, feed `1830841`, account `187335961`; [store](https://ui.ads.microsoft.com/campaign/vnext/merchantcenter/overview?aid=187335961&cid=255124527&storeId=50112622&uid=193182372). [Setup and refresh instructions](microsoft-merchant-center.md). |
| GA4 property | 546648922 — Boldstone Sculpture; measurement ID G-DYE31M1PWM |
| Meta business | 2380586078685156 |
| Meta catalogue | 1638438493182970 |
| Meta commerce account | 326960679342026 |
| Meta shop | 2182319861923672 |
| Meta dataset/pixel | 4566349726935061 |
| Facebook Page attached to Commerce Manager | https://www.facebook.com/BoldstoneSculpture/ — Page ID 103781478537396; profile ID 100067801382847 |
| Facebook creator profile used for Marketplace | https://www.facebook.com/boldstone.s — profile ID 100064311860325 |
| Instagram | https://www.instagram.com/boldstonesculpture/ |
| Threads | https://www.threads.com/@boldstonesculpture |
| Marketplace selling | https://www.facebook.com/marketplace/you/selling |
| Website payment provider | Stripe connected as info@boldstone.co.uk; PayPal not connected in the inspected settings |

Do not confuse the Facebook creator profile used for Marketplace with the Facebook Page connected to Commerce Manager. On 31 October the website's social icon was corrected to the connected Page and a Threads link was added; both were read back on the public website. Verify the Page ID from the shop's sales-channel settings before changing Page controls.

## Tracking convention

Use HTTPS, lower-case values and a stable campaign. Preserve the canonical product path and append tracking parameters only to links used outside the website.

| Placement | utm_source | utm_medium | utm_campaign | utm_content |
|---|---|---|---|---|
| Instagram bio | instagram | organic_social | wall_sculptures | profile |
| Instagram Story | instagram | organic_social | wall_sculptures | story_COMPONENTID_DATE |
| Facebook shopping button | facebook | organic_social | wall_sculptures | page_button |
| Facebook featured introduction | facebook | organic_social | wall_sculptures | featured_shop_intro |
| Threads profile | threads | organic_social | wall_sculptures | profile |
| Threads product post | threads | organic_social | wall_sculptures | product_slug |
| Marketplace listing | facebook | marketplace | wall_sculptures | component_id |

The Page currently uses **Learn more**, pointing to the tracked sculpture collection. The inspected **Buy now** provider selector did not offer Squarespace or a custom URL. Existing Marketplace listings currently contain canonical product links; the Marketplace UTM row is the convention for future edits, not a claim that every existing link is tagged. The new crossposted Ammonite post uses `utm_source=meta`; that single shared URL does not distinguish Facebook clicks from Instagram clicks.

Example currently saved on Threads:

`https://boldstonesculpture.com/?utm_source=threads&utm_medium=organic_social&utm_campaign=wall_sculptures&utm_content=profile`

Never put UTM parameters on internal website navigation or strip Google's auto-tagging parameter or Meta's click ID during redirects. Do not place names, email addresses, order details or other personal information in tracking URLs. Native product feeds should keep the correct canonical destination; use their supported tracking configuration rather than replacing IDs or product paths.

## What should propagate after each kind of change

| Change | Mandatory downstream checks |
|---|---|
| New image or changed image purpose | App approval → website carousel → homepage if primary → workbook → Google/Meta image supplements → Marketplace photos → relevant social tags/link previews |
| Rename only | App/Dropbox identity → public retail title if intended → workbook → feeds → social/Marketplace titles; retain IDs and URLs |
| Price/labour/markup | Effective app price → website/cart/structured data → workbook → feeds → Marketplace price → conversion value |
| Merge/delete/exclude | Stable-ID reconciliation → public availability/removal → workbook → feeds → collections/tags → Marketplace removal/update → redirects for old URLs |
| Shipping/lead time | App/package data → native store checkout → delivery policy → Merchant shipping settings → public copy and Marketplace terms |
| Product URL change | Redirect → native feed → supplements → profile/post/tag/Marketplace links → attribution/canonical tests |
| Tracking/consent | Code/configuration → both consent states → exact catalogue matching → cart/checkout → authorised purchase/deduplication → source attribution |
