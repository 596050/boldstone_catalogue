# Saatchi correction and Microsoft Merchant Center — 7 November 2026

## Verified native results

Ammonite Petite II (Right) – White, SKU `BOLD-EFBAEB31C2B1`, existing Saatchi artwork `14393353`: **US$265 saved and independently reloaded**. The edition of 50, available quantity of one, 24 kg crate and other non-price controls were preserved. Evidence: `saatchi-price-receipt.json`, `saatchi-persisted.txt`, `saatchi-price-265-verified.png`.

The existing Dropbox master workbook was updated at **17:50 UTC** and downloaded again for byte verification: revision `65fb35b9ca27e0c0dea29`, SHA-256 `0ca847a397ffdb139726b6ddcf3cb63f9737283a39e89aed8289682f2eb6e111`. Exactly three Saatchi observation cells changed; all 181 records, 12 sheets, 31,896 formulas and all other values were preserved. The local current-master pointer now identifies this verified file.

Microsoft Merchant Center: account-only onboarding completed without adding payment or importing an advertising campaign. Created **Boldstone Sculpture**, store `50112622`, using the existing verified `boldstonesculpture.com` Bing Webmaster domain. Reused its automatically created **Default Catalog**, feed `1830841`. The 176-product feed was submitted once.

The downloaded native report contains exactly the 176 submitted stable IDs. All **1,232** comparisons passed for title, description, product URL, primary image URL, GBP price, brand and catalogue ID. All **176 are Pending**. Microsoft states store approval can take up to three business days. Approval and public display have not been established. The performance overview still showed zero in its summary widgets at this stage; the current Products table and downloaded product report establish the imported count.

Free Product Listings are **on**. Automatic website price and availability updates are **on**. Full-feed refresh remains manual; use `channel-update-playbook/microsoft-merchant-center.md` for the refresh and verification procedure.

## Source and scope

The current app is the product source of truth. The publication scope remains the established 176 products, within 181 component records. The feed uses current app descriptions and titles, explicit GBP prices, existing stable Seller SKUs, and content-hash-matched public image URLs. It does not invent GTINs or manufacturer MPNs or introduce a free-delivery promise.

Every website product was checked for its expected SKU, GBP price and current primary photograph before uploading. Eighteen distinct additional photographs, representing 20 image associations, lacked a retained exact-hash public URL. All primaries were mapped. Microsoft documents that it currently does not use additional image links in its content API; feed acceptance does not establish that all selected photographs will be displayed.

## Receipts

- `microsoft-feed-manifest.json`: local payload identity, source revision and native submission status.
- `microsoft-feed-uploaded.txt` / `.png`: native accepted upload, pending editorial review.
- `microsoft-products-176-pending.txt` / `.png`: 176-product table.
- `microsoft-native-products.csv`: downloaded account report.
- `microsoft-native-reconciliation.json`: complete product/field comparison.
- `microsoft-free-listings-enabled.txt` / `.png`: free-listing setting.
- `microsoft-automatic-updates.txt`: automatic price and availability setting.
- `workbook/`: narrow three-cell catalogue update recording the successful Saatchi price save, with preservation and independent reader checks. Check `workbook/dropbox-receipt.json` before treating its upload as complete.

No broader platform publication status, further Instagram posts, or whole-catalogue Saatchi completion is implied by this bounded release.
