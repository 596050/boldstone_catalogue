# Google, Microsoft and Pinterest catalogue operations

Verified 8 November 2026. The sculpture app is the source of product facts. Saved records, approval, public visibility and completed checkout are separate outcomes. Earlier dated observations are retained in release packets; the current statuses below supersede them.

## Master and release files

Resolve the current workbook through `sculpture-catalogue/current-master.json`. It contains 181 component records, 176 publication products, 12 sheets and 32,776 formulas. Current evidence is in `outputs/channel-completion-20261108/`; verify the receipt linked by the pointer before claiming the latest revision. The original release is in `catalogue/`; the original-photo/Brandboom follow-up is in `catalogue-followup/` and becomes current only after its revision-guarded upload and complete byte readback pass.

- Dropbox master: `/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx`, ID `id:cnqzTNngPVsAAAAAAA7JEQ`.
- Private Google master: https://docs.google.com/spreadsheets/d/1T-t6Mgy_TiMKzV8P45o1hvH2tpndicPO8Pq05KG8ZAs/edit . **Refreshed in place on 8 November** from the current Dropbox master: 181 records, 888 columns, twelve sheets. Same document ID, owner `info@boldstone.co.uk` and private sharing retained. Fresh native export independently compared across 567,089 cells, with all 32,776 formulas and intended tables preserved. All twelve native sheets were visually inspected. The existing Dropbox file `catalogue_wall_sculptures_google_sheets_backup.xlsx` was revision-updated and downloaded again for exact byte readback.
- Separate public retail feed: https://docs.google.com/spreadsheets/d/1PVhR1H-GFaojV_G7Khh0Vt3IwFL1RBHyLLzvXGIT-BQ/edit . Owned by `info@boldstone.co.uk`; 176 rows, 46 fields.
- Hosted CSV: https://docs.google.com/spreadsheets/d/1PVhR1H-GFaojV_G7Khh0Vt3IwFL1RBHyLLzvXGIT-BQ/export?format=csv . Only 21 existing additional-image cells changed on 8 November. All public values were read back; prices and identities are unchanged.

Sheets are snapshots, not installed app-to-Sheets automation. Never expose costs, labour, margins, private account or task fields in the public source. Do not widen sharing when a connected profile lacks write access; use the authorized owner session. The private master stays Restricted.

**Google date-conversion regression, corrected 8 November:** the first native readback exposed 1,832 missing timestamps. Their source OOXML cells used `t="d"` with UTC ISO values, which Google dropped during import. The authoritative workbook now stores those exact instants as numeric Excel dates with a UTC millisecond format; original strings remain in the exact patch manifest. Independent Calamine readback verifies each instant within one millisecond. The corrected native export retains all 1,832. Do not accept an import on a Saved message alone: compare all populated cell values, formulas, errors, table counts and date fields after conversion. Nine stale snapshot labels were clarified as retained/base exports or dated channel evidence. Prices, labour, stock, GTINs and photo decisions were preserved.

The Google engine rounds three existing Faire planning `ROUNDUP` calculations one penny differently from the Excel cache. Each matches exact decimal upward rounding and retains the same formula; adopted retail prices have no differences. Evidence: `outputs/channel-completion-20261108/continuation-2230/google-date-refresh-verification.json`; date manifest and guarded master publication: `catalogue-google-dates/`. The private refresh did not touch the public Pinterest source: all 176×46 public cells were read back unchanged, with costs and audit fields still private.

Before any later Google import, run `python3 channel-update-playbook/automation/check_google_sheet_import.py /absolute/path/to/catalogue.xlsx`. A typed-date or formula-error hold must be reconciled before importing. This is read-only preflight, not proof of successful conversion: follow it with native export and independent comparison. The actual regression input has 1,832 typed dates and is held; the corrected master passes with all 32,776 formulas retained. Existing private sharing and document IDs must be verified before and after every refresh.

## Website and policies

All 62 retail titles now use the catalogue's Finish wording on the existing products and homepage cards. All 176 titles, GBP prices and stock reconcile; product/variant IDs are unchanged.

All 1,437 selected photo placements, representing 1,063 Dropbox identities, are in the 176 main carousels. Twenty missing secondary photos were appended once. Dune Ripple I - Verdigris Finish's selected primary was put first, retaining all eight photos. Exact source identity/content-hash checks, final native export and public pages were verified.

Squarespace CSV imports do not update Hosted Image URLs on existing products. Use native image controls, save once and verify the saved export plus public page. Never recreate a product for photo updates. Preserve alt text, order, prices and stock. Reference: https://support.squarespace.com/hc/en-us/articles/115000378108-Importing-products-from-a-csv .

Shipping, Returns and FAQ now agree: catalogue dispatch within ten working days; bespoke timing separately agreed; transit additional. Customer pays actual change-of-mind return postage. The saved policy specifies a 30-day request window, 14 days to return and the applicable refund timing/statutory rights. Ordinary catalogue casts are not silently treated as personalized goods. Exact saved/public receipts are in the release packet.

## Google Merchant Center

Use **5664655454**, info@boldstone.co.uk, primary **Squarespace-1469f13b**, Merchant API source **10788949980**. Do not use old account 550093983. Source label US does not imply USD; explicit prices are GBP.

Final native overview: **325 Approved, 0 Limited, 0 Not approved, 0 Under review**. All 176 publication UUIDs are present. Approval is eligibility, not proof of impressions or sales.

Existing supplement **10789003059** was updated without adding products. Its 11 fields are id, title, description, price, image_link, additional_image_link, shipping_weight, custom_label_0, custom_label_1, max_handling_time and brand. All 176 matched and updated, all attributes recognized, no processing issues. A later combined export matches every field, including the registered spelling **Boldstone**. Other 149 offer brands are unchanged. Removing this mismatch does not prove brand letter case caused the Manufacturer failure.

Future refreshes must retain stable UUIDs and all existing overrides. Read back combined offers after propagation; a successful upload alone is insufficient. If an early export is stale, allow propagation instead of resubmitting blindly. Google/Pinterest support a main image plus up to ten secondary images; prioritize newly selected photos within the cap. Website galleries can contain more.

## Manufacturer Center and genuine GTINs

Account **5898308482** has an Active link to correct Merchant account **5664655454**, but zero variants. The earlier Approved-brand snapshot is superseded. On 8 November **Boldstone, brand 301096324**, was rejected for low logo image quality, requiring at least 800 × 800 pixels.

The genuine 1,254 × 1,254 original was recovered from `/BOLDSTONE MASTER/Documents/Logos/Boldstone Sculpture transparent square logo.png`, ID `id:cnqzTNngPVsAAAAAAA5RAQ`, revision `65da403af0a820c0dea29`. Exact bytes/content hash/dimensions and design were verified. The existing brand was saved once with this original; the logo error disappeared and native status is now **Brand review pending**. Do not edit repeatedly or claim approval.

No genuine GTIN allocation was located in checked master/local records or targeted business-mailbox searches. An allocation under another email remains possible. Manufacturer Center requires genuinely assigned GTINs. Handmade-product exemption in Merchant Center does not establish Manufacturer Center eligibility. A SKU, invented checksum-valid number or another brand's barcode is not acceptable.

Owner action: supply an existing Boldstone GS1 allocation, or establish the correct turnover-based licence and approve its purchase. No subscription may be purchased without commercial approval. Assign one identifier per distinct sellable component/finish and retain licensee/assignment evidence. Then project the same genuine identifiers to website, Merchant and Manufacturer records. Await brand approval and verify actual daily sync, imported count and per-product status.

Official: https://support.google.com/manufacturers/answer/7494888?hl=en and https://support.google.com/manufacturers/answer/10562928?hl=en .

## Pinterest approval

Catalogue **4814500935893**, business **846254723639262523**, source **1536497259764**. UK, English UK, GBP and daily **07:00 Europe/London** remain saved. Website is claimed, Instagram connected and profile website points to boldstonesculpture.com.

Source remains **Disabled / Not approved**. No products are confirmed live. Zero distribution issues with zero ingested products is not approval. Fresh native View issues lists minimum product requirements and minimum website quality requirements, without identifying individual product IDs. Its reassessment route is **Submit appeal**, with two appeals remaining. Owner instruction is **no appeals**; none were entered/submitted. Do not recreate the source to bypass this gate.

Earlier measured title discrepancies, missing selected website photos and policy conflicts are corrected. Existing hosted CSV is reachable and its 176 records are read back. These corrections do not establish approval.

There are **96 primary-image dimension checks** against Pinterest's documented minimum width 1,000 and height 1,500 pixels. These are measured checks, not proven item-level rejection causes. Review exact components at http://127.0.0.1:8767/#specifications?platform=pinterest&task=primary_image_size . Use a genuine larger original of the correct product/finish or select an appropriate existing original. Do not upscale small pictures and claim extra captured detail.

Follow-up checked all 96 original dimensions, not only hosted previews. Two Lava Moonshell originals were streamed into memory, independently checked against their exact Dropbox revisions/content hashes, and measured at 1,200 × 1,200; no downloaded original copy was retained. **28 products have 41 qualifying selected Listing placements using 39 distinct existing photos**. Their already-hosted public URLs also meet the documented dimensions, checked through bounded image-header reads. The other **68 have no qualifying alternative among currently selected Listing photos**; this is not a claim that every unselected or new photograph has been exhausted. Owner review: `outputs/channel-completion-20261108/pinterest-photo-alternatives.html`. App tasks include exact candidate names, identities and dimensions. Primary/Listing choices remain unchanged until reviewed.

Further read-only checking covered 2,385 associations for the remaining 68 products and bounded original headers for 25 plausible candidates. Twenty-one unselected originals across four more products meet the dimensions: Bone Spiral II White, Lunar Phase II White, Lunar Phase IV Silver Finish and Lunar Water Catcher White. Small provider previews were visually checked; shadows/orientation still require owner review. These are not Listing or Primary selections. Exact current Dropbox revision/size/provider-hash metadata and image headers were checked; the full original hash was not recomputed. See `outputs/channel-completion-20261108/pinterest-unselected-photo-options.json` and the contact sheets linked in the photo review. This was not an exhaustive search of every Dropbox file.

Finish photo review, keep accurate price/stock and accessible checkout/contact/policies, then the owner must choose whether to use Pinterest's offered appeal route. Following approval, verify an actual completed ingestion, accepted product count and public Product Pins. Claimed sites, Instagram auto-publishing and RSS are not catalogue approval. Verified Merchant Program eligibility is separate from ordinary merchant approval.

Official: https://policy.pinterest.com/en/merchant-guidelines and https://help.pinterest.com/en/business/article/before-you-get-started-with-catalogs .

## Pinterest tag and consent

Tag **2612823030261** is saved in the existing Squarespace header with GA4/Meta preserved. Marketing consent gates loading/events independently from performance consent. No email transmission or no-script bypass. Exact 176 UUID mapping, validated GBP/value/quantity and fail-closed unknown/mixed baskets.

Native private-browser testing on 8 November verified matched PageVisit, confirmed AddToCart and InitiateCheckout at HTTP200 for Brancusi Totem White: exact product UUID, GBP79.62 and quantity1. Existing browser protections were unchanged; no AdBlock pause was needed. A genuine pointer click and settled cart quantity were required. Accessibility activation changed the cart but correctly did not satisfy the trusted analytics click guard. A Network filter must be committed with actual input; merely setting its displayed value gave a misleading empty trace.

Separate-category testing reproduced and fixed a real defect: a shared view key suppressed the first event for a destination consented later. The canonical shopping funnel now keeps independent GA4/Pinterest view keys. Both grant orders were verified live: analytics-only then advertising, and advertising-only then analytics. Each destination gets one product view; advertising withdrawal and a fresh denied reload produced zero Pinterest requests and zero SDK loads. GA4 can batch `view_item` in a POST payload, so query-string filtering alone is not sufficient evidence of absence. Seventeen logic checks pass. The exact saved footer was reloaded and read back. The cart was cleared and the private QA window closed; no customer/payment details, order or purchase event were submitted.

This is one representative live product test, with all176 configured mappings retained; it does not prove every product or a completed purchase. Completed-order tracking remains unverified and requires a genuine bounded end-to-end check. Receipt: `outputs/channel-completion-20261108/consent-fix/verification.json`.

Code/tests: `automation/pinterest_tag.js`, `automation/shopping_funnel.js`, `automation/test_pinterest_tag.cjs`. Run `node channel-update-playbook/automation/test_pinterest_tag.cjs`. Prepare future artifacts using `automation/build_pinterest_tracking.py CONFIG_JSON OUTPUT_DIR`; it makes no live writes. Do not regenerate the historical 8 November packet with its original `build_tracking.py`, which preserves the pre-fix shared-key implementation. Verify the exact current footer, replace only its existing funnel block, read back before saving, then reload and compare persisted source. Native CodeMirror typing altered formatting/trailing characters during QA; exact multiline paste plus readback was reliable. Official event names: https://help.pinterest.com/en/business/article/add-event-codes .

## Microsoft Merchant Center

Store **50112622** is populated from correct Google account 5664655454. Daily import **Website sync - GMC 5664655454**, feed 1830968, 06:00 London. Native readback: **325 imported, 0 Active, 323 Pending, 2 Rejected**, including 311 image-crawl waits and 12 manual reviews. Import works; visibility remains pending.

**Lunar Wave - White**, UUID `76dc58c2-9754-4b21-a7f8-c6c844dc643c`, is incorrectly classified as Disallowed Supplements and Health Products. Resolve that sculpture-specific editorial issue. Other rejection is an unrelated greetings card; do not request review of all products. Old manual feed 1830841 remains test-only to avoid duplicate identities. No advertising spend/payment method added.

## Brandboom restoration

Native restore completed: **176 existing products/SKUs updated, zero added**. The native all-product export was downloaded and independently matched on all 176 SKUs and thirteen fields: **2,288 comparisons, zero differences, zero inactive products**. The export contains no photo columns; do not infer gallery completeness or public Marketplace publication from it.

Sample Wave and Moonshadow II - White (BOLD-B6EC1EDD319F) had eighteen native photos against seventeen selected source identities. Native media 34736843 was byte-identical to retained 34706371 (SHA-256 `eca21f68ec7377e33020d92da5d6b43287354d7d06334b2d772802b318540d4f`). Only the extra association was moved to the recoverable Media Bin. Saved once, browser reloaded and the existing product reopened: all seventeen expected thumbnail identities persisted; primary 34706366 and wholesale £109.25 were unchanged. Two other byte-identical rendered photos correspond to distinct owner-selected Dropbox records and were retained. Other native galleries have not received this exact review; do not repeat bulk image imports. Recovery/action reference: https://support.brandboom.com/en/articles/14121356-add-copy-remove-and-reorder-product-images .

Deleted previews 681061/681160 were empty after reload. One replacement **681169 — Wall Sculptures - 50 Preview** contains the exact saved 50-SKU selection. Owner-only: https://www.brandboom.com/app/a/8BB0EB70AC2 . Wholesale only, prepacks off, ordering disabled, no share links, no Marketplace submission. Native preview shows a blank future-shipping heading with ordering disabled; recorded as a display issue, not a delivery promise. Editor: https://manage.brandboom.com/products/s/111089/p/681169 .

Plan limit 50, genuine retail-price choice and Marketplace requirements remain separate. No paid upgrade/agreement accepted.

## App tasks and social publications

App 2.19.0 has dated task badges for 20 platforms on each component, including platform/task filters. 181 records represented; five held/excluded products not targeted. Relevant field/photo edits or seven-day age make checks stale; invalid evidence becomes Unknown. Current 96 Pinterest photo tasks and Manufacturer brand-review wait are installed. Website/Google verification is separate from pending approval/publication and unknown native readbacks.664 Python and321 UI tests passed for the release.

This continuation published **five additional posts each to Instagram, Facebook and LinkedIn**. Meta saved exact Commerce variant title/price tags; LinkedIn tracked product destinations were verified. All 15 have unique native permalinks, full caption readback and photos in `outputs/channel-completion-20261108/`. Earlier 8 November ten LinkedIn/five Instagram posts remain in `outputs/product-social-approval-20261108/` and were not duplicated. AppleScript runner remains not live-validated; successful native Chrome posting is independent of it.

## Other pricing boundaries

Furnitures/Faire observations remain separately dated and were not refreshed by this release. Faire actual wholesale prices remain below protected model; approximately 3.77× shared-retail proposal is unapproved and not applied to website/Brandboom. Keep actual native prices separate from proposals; never advertise discounts against an RRP not genuinely adopted.


## Image and gallery follow-up — 9 November 2026

This dated readback supersedes the earlier gallery and Microsoft counts above. Native Google Merchant account 5664655454 accepted an update of the **existing** supplement 10789003059: 176 updated/matched, all attributes recognised, no issues. The combined export was independently checked on all eleven fields for all176 sculptures; prices, UUIDs, photo paths/order and the other149 offers are unchanged. All325 account products remain Approved at the dated check.

A header audit found217 primary/additional photo URLs above Microsoft's documented3.9MB limit. All217 now use qualified1000w renditions of the **same** provider assets, below1.5MB, without upscaling or changing app/website photo choices. This is a feed compatibility correction; the nine small images that previously failed with Microsoft's internal download error are not proven fixed until its new result arrives. Official cap: https://learn.microsoft.com/en-us/advertising/shopping-content/products-resource?view=bingads-13 .

Every existing Brandboom product gallery was inspected: **176 products,1437 selected photo placements**, primary first. Fourteen further excess-photo cases were repaired. Three sideways renditions were replaced with upright renditions of their existing selected photos. Each repair was saved, the page reloaded, and the exact ordered IDs/count/primary/title/wholesale price independently reopened. Seventeen removed associations have no other-product references; old media remains in the recoverable native Media Bin. No Dropbox originals were deleted and zero products were added. Owner-only50-product preview remains unsubmitted; editor completeness is not Marketplace publication.

Brandboom's From Link uploader twice finished at the image host but failed to register media, with native Console `UploaderPublicApi is not initialized`. Do not blindly repeat uploads. Reload the existing product, activate its photo placeholder, use From device with an exact verified filename, wait for finished then Done, select the new media and verify exact gallery IDs before Save. The native Go To path must be set explicitly and read back before Return; clipboard paste can restore stale contents. Reopen after Save and retain a receipt. Source photos in this follow-up came from correctly oriented existing website renditions; no AI photos or local transformations were used.

Pinterest's9November native check still reports minimum-product and minimum-website-quality failures and0 approved items. Its displayed re-evaluation route is an appeal. **No appeal was entered or submitted**, as instructed. Manufacturer brand301096324 is still Brand review pending and its variants table is empty. Genuine GTIN allocation remains required; no identifier was fabricated or bought.

Evidence: `outputs/channel-completion-20261108/brandboom-gallery-audit/verification.json`, `continuation-2230/google-rendition-after-verification.json`, `continuation-2230/microsoft-rendition-refresh-intent.json`, and `catalogue-image-followup/`. App evidence was atomically refreshed and all181records/20platforms read back without source errors; product facts, costs, zero labour, prices, stock and photo choices are preserved. Use the current-master pointer and release receipts for current Dropbox/private-Google status.


The9November release is now saved and fully read back: current master has181records,905columns and32776formulas. All4444scoped evidence cells pass two independent readers;497630unrequested cells and all other OOXML parts are preserved. Existing Dropbox master revision65fcd5ca583a90c0dea29, SHA256 `22f9731687e049ea27910633fec22716b3cc7ad0e6aaf3a95dfb553da6d12e62`. The existing private info@ Google document was replaced in place after a567089-cell owner-edit check found zero changes; its570285-cell export comparison found zero unexpected differences. All12native sheets were visually inspected;1061refreshed evidence timestamps survived conversion. Existing Google-native Dropbox backup revision65fcd691c6a2e0c0dea29 was downloaded again and matched byte-for-byte. The public Pinterest feed remains exactly176×46 with all cells unchanged; no private fields were projected. See `catalogue-image-followup/final-release-verification.json`.

Microsoft's final read-only recheck still showed completed overview timestamp8November23:28:09GMT,0Active/308Pending/17Rejected. The feed row's date advanced to9November, but that alone is not proof the new import completed. No additional import was requested. The source correction is verified; Microsoft processing/rejection recovery remains unverified.


## Automatic catalogue synchronisation design — 9 November 2026

**Status: design prepared, not installed.** The matching Google/Dropbox copies above are verified release snapshots, not an automatic synchronisation service. The current app's background Dropbox image-inventory refresh does not export or publish this workbook. No catalogue sync LaunchAgent was found. The available Google Drive connector returned404 for the private info@ master on9November; this does not mean the native document is absent. Its existing browser access is separate from unattended API authority.

The app remains the product source of truth. On a committed app change, queue a workbook publication; coalesce rapid saves and reconcile every five minutes plus daily. Resolve the master from `sculpture-catalogue/current-master.json`, preserve stable component IDs, all twelve sheets, formulas, dates, private costs and platform-prefixed records. Maintain one logical version for the app snapshot, master and both cloud outputs. A worker publishes only actual changes to the existing Dropbox file and existing native Google document, retaining their identities and privacy. It must use official APIs, not browser automation.

Two cloud writes cannot be one atomic transaction. Keep a durable intent, one writer lock, per-target states and independently read-back receipts. Dropbox writes use its current revision as the precondition. Before Google updates, compare current cells/formulas against the last verified baseline to detect direct-owner edits. If either copy changed independently, hold that release and report the exact conflict; do not silently overwrite. A timeout triggers readback first, not an unexplained repeat upload. Retry only transient/idempotent work with bounded backoff. Show the app's desired version and each target's last successful version, error and timestamp. A partial release remains visibly partial until both readbacks pass.

The public Pinterest retail feed remains a separate, allow-listed projection. Never expose private manufacturing costs, task JSON or the whole master publicly to avoid OAuth. A scheduler on this Mac runs only while the Mac/app is available and catches up after restart;24/7operation requires an approved always-on host. There is no need to change the existing Google document ID or widen sharing to make this work.

Activation still requires a complete app-to-workbook projection and an approved direct Google OAuth connection as info@boldstone.co.uk, with offline access and the narrowest selected-file permissions supported. A connector grant cannot simply be copied into a standalone cron job. Store refresh credentials in Keychain/host secret storage, not this repo, a public URL or a sheet cell. Verify unchanged versions, real source changes, other-cloud failure, timeout-after-commit, conflicting edits, revoked authorisation, invalid dates/formulas and restart recovery before enabling unattended writes. Prepared target/trigger contract: `automation/catalogue_sync_plan.json`.

Official references: https://developers.google.com/workspace/sheets/api/guides/batchupdate and https://developers.google.com/workspace/sheets/api/limits . Apps Script time triggers are another option after owner authorisation, but they do not by themselves connect the local app or provide a safe complete workbook projection.

## Obtaining genuine GTINs for Boldstone — 9 November 2026

Recover an existing Boldstone GS1 allocation if one exists. Otherwise join GS1 UK using the correct legal trading entity, annual turnover and number of product variants; membership is an annually renewed licence. The published entry tier includes only10GTINs, so it does not cover176variants without added capacity. Obtain the exact appropriate membership/top-up quote rather than claiming the smallest advertised fee covers this catalogue.

Use My GS1 → My Numberbank to allocate a unique GTIN-13 to each sellable design/size/finish variant, using its stable catalogue ID and SKU as the crosswalk. An identical model/finish manufactured again uses the same product GTIN; platforms use the same GTIN for that variant. A changed customer-facing name, price or photograph does not on its own require a new identifier. Material/size/finish changes and sellable sets need the appropriate GS1 variant/packaging assessment. Never reuse a retired number for a different product, borrow another brand's barcode, or treat a generated checksum as proof of allocation.

Download the account-specific My Numberbank XLSX template, preserve its headers and required fields, populate it from the176publication products, and use the portal's allocation/import workflow. Verify assigned records and licence-holder/product matching, retain the allocation export/receipt and add the confirmed numbers and verification dates to the master register. Only then update website, Merchant Center, Manufacturer Center and other channel records. Generating an EAN barcode image comes after genuine number allocation. Manufacturer Center's brand review remains a separate gate; supplying identifiers does not guarantee approval.

Official references: https://www.gs1uk.org/knowledge-hub/membership/how-much-does-gs1-uk-membership-cost , https://www.gs1uk.org/standards-services/data-services/my-numberbank , https://www.gs1uk.org/knowledge-hub/my-numberbank/finding-your-export-and-import-template-with-step-by-step-guide-to-bulk and https://support.google.com/manufacturers/answer/6124116?hl=en . No account was created, terms accepted, licence purchased or GTIN allocated during this design check.


Owner confirmed annual turnover **below£100,000**. The live official GS1 UK plans page, with Up to£99,999 selected, shows10codes at£50/year,100at£100/year, and**1000at£130/year**, all excluding VAT. The1000-code plan is the smallest displayed option that covers176publication variants. This is the total displayed annual plan price, not a£130top-up added to£50. Source: https://www.gs1uk.org/about-us/membership/get-a-barcode#plans . Native AX/screenshot and the dated proposal are retained in `outputs/catalogue-sync-gtin-20261109/`. No membership application, payment, agreement acceptance or allocation was submitted. Reconfirm the payable checkout price before an authorised purchase.
