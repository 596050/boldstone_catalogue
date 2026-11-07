# Checklist for every product update

Create one release record before starting. Record `PASS`, `FAIL`, `PENDING` or `NOT APPLICABLE` with evidence; do not mark a channel complete solely because an upload succeeded.

## 1. Capture the change and preserve recovery

- [ ] Give the release a date/time and unique ID; identify the operator and exact scope.
- [ ] Record changed component IDs and stable Dropbox file IDs, revisions and content hashes.
- [ ] Classify each change: new item, rename, merge, exclusion, deletion, finish, price, specifications, image content, image purpose, primary, shipping or stock.
- [ ] Save a consistent review export/database backup and the current catalogue source hashes/event cutoff.
- [ ] Save current platform IDs, product URLs, prices, gallery order and publication state for affected products.
- [ ] Check Jobs for in-flight moves, renames and uncertain deletions. Reconcile uncertain results before another write.
- [ ] Ensure no unsaved editor changes or concurrent publisher can be overwritten.

## 2. Reconcile Dropbox with the app

- [ ] Run **Check now** and wait for a successful complete inventory check, with a fresh timestamp.
- [ ] Confirm the expected account/root and pagination/cursor completion; an incomplete inventory must not imply deletion.
- [ ] Check additions, moved files, renamed folders and deleted originals by stable ID.
- [ ] Confirm changed bytes invalidate old image approval and have been reviewed again.
- [ ] Review each new component/finish candidate; an In Situ or Details folder is not a separate saleable sculpture.
- [ ] Resolve aliases and merged products while retaining historical mappings; do not create duplicate finishes.
- [ ] Ensure removed/excluded components remain excluded after refresh.
- [ ] Inspect previews and original dimensions; a cached thumbnail is not evidence of original resolution.
- [ ] For Saatchi primary images, verify at least 1500 pixels wide and 1200 pixels high in the intended viewing orientation. A 1200-wide portrait fails even when its long edge exceeds 1500. Do not upscale, pad or turn the sculpture sideways to satisfy the check.
- [ ] Verify group photographs are associated with the correct individual components.

## 3. Finalise catalogue choices

- [ ] Confirm inclusion/exclusion for every changed component.
- [ ] Check retail name, original name, family, finish, SKU and exact platform mapping.
- [ ] Check dimensions, weight, fixings, availability, lead time and current specification values.
- [ ] Check [platform-required fields](platform-requirements.md): brand, product type/model, exact SKU, colour/appearance, quantity, material, dimensions, package and identifiers. Preserve unknown barcode, manufacturer, origin and artwork-edition details as gaps; never invent them.
- [ ] Apply 10 working days by default and three only for the platform routes requiring it. Read back the native handling setting and matching description; hold products if an account requires a shorter deadline the owner has not confirmed.
- [ ] Preserve the qualification of extrapolated values; do not describe an estimate as a physical measurement.
- [ ] Check design/inspiration copy, finish description and outdoor/fixing wording.
- [ ] Include exactly one material point: "Made from a gypsum-based material." Add an applied surface-effect point for recorded decorative finishes; preserve imitation gold-leaf wording. Remove contradictory base-material claims and keep the Royal Mail tariff paragraph out of public descriptions.
- [ ] Recalculate manufacturing cost without labour; keep labour separate and avoid adding it twice.
- [ ] Recalculate selling price with effective markup/fixed-price rules and penny rounding.
- [ ] Confirm primary belongs to the listing and is not excluded or in situ.
- [ ] Review listing, in situ, advertising and associated-only purposes separately.
- [ ] Include every selected listing and in situ image; record any photography gaps without inventing images.
- [ ] Use complete photo ID lists from `/api/coverage` and full records from `/api/component-overview/{product_id}`. The `/api/specifications` photo `images` arrays are card previews capped at six per section; never treat them as complete galleries. Assert full ID totals match the stated section counts before generating a channel plan.
- [ ] Put primary first and preserve intentional gallery order; remove duplicate placements.
- [ ] Add accurate alt text and verify publishing rights for selected photographs.
- [ ] Confirm packed shipping weight, outer package dimensions, delivery region/rate and any quote-only exception.

## 4. Freeze and validate one release snapshot

- [ ] Capture effective app records, saved decisions, image uses, costs and source hashes consistently.
- [ ] Confirm the event cutoff/source did not change during capture; rebase if it did.
- [ ] Build an item-level before/after manifest, including all downstream channel IDs.
- [ ] Reconcile included product count from this release; do not hard-code the historical count of 176.
- [ ] Check no unrelated products or categories are in the mutation plan.
- [ ] Verify stable public image URLs; do not publish expiring Dropbox temporary URLs or local localhost paths.
- [ ] Verify original bytes before any temporary upload/download; retain hashes and minimal staging only.

## 5. Publish Squarespace and the homepage

- [ ] Update by mapped product/variant ID and SKU. Preserve unrelated inventory fields and URL slugs.
- [ ] Update retail title, public copy, price, availability and shipping attributes from the frozen snapshot.
- [ ] Upload/replace only required media; put all chosen listing/in situ images in the main carousel.
- [ ] Remove obsolete public placements and the old separate In a setting block if present.
- [ ] Refresh the sculpture homepage manifest, primary photographs and family/search filters.
- [ ] Verify public visibility, canonical product URL, image order/count and structured product data.
- [ ] Check every changed product, then representative unchanged products for regressions.
- [ ] Reconcile any ambiguous save by reading it back before retrying.
- [ ] For eBay photo uploads, wait until every expected photo has an enabled edit/view control and Select is enabled. The upload counter can include unfinished files. Save once, reopen the exact draft ID/SKU, and verify the complete gallery persisted before proceeding.
- [ ] Pilot appending to an imported eBay gallery before using that method broadly. A mixed imported/local gallery saved only its newly uploaded photo on 7 November. If readback loses retained photos, stop appending and replace the complete gallery from verified current originals, primary first; reopen and reconcile the full set before publication.

## 6. Refresh the Dropbox catalogue document

- [ ] Regenerate the workbook from the same release snapshot, including all component records, excluded states, specifications, listing copy, costs, labour, markup, prices and image links/purposes.
- [ ] Ensure the retail-name column and native channel mappings are present.
- [ ] Verify formulas/cached values, unique IDs, row counts, hyperlinks and workbook opening.
- [ ] Include Channel Details and US Delivery Estimates. Clearly distinguish dated sample-destination planning budgets from bookable or checkout shipping quotes; keep heavy/oversize freight exceptions visible.
- [ ] Upload to `/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx`.
- [ ] Read back metadata/revision and download verification bytes; verify the actual workbook matches the release.
- [ ] Record the new Dropbox stable ID/revision/hash and refresh time.

## 7. Google Merchant Center

- [ ] Verify account **5664655454**, website claim, target country and currency.
- [ ] Wait for Squarespace's native feed to process the new changes; inspect the source timestamp and error report.
- [ ] Refresh supplementary titles/descriptions, primary/additional images, shipping weight and labels where used.
- [ ] Match supplements by exact offer/variant ID; do not create parallel offers with different identifiers.
- [ ] Apply the channel's current image limits and verify which images are retained.
- [ ] Check price, availability, shipping and return policy agree with the product page and checkout.
- [ ] Review account issues, product issues, warnings and approval status separately from feed acceptance.
- [ ] Record approved, limited, pending and disapproved counts for the changed IDs.
- [ ] Request review only after fixing an actual issue; pending review is a platform state, not an import failure.
- [ ] Verify auto-tagging and the GA4 link remain enabled. Allow reporting delay and then inspect attributed traffic.
- [ ] Recheck optional programmes only when applicable: promotions, reviews, loyalty and Wallet require real business details/terms.

## 8. Meta catalogue, Facebook Shop and Instagram Shopping

- [ ] Verify business **2380586078685156**, catalogue **1638438493182970**, commerce account **326960679342026** and intended sales channels.
- [ ] Verify the native Squarespace feed refresh and item-level processing results.
- [ ] Refresh supplementary image/label fields without overriding correct native price/availability.
- [ ] Verify exact content IDs, image order, current price, availability and destination URL.
- [ ] Reconcile family/finish/price collections and remove excluded products from them.
- [ ] Publish saved shop-layout changes; retain the publication receipt for both platforms.
- [ ] Check the Facebook and Instagram previews and public purchase route where available.
- [ ] Tag exact catalogue products in relevant posts; confirm the pictured component and finish, not just a similar family name.
- [ ] Check existing tagged posts for stale IDs after merges/replacements.
- [ ] Add/update Stories and supported Reels product tags and purchase links; retain permalink or mobile evidence.
- [ ] Maintain a Wall Sculptures highlight and a tracked shop bio link; complete mobile-only controls in the Instagram app.

## 9. Facebook, Threads and Marketplace content

- [ ] Verify the real Facebook Page attached to Commerce Manager before changing its button or publishing Page content.
- [ ] Point its shopping button to the current wall sculpture collection using a tracked URL.
- [ ] Publish/refresh and feature the shop-introduction post; use exact product links for product-specific content.
- [ ] Keep Threads' tracked shop profile link current and use tracked direct links in relevant posts.
- [ ] Check link previews use the current primary photograph and name.
- [ ] Reconcile Marketplace listings by SKU and saved listing ID before creating another listing.
- [ ] Update existing Marketplace price, description, photographs and availability; Marketplace does not inherit every catalogue change.
- [ ] Verify any whole-pound Marketplace display against the exact website price and explain any required rounding in the description.
- [ ] Keep the sale scope clear: individual component versus pair/set; made-to-order status and delivery terms must remain accurate.
- [ ] Record publish receipt, actual listing URL and review status. Do not retry an ambiguous Publish without checking Your listings.
- [ ] Confirm no unintended group cross-posting, boosts or paid ads were selected.
- [ ] Verify the ordering/payment route. A Meta advertising payment method is not a Marketplace payout destination.

## 10. Test, observe and close

- [ ] Update existing eBay, TikTok Shop, Chairish, Wescover and Saatchi Art records by account plus platform ID/SKU. Reconcile drafts, pending reviews and live records before creating anything; preserve distinct pair/set offers.
- [ ] In Saatchi's sale form, wait for a positive native shipping quote and a complete price preview before Save. A visible Save link and populated inputs do not prove the quote or save is ready. Reopen the same artwork's overview to verify the actual price, edition, quantity and packed weight; reconcile a failed save before retrying.
- [ ] Validate Saatchi publication receipts through `native_artwork_bindings`: native ID, exact SKU, Published visibility, public URL ending in the same ID, native evidence and original verification time are all required. Repair incomplete tracking fields only from retained native evidence; never recreate an existing artwork to repair a local receipt.
- [ ] Verify material and surface-effect wording on every changed channel, including any structured material field and supplementary feed that can override native copy. Do not treat an accepted upload as a verified live change.
- [ ] Pilot any bulk editor on one existing record and verify its publication state. In TikTok, `draft_tab=true` did not prevent `Live(1)` from publishing drafts in the 1 November template; do not reuse that upload for draft-preserving edits.
- [ ] Preserve eBay draft upload receipts and reconcile the account's current drafts before any further import. The 1 November requests were `12356778479` for 157 sapr_2972 offers and `13338436334` for 176 in6192 drafts; accepted imports are not proof that offers are live.
- [ ] Resolve renamed existing items before new imports, including Wescover's Feather Fall / Icarus and Strata in Verdigris. Retain pair/set offers as separate sale units.

- [ ] Complete the relevant rows in [test-matrix.md](test-matrix.md).
- [ ] Reconcile item counts and IDs across app, workbook, website, Google, Meta and Marketplace; retain exceptions explicitly.
- [ ] Save screenshots and readback receipts; redact customer and financial details from shareable evidence.
- [ ] Recheck asynchronous feeds/reviews after their expected processing window.
- [ ] Update the release record with verified results, unresolved blockers, owner and next action.
- [ ] Remove temporary full-size downloads only after their publication/archive/original has been verified and no live workflow depends on them.
- [ ] Keep the active app state, source exports, mappings, current workbook and publication history.
- [ ] Mark the release complete only when all required tests pass or a named exception has been accepted.
