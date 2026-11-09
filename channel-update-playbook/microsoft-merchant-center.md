# Microsoft Merchant Center

Native setup verified on 7 November 2026. This is the product-catalogue route for Bing Shopping. The onboarding option **Import from Meta Ads** imports advertising campaigns; it does not create the sculpture product catalogue.

## Latest check — 8 November 2026

The correct existing import has populated **325 products: 0 Active, 323 Pending and 2 Rejected**. This is an import success, not public Bing visibility. The last server-side feed timestamp still reads **8 November at 11:24:21 GMT**. A single **Import now** refresh was requested at **22:41:37 UTC** after the website/Google corrections. Microsoft acknowledged **Import scheduled — Product data will update when the import finishes**. The later server timestamp has not yet advanced; do not report that refresh as processed or repeat it solely because the notification is gone. Recheck this same store/feed and export current offers before claiming the updated fields arrived.

Lunar Wave White (`76dc58c2-9754-4b21-a7f8-c6c844dc643c`) is wrongly classified under Disallowed Supplements and Health Products. A native exact-title filter confirms the single sculpture offer. The diagnostics view exposes **Request review for all**, covering that sculpture plus an unrelated Amanita greetings card; no all-product review was submitted. No Pinterest appeal, account payment method or advertising spend was added. Evidence: `outputs/channel-completion-20261108/continuation-2230/microsoft-refresh-intent.json`, the native scheduled acknowledgement, filtered sculpture and current overview receipts.

## Initial Google import — 7 November 2026, evening

The production source is now **Google Merchant Center 5664655454, Boldstone Sculpture**, signed in as `info@boldstone.co.uk`. Do not select the older account `550093983` offered first by the Microsoft wizard.

- Google primary source `Squarespace-1469f13b`, Merchant API data-source ID `10788949980`, has 325 website products. The native export matches all 176 established wall-sculpture URLs and current GBP catalogue prices. Its Google item IDs are variant UUIDs, not the Seller SKUs in the earlier manual feed. The native Google feed label is `US`; do not infer currency from that label. The checked wall-sculpture prices are explicitly GBP.
- Microsoft import **Website sync - GMC 5664655454** is saved for every day at **06:00, GMT Standard Time (London)**. Its Google-import feed is `1830968`, native name `GoogleImport_5664655454_20261107211433`.
- The first import was requested once and queued. At the last recorded check, the imported product count was still zero and no completed run was shown. A saved schedule is not evidence of a completed import, approval or Bing visibility.
- Old manual feed `1830841` was reversibly changed to **Use feed for testing only** and read back as **Test feed**. Keep that setting while the Google import is the production source. Its original 176 SellerSKU IDs do not overlap the Google UUIDs; allowing both feeds to serve would risk duplicate offers.
- No paid campaign, payment method or new advertising spend was added.

Evidence is in `outputs/catalogue-channel-imports-20261107/`, including `google-source-reconciliation.json`, `microsoft-google-daily-schedule.txt`, `microsoft-two-feed-identities.txt`, and `microsoft-manual-feed-test-only.txt`.

## Refresh after a catalogue update

1. Complete the app-to-website release first. The app owns specifications, catalogue inclusion, prices and image choices. Keep website product and variant identities stable.
2. Verify the current Squarespace Merchant API source in Google account **5664655454** has the intended website records, GBP prices, product URLs and primary images. Its total currently includes 149 non-wall-sculpture products as well as the 176 sculptures; a whole-account Microsoft import is broader than a wall-only file.
3. Let the existing daily Microsoft Google import run, or request **Import now once**. Never submit a second manual production feed as an unexplained workaround for a queued import.
4. Inspect the native import result, feed and product report. Match all 176 sculpture URLs and Google UUIDs, inspect other imported products separately, then reconcile GBP prices and images. Record pending, rejected and approved counts separately. If the count remains zero, record that no completed import was established rather than claiming successful publication.
5. Keep the old manual feed test-only. If a deliberate rollback is needed, first stop the Google import from serving and reconcile its current offers; then restore the reviewed manual payload. Do not serve both identity schemes together.
6. Check free Product Listings, diagnostics, price/availability safeguards and subsequent visibility. Do not add payment or advertising campaigns to solve a free-catalogue setup issue.

The daily import refreshes Google's current website catalogue. It does not publish unsaved app changes to Squarespace or refresh separate Pinterest/Google Sheets snapshots.

## Earlier manual upload — retained history

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

## Historical manual-feed procedure — rollback reference only

1. Complete the normal app-to-website release first. Freeze current specifications, complete image coverage and the image library. Keep the established publication scope and stable Seller SKU identifiers.
2. Generate one tab-delimited UTF-8 `.txt` feed from the current app. Every product must have a matching live website SKU, GBP selling price and current primary photograph. Stop if a check fails.
3. Use the current public title, complete description, finish wording, truthful availability and direct product URL. Use the existing public CDN image only when its source content hash matches the current Dropbox original. Never use a thumbnail preview list as the complete set of selected photographs.
4. Handmade products without GTIN or manufacturer MPN use `identifier_exists=FALSE`. Do not invent barcodes or identifiers. Do not introduce a free-delivery promise or guessed delivery charge. The current GB sculpture feed has no shipping-price field; native shipping settings are labelled US only.
5. Open Merchant Center → Boldstone Sculpture → Feeds → **Default Catalog** → Update feed. Update feed `1830841`; do not create another store or catalogue for a routine refresh.
6. Save a submission intent with exact file hash, scope, store and feed. Submit once, retain the native result and reconcile ambiguous outcomes before any retry.
7. Download the native Products CSV. Check the full SKU set, product count, GBP prices, titles and URLs against the submitted file. Inspect Diagnostics for product, feed and store issues. Distinguish pending, approved and rejected records.
8. Confirm free product listings remain on. Approval makes products eligible to display; it does not guarantee impressions or sales. Check subsequent product-listing performance separately from paid advertising.

This was the initial manual feed procedure. It is superseded for production by the Google import above. Its source files remain available for a deliberate, reconciled rollback. Automatic item updates are a useful price/stock safeguard, not a substitute for a complete catalogue refresh.

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


## Image-compatibility follow-up — 9 November 2026

The first requested refresh completed at8November23:28:09GMT. Native counts became325 total,0Active,308Pending,17Rejected. The detailed report has15 internal image-download errors, two editorial rejections,295image-crawl waits and13manual reviews. For the176sculptures:160pending,16rejected. Lunar Wave White remains the sculpture editorial rejection; the other editorial rejection is the unrelated greetingscard. Thirteen abstract sculptures have adult-content manual-review flags, which are pending, not rejected.

Public headers were checked for all1252distinct image URLs used by the current Google supplement.217 exceeded Microsoft's3.9MB imageLink cap; all were replaced only in the existing Google supplement with qualified renditions of the same photo paths, below1.5MB, no upscaling. Native Google processing and its combined325-offer export were independently verified; all176sculptures match all11fields, prices/IDs unchanged, all325Google offers Approved. Six of Microsoft's15download failures were over3.9MB; nine were already below it, so the size correction alone does not establish their recovery.

**One further import** was then requested through the existing Website sync - GMC5664655454 and acknowledged `Import scheduled`. Processing/publication is not yet verified. Do not queue another import based on an unchanged old success label: require an advanced native completed-feed timestamp and per-offer readback. Keep manualfeed1830841test-only. No paid ads, support messages or all-product review requests were submitted.

Receipts: `outputs/channel-completion-20261108/continuation-2230/microsoft-refresh-status.json`, `microsoft-rejection-report.csv`, `merchant-image-header-audit.json`, `google-rendition-after-verification.json`, `microsoft-rendition-refresh-intent.json`. Official limit: https://learn.microsoft.com/en-us/advertising/shopping-content/products-resource?view=bingads-13 .
