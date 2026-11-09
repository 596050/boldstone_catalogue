BOLDSTONE - prepared wall sculpture upload

The current component population and owner decisions are retained. This package
prepares local records; it has not created, overwritten or published store products.

all-components-upload-register.csv
  One row per current component, including specifications, markup price, SKU,
  exact existing identifiers or planned creation action, delivery and review state.
upload-plan.json
  Complete structured mappings, source hashes, source rows and retirement record.
shopify-new-products-draft.csv
  Only included components whose proposed handles are new in the local Shopify
  source. Product status is draft and Published is FALSE. Pending and excluded
  components are omitted. Check destination handles before import because the
  local export is historical. This file does not create public image links.
shopify-existing-variant-price-updates.csv
  Exact existing local handle, option tuple and SKU, with new price and cost.
  Original parent titles and option values are preserved. Recheck the destination
  before applying. Do not use an option-renaming import to append variants.
  Seven additional variants have explicit append actions in upload-plan.json;
  append them through the platform API after resolving the destination options.
  Frozen Fish reuses the existing blank-SKU family draft as parent for its three
  finish variants. Reconcile that placeholder through the API rather than create
  another Frozen Fish parent. The placeholder is not an exact native variant match.
selected-image-upload-manifest.csv
  Per-component order, primary selection, purposes, types, alt text, original pixel
  dimensions, stable Dropbox file ID and expected content hash. Fetch originals
  by ID and verify their bytes, then upload to destination media storage. Dropbox
  home/preview links require access; they are not public CSV-import image URLs.
  A single original may serve several components. No shared Dropbox links were
  created and no source photographs were changed or deleted by this preparation.
retired-components-not-for-upload.csv
  Eight historic components omitted after the current app's merges/retirements.

Delivery: quote separately for each order. Production: made to order, 1-2 weeks.
Dispatch and transit arrangements are agreed with the delivery quote. No carrier,
delivery charge, packed weight or package dimensions are invented. Product weights
and dimensions remain product specifications, not certified shipping measurements.

Prices use the app's manufacturing-cost scenario, including separate labour,
plus 100% markup. Delivery is not included. Physical material specifications and
the production material used by the costing model remain separately recorded.

Four selected photographs visibly have brown/pink/sand tones while associated
with White Cup Ring and Spiral components. Their selections were retained and
flagged for visual review. Choose the missing primary/listing images and resolve
pending component decisions before publication; these are not silently approved.

Shopify CSV behavior checked against:
https://help.shopify.com/en/manual/products/import-export/using-csv
https://help.shopify.com/en/manual/products/import-export/import-products

Workbook: catalogue_wall_sculptures.xlsx has the current app records, image links,
source qualifications, editable cost formulas, markup prices and an Upload Plan.
Workbook edits do not write back into the app. Use the app to change source decisions.
