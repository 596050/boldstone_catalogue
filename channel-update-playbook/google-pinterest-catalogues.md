# Google, Microsoft and Pinterest catalogue handoff

Verified 7 November 2026. The app remains the source of truth. These native status observations do not imply checkout, payment or approval success.

## Current records and snapshots

The master contains 181 component records, 12 sheets and 31,896 formulas. The current publication scope is 176; retain the five deferred/excluded component rows in the private master. Resolve the current local workbook through `sculpture-catalogue/current-master.json`. The release packet is `outputs/catalogue-channel-imports-20261107/`, with a narrow finish-title correction under `finish-titles/`.

- Private native master, owned by `info@boldstone.co.uk`: https://docs.google.com/spreadsheets/d/1T-t6Mgy_TiMKzV8P45o1hvH2tpndicPO8Pq05KG8ZAs/edit
- Public retail-only Pinterest feed, same owner: https://docs.google.com/spreadsheets/d/1PVhR1H-GFaojV_G7Khh0Vt3IwFL1RBHyLLzvXGIT-BQ/edit
- Daily-ingestion URL: https://docs.google.com/spreadsheets/d/1PVhR1H-GFaojV_G7Khh0Vt3IwFL1RBHyLLzvXGIT-BQ/export?format=csv

The private master is Restricted. Only the separate retail feed is public. Never expose manufacturing, labour, platform margin or private account fields through the Pinterest sheet. The Dropbox documents folder contains the master XLSX, the native Google master XLSX export, and retail-only Pinterest CSV/XLSX backups. Read the final `dropbox-receipt.json` before claiming their current revision.

Google Sheets are verified snapshots, not an installed app-to-Sheets automation. A changed app/website catalogue requires a deliberate refresh of the existing sheets and Dropbox files. Native conversion drops some ISO timestamp cells; preserve them as plain text and independently compare the exported native workbook. Google changes internal mapping hyperlink display labels to “View mapping” while retaining their exact destinations. Its calculation engine can differ by one penny on the ROUNDUP auction asking-price reference; record and check the exact formula/Decimal ceiling separately. Core retail and manufacturing values must match.

## Correct Google source and Microsoft import

Use Google Merchant Center **5664655454 — Boldstone Sculpture**, `info@boldstone.co.uk`, primary source **Squarespace-1469f13b**, Merchant API source **10788949980**. Its 325 total products include the 176 wall sculptures. All 176 URLs and explicit GBP prices reconcile to the catalogue. Native source label `US` is not evidence of USD currency. Do not use older account **550093983**.

Microsoft store **50112622** has the saved daily **06:00 London** import **Website sync - GMC 5664655454**, feed **1830968**. The first run was requested once; the final native check still showed **zero imported products and no completed run**. Do not equate the schedule with completion. Old manual feed **1830841** is test-only to avoid serving duplicate SKU and Google UUID identities. Follow `microsoft-merchant-center.md` for reconciliation. No advertising spend or payment method was added.

Google's native titles omit “Finish” on 62 publication products compared with the current app naming policy. The workbook preserves actual native titles separately. Prepared Pinterest titles now use `finish_retail_name` from the app. This release does not claim to have changed the 62 native Google or website titles.

## Manufacturer Center

Manufacturer account **5898308482** already has an **Active** link to merchant account **5664655454** and an **Approved** Boldstone brand. Its native variants list is empty. Manufacturer Center requires valid GTINs; none is verified for these handmade sculpture records. Merchant Center's handmade-product identifier exemption does not establish Manufacturer Center eligibility. Never manufacture GTINs or put Seller SKUs into MPN fields without a real manufacturer identifier. Brand casing differs between the approved brand and the native merchant feed; do not assert that casing is the cause without evidence.

References: https://support.google.com/manufacturers/answer/6124116?hl=en and https://support.google.com/merchants/answer/13886707?hl=en

## Pinterest

Catalogue **4814500935893**, business **846254723639262523**, source **1536497259764**, name **Boldstone Wall Sculptures - website retail**. The 176-product, 46-field template feed was validated and saved. UK, English UK, GBP, every 24 hours at **07:00 Europe/London** are saved.

The source is **Disabled / Not approved**, with no upcoming ingestion. Pinterest reports minimum product and website quality requirements at merchant level. There is no verified accepted product count or public Product Pin publication. Two appeals remain; no appeal was submitted. Do not recreate the source or claim automatic ingestion is running while Disabled.

Use stable Google variant UUIDs matching the website. Read the complete `/api/coverage` selection sets; `/api/specifications` returns a bounded six-photo preview. Reconcile current original identity/content hash before reusing existing public CDN URLs. Do not invent GTIN, MPN, ratings, reviews, free shipping or a fixed delivery quote. The template's optional unsupported fields remain blank. Pinterest does not support Dropbox file links as its hosted source; use the retail Google sheet export URL above.

## Current publication status of the three requested platforms

| Platform | Verified native status | Remaining limits |
|---|---|---|
| Furnitures.co.uk | 176 products, all Active; current title, price and stock observations refreshed | Stripe payouts are advertised as arriving in a later release. Checkout and payout success were not verified. Preserve its actual 10% fee-uplift prices separately from core retail. |
| Faire | 176 Published, 0 Unpublished, 0 Drafts; fresh export matched by SKU and existing product token | GBP bank-account action remains. All 176 native wholesale prices remain below the protected pricing model and RRPs differ from website retail. Actual export fields were recorded; proposed protected prices were not applied. Native Customizable = No also differs from the custom-design offer in copy. |
| Brandboom | All 176 products exist in the editor | Current 50/50 plan limit; presentation 681061 shows only 50 in an owner-only preview, with no public share link. This does not establish 176 public or Marketplace-live products. No paid upgrade or Marketplace agreement was accepted. |

Refresh actual native export observations in the existing `faire_`, `furnitures_`, `brandboom_`, `google_merchant_`, `microsoft_merchant_`, `google_manufacturer_` and `pinterest_` fields. Do not overwrite actual observations with proposed targets or create duplicate product records during a routine release.
