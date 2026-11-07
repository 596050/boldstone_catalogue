# Microsoft Merchant Center

Native setup verified on 7 November 2026. This is the product-catalogue route for Bing Shopping. The onboarding option **Import from Meta Ads** imports advertising campaigns; it does not create the sculpture product catalogue.

## Account and current result

- Signed-in business account: `info@boldstone.co.uk`, Boldstone (`G1459Y2Q`).
- Advertising account `187335961`, customer `255124527`, user `193182372`.
- Merchant store **Boldstone Sculpture**, ID `50112622`.
- Domain `https://boldstonesculpture.com/`, selected from the account's verified Bing Webmaster Tools domains.
- Existing automatically created **Default Catalog**, feed `1830841`, reused for the upload. Target United Kingdom, English, explicit GBP prices.
- The 176 publication products were uploaded once and the native Products table reports **176 products**. Their initial status is **Pending**. Upload acceptance does not establish approval or public display.
- Microsoft reports store processing can take up to **three business days**.
- **Show free Product Listings in the shopping tab** is on.
- Automatic item updates are on for **Price and availability**. These reconcile the website; they do not publish app edits, add new products or refresh all feed fields.
- Payment setup was skipped. No paid campaign was created or imported.

[Open the store](https://ui.ads.microsoft.com/campaign/vnext/merchantcenter/overview?aid=187335961&cid=255124527&storeId=50112622&uid=193182372).

## Refresh after a catalogue update

1. Complete the normal app-to-website release first. Freeze current specifications, complete image coverage and the image library. Keep the established publication scope and stable Seller SKU identifiers.
2. Generate one tab-delimited UTF-8 `.txt` feed from the current app. Every product must have a matching live website SKU, GBP selling price and current primary photograph. Stop if a check fails.
3. Use the current public title, complete description, finish wording, truthful availability and direct product URL. Use the existing public CDN image only when its source content hash matches the current Dropbox original. Never use a thumbnail preview list as the complete set of selected photographs.
4. Handmade products without GTIN or manufacturer MPN use `identifier_exists=FALSE`. Do not invent barcodes or identifiers. Do not introduce a free-delivery promise or guessed delivery charge. The current GB sculpture feed has no shipping-price field; native shipping settings are labelled US only.
5. Open Merchant Center → Boldstone Sculpture → Feeds → **Default Catalog** → Update feed. Update feed `1830841`; do not create another store or catalogue for a routine refresh.
6. Save a submission intent with exact file hash, scope, store and feed. Submit once, retain the native result and reconcile ambiguous outcomes before any retry.
7. Download the native Products CSV. Check the full SKU set, product count, GBP prices, titles and URLs against the submitted file. Inspect Diagnostics for product, feed and store issues. Distinguish pending, approved and rejected records.
8. Confirm free product listings remain on. Approval makes products eligible to display; it does not guarantee impressions or sales. Check subsequent product-listing performance separately from paid advertising.

The current feed is a manual upload. Refresh after relevant product changes and before Microsoft's 30-day feed expiry; daily refresh is Microsoft's recommendation. No unattended Microsoft publisher was installed by this setup. Automatic item updates are a useful price/stock safeguard, not a substitute for that refresh.

## Evidence and implementation

The frozen first-release files are in `outputs/saatchi-bing-merchant-20261107/`:

- `prepare_microsoft_feed.py`: builder with 176 mapped website SKU/price/primary checks. Its inputs are frozen files in that directory; capture fresh app data and mappings before reusing it for a later release.
- `boldstone_wall_sculptures_microsoft.txt`, `microsoft-feed-manifest.json`: submitted payload and local validation.
- `microsoft-public-product-readbacks.json`: mapped public website verification.
- `microsoft-store-created.txt`, `microsoft-feed-uploaded.txt`: native creation and submission receipts.
- `microsoft-products-176-pending.txt`: native count and initial processing state.
- `microsoft-native-products.csv`, `microsoft-native-reconciliation.json`: complete downloaded native report; all 176 stable IDs and all 1,232 title, description, URL, primary image, GBP price, brand and catalogue-ID comparisons matched. All 176 were pending in this report.
- `microsoft-free-listings-enabled.txt`, `microsoft-automatic-updates.txt`: native settings.
- `microsoft-missing-public-images.json`: 20 additional image associations (18 distinct photographs) lacking an exact-hash public URL in the retained mappings. All 176 primaries had valid mappings. Microsoft documents that its content API currently does not use additional image links; do not claim that every selected photograph will appear on Bing.

Use the latest release receipt and native diagnostics for current status; this document's approval state is dated.

Official references: [Merchant Center and feed setup](https://help.ads.microsoft.com/apex/index/3/en/60048), [product field schema](https://learn.microsoft.com/en-us/advertising/shopping-content/products-resource), and [free product listings](https://about.ads.microsoft.com/en/blog/post/august-2020/product-listings-show-products-for-free-in-the-bing-shopping-tab).
