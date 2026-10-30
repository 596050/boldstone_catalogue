"""Prepare reviewable listing corrections without mutating accounts or masters."""
import datetime
import hashlib
import html
import json
import pathlib

P = pathlib.Path(__file__).resolve().parent
MASTER_HASH = "7760b44a4d52ff3b78c893d5b86ef174814b48c29f7e41814c8a01a42af5326d"
M = json.loads((P / "inputs/master-register.json").read_text())
assert hashlib.sha256((P / "inputs/master-register.json").read_bytes()).hexdigest() == MASTER_HASH
F = json.loads((P / "worker-01/FRESH_PUBLIC_INVENTORY.json").read_text())
N = {p["native_product_id"]: p for p in F["products"]}
OFFERS = {r["offer_ref"]: r for r in M["source_platform_offer_coverage"]}


def ref(path, pointer):
    path = P / path
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "json_pointer": pointer}


def product(offer):
    return N[OFFERS[offer]["squarespace_id"]]


RULES = {
    "BSI-1E0C826D896E": {
        "canonical_offer": "O079",
        "title": "Bone Water Spiral — White, 80 × 60 cm",
        "lead": "An individually carved and cast relief panel with a spiral design and a white marble stone effect.",
        "standard_size": {"width_cm": 80, "height_cm": 60, "projection_cm_range": [5, 8], "projection_scope": "Historical maker estimate; unmeasured"},
        "price": {"mode": "ACCEPTED_WORKING_ASK", "currency": "GBP", "value": "1100.00", "unit": "one panel"},
        "public_fields": {"Dimensions": "Standard panel: 80 cm wide × 60 cm high; approximately 5–8 cm deep.", "Approximate weight": "15–20 kg per panel.", "Finish": "White marble stone effect.", "Fixing options": "Keyhole fixing or French cleat; details confirmed with the order.", "Price": "£1,100 per panel.", "Availability": "Made to order; enquire for current lead time."},
        "source_version_disposition": "Use the owner-accepted80cm-wide by60cm-high working version as the correction target. Retain the native55×55 and historical110×55 versions as historical/version evidence; do not silently assert that those were the same manufactured dimensions.",
        "specific_limits": ["Panel sale unit only. Water-system components, sealing, pump, outlet, basin and plumbing are not established by this source-record match."],
    },
    "BSI-DB7FBD3E1323": {
        "canonical_offer": "O046",
        "title": "Golden Spiral — White and Gold, 45 × 40 × 5 cm",
        "lead": "An individually cast spiral relief with a gold leaf finish, using the owner-confirmed size shared with Timeless Spiral.",
        "standard_size": {"recorded_dimension_order_cm": [45, 40, 5], "new_height_width_assignment": False},
        "price": {"mode": "ACCEPTED_WORKING_ASK", "currency": "GBP", "value": "250.00", "unit": "one panel"},
        "public_fields": {"Dimensions": "45 × 40 × 5 cm.", "Approximate weight": "10 kg; estimated range 8–12 kg.", "Finish": "White and gold leaf finish.", "Fixing options": "Keyhole fixing or French cleat; details confirmed with the order.", "Price": "£250 per panel.", "Availability": "Made to order; enquire for current lead time."},
        "source_version_disposition": "Replace30×30×5cm as the current working standard in listing copy with45×40×5cm. Preserve the old source30×30 version and dimension-coded SKU as history; same family alone does not make all sizes one physical object.",
        "specific_limits": ["Do not turn gold leaf wording into a purity, composition or base-material certification."],
    },
    "BSI-6581D83760F1": {
        "canonical_offer": "O058",
        "title": "Leaf Form — White, 35 × 35 cm",
        "lead": "A single carved leaf relief in a white stone effect. One panel can be displayed in either of the retained LF1/LF2 orientations.",
        "standard_size": {"nominal_face_cm": [35, 35], "nominal_depth_cm": 6, "historical_side_depth_cm_range": [5, 7], "measured": False},
        "price": {"mode": "ACCEPTED_WORKING_ASK", "currency": "GBP", "value": "350.00", "unit": "one panel in one selected orientation"},
        "public_fields": {"Dimensions": "Nominally 35 × 35 × 6 cm per panel.", "Approximate weight": "6–8 kg per panel.", "Finish": "White marble stone effect.", "Fixing options": "Keyhole fixing or French cleat; details confirmed with the order.", "Price": "£350 for one panel in a selected orientation.", "Availability": "Made to order; enquire for current lead time."},
        "source_version_disposition": "Correct the individual standard to nominal35×35×6cm and retain the40×20 native source as a version conflict. O028 remains a separate two-panel offer; no division of its total price, dimensions or weight.",
        "specific_limits": ["LF1/LF2 are orientation choices on this accepted individual record, not two new catalogue products or mould claims."],
    },
    "BSI-70C7029C1DB1": {
        "canonical_offer": "O059",
        "title": "Moon Water Catcher — White (MWC1)",
        "lead": "A lunar relief panel in a white stone effect, with rippled-water texture held within a raised rim.",
        "standard_size": {"height_cm_approx": 51, "width_cm_approx": 48, "side_depth_cm_range": [5, 7], "scope": "Historical maker-stated working version; panel unmeasured"},
        "price": {"mode": "PROPOSE_PRICE_ON_ENQUIRY", "currency": "GBP", "value": None, "retained_native_ask": "800.00", "retained_local_draft": "599.69", "zero_price_proposed": False},
        "public_fields": {"Dimensions": "Approximately 51 cm high × 48 cm wide; side depth approximately 5–7 cm.", "Approximate weight": "10–12 kg.", "Finish": "White stone effect.", "Fixing options": "Keyhole fixing or French cleat; details confirmed with the order.", "Price": "Price on enquiry.", "Availability": "Made to order; enquire for current lead time."},
        "source_version_disposition": "Use O059 Moonwater as the proposed primary native record for the current MWC1 working version. Preserve O015 as a title/photo identity conflict and separate nominal50cm source version; do not relabel it as MCP4 from title or intended BOM alone.",
        "specific_limits": ["O015's photograph belongs to the MWC1 visual scope; that does not establish the originally intended Concave Moon configuration.", "An enquiry-only price requires a matching purchase/enquiry flow; do not encode it as a zero-priced checkout product or silently replace the accepted price-source assertions."],
    },
}

rows = []
for index, option in enumerate(M["options"]):
    if option["product_id"] not in RULES:
        continue
    rule = RULES[option["product_id"]]
    native = product(rule["canonical_offer"])
    assert len(native["variants"]) == 1
    variant = native["variants"][0]
    fields = {name: value["display"] for name, value in option["master_fields"].items()}
    # Preserve source-qualified working fields separately. Public-copy proposals
    # use buyer-facing wording and retain approximation qualifiers.
    description = "<p>" + html.escape(rule["lead"]) + "</p><dl>" + "".join(
        "<dt>" + html.escape(name) + "</dt><dd>" + html.escape(value) + "</dd>"
        for name, value in rule["public_fields"].items()
    ) + "</dl>"
    selected = {k: variant[k] for k in ["native_product_id", "native_variant_id", "sku", "option_attributes", "price", "stock_setting", "raw_dimensions_and_weight", "source_locator"]}
    rows.append({
        "case_id": "EXISTING-LISTING-20261021:" + option["product_id"],
        "product_id": option["product_id"], "canonical_key": option["canonical_key"], "name": option["name"],
        "canonical_offer_proposal": rule["canonical_offer"],
        "native_record_identity": {"product_id": native["native_product_id"], "variant_id": variant["native_variant_id"], "sku": variant["sku"], "url": native["url"]},
        "native_before": {"title": native["title"], "description_html": native["description_html"], "description_text": native["description_text"], "variant": selected, "timestamps": native["timestamps"]},
        "accepted_working_specifications": fields,
        "accepted_specifications_changed": False,
        "proposed_listing_title": rule["title"],
        "proposed_review_description_html": description,
        "proposed_public_specification_fields": rule["public_fields"],
        "proposed_standard_size": rule["standard_size"],
        "commercial_policy_proposal": rule["price"],
        "source_version_disposition": rule["source_version_disposition"],
        "native_sku_policy": {"action": "RETAIN_CURRENT_NATIVE_SKU_AS_LEGACY_IDENTIFIER_IN_THIS_CORRECTION", "value": variant["sku"], "sku_digits_are_not_dimensions": True,
                              "canonical_working_option_id": option["product_id"], "prior_sku_aliases_retained": True},
        "shipping_measurements_policy": {"action": "NO_CHANGE", "reason": "Native/API shippingMeasurements are packed-shipment measurements. Accepted artwork dimensions and unweighed estimates are not packed dimensions or shipping weights; store units and actual packing data are not confirmed."},
        "native_product_partial_update_draft": {"method": "POST", "path": "/v2/commerce/products/" + native["native_product_id"],
                                                "body": {"name": {"present": True, "value": rule["title"]}, "description": {"present": True, "value": description}},
                                                "executable_now": False},
        "execution_preconditions": [
            "Confirmed active target store and authenticated access to the same site.",
            "Fresh authenticated product/variant identity and before-value readback; stop on concurrent changes.",
            "Preserve numeric IDs, native image order, stock configuration and all historical source assertions.",
            "Apply the grouped product-copy and commercial-mode decision consistently; Moon Water Catcher price/enquiry proposal is not a native numeric-price edit.",
            "Read back the exact changed fields from the native account, then check public output; record a separate execution receipt.",
        ],
        "specific_limits": rule["specific_limits"],
        "primary_image_file_id": option.get("file_id"), "primary_folder_id": option.get("folder_id"),
        "master_evidence": ref("inputs/master-register.json", "/options/" + str(index)),
        "native_evidence": ref("worker-01/FRESH_PUBLIC_INVENTORY.json", "/products/" + str(F["products"].index(native))),
        "status": "PREPARED_WORKING_VERSION_CORRECTION; NOT_APPLIED_TO_PLATFORM",
        "exact_current_native_configuration_verified": False,
        "physical_specifications_certified": False,
    })

assert len(rows) == 4
result = {"schema": "boldstone.four-existing-listing-correction-proposals.v1", "prepared_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "owner_instruction": json.loads((P / "OWNER_INSTRUCTION.json").read_text()), "input_master_sha256": MASTER_HASH,
          "scope": "Four owner-requested existing listing corrections, preserving owner working values and native histories. These are concrete review/execution drafts, not account-write receipts.",
          "records": rows,
          "official_platform_sources": [
              {"url": "https://developers.squarespace.com/commerce-apis/products", "used_for": "Product and variant partial update structure; shipping measurements mean when shipped; native SKU uniqueness."},
              {"url": "https://support.squarespace.com/hc/en-us/articles/115000378108-Importing-products-from-a-csv", "used_for": "Existing product and variant IDs must be retained for same-site updates; CSV numbers follow store measurement standard; cannot use CSV to reassign existing images."},
          ],
          "scope_limits": ["No old source version is deleted or overwritten.", "No accepted field, catalogue count, physical stock or installed fixing is changed by this proposal.", "No native shipping measurements, inventory quantities, product/variant IDs or image bindings are mutated.", "SKU strings remain identifiers; correcting a standard-size description does not require inventing a replacement native SKU."],
          "platform_writes": 0, "shared_master_writes": 0}
(P / "FOUR_LISTING_CORRECTIONS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"records": len(rows), "platform_writes": 0, "accepted_fields_changed": 0, "native_record_ids_bound": 4}))
