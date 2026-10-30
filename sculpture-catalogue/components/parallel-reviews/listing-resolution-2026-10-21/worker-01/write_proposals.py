import json
from capture_public_inventory import OUT, BASE, OLD, digest, now, save

def main():
    master_path = BASE / 'inputs/master-register.json'
    master = json.loads(master_path.read_text())
    source_path = OUT / 'CASE_SOURCE_RECORDS.json'
    cases = json.loads(source_path.read_text())['case_source_records']
    case_by = {case['offer_ref']: (index, case) for index, case in enumerate(cases)}
    comparisons = json.loads((OUT / 'CASE_COMPARISONS.json').read_text())['comparisons']
    image_data = json.loads((OUT / 'CASE_IMAGE_RECEIPTS.json').read_text())
    old_media = json.loads((OUT / 'HISTORICAL_MEDIA_RECEIPTS.json').read_text())['media']
    option_by = {option['product_id']: (i, option) for i, option in enumerate(master['options'])}

    def local_ref(name, pointer):
        path = OUT / name
        return {'path': str(path), 'json_pointer': pointer, 'sha256': digest(path)}

    def source_refs(offers, comparison_index, product_ids):
        refs = [local_ref('CASE_COMPARISONS.json', '/comparisons/' + str(comparison_index))]
        for offer in offers:
            index, case = case_by[offer]
            refs.append(local_ref('CASE_SOURCE_RECORDS.json', '/case_source_records/' + str(index)))
            for image_index, image in enumerate(image_data['public_media']):
                if image['offer_ref'] == offer:
                    refs.append(local_ref('CASE_IMAGE_RECEIPTS.json', '/public_media/' + str(image_index)))
            for image_index, image in enumerate(image_data['cached_source_media']):
                if image['offer_ref'] == offer:
                    refs.append(local_ref('CASE_IMAGE_RECEIPTS.json', '/cached_source_media/' + str(image_index)))
            for image_index, image in enumerate(old_media):
                if image['offer_ref'] == offer:
                    refs.append(local_ref('HISTORICAL_MEDIA_RECEIPTS.json', '/media/' + str(image_index)))
        for product_id in product_ids:
            index, option = option_by[product_id]
            refs.append({'path': str(master_path), 'json_pointer': '/options/' + str(index), 'sha256': digest(master_path)})
        return refs

    def photo_pair(left, right, left_index, right_index, state, note):
        left_image = next(image for image in image_data['public_media'] if image['offer_ref'] == left and image['gallery_index'] == left_index)
        if right in ['O039', 'O064']:
            right_image = next(image for image in old_media if image['offer_ref'] == right and image['historical_gallery_index'] == right_index)
            right_id = None
        else:
            right_image = next(image for image in image_data['public_media'] if image['offer_ref'] == right and image['gallery_index'] == right_index)
            right_id = right_image['native_media_id']
        return {'left_offer_ref':left,'left_gallery_index':left_index,'left_native_media_id':left_image['native_media_id'], 'right_offer_ref':right,'right_gallery_index':right_index,'right_native_media_id':right_id,
            'left_image_path':left_image['receipt']['body_path'],'left_image_sha256':left_image['receipt']['sha256'],
            'right_image_path':right_image['receipt']['body_path'],'right_image_sha256':right_image['receipt']['sha256'],
            'encoded_bytes_identical':left_image['receipt']['sha256']==right_image['receipt']['sha256'],
            'decoded_rgb_pixels_identical':left_image.get('decoded_rgb_sha256')==right_image.get('decoded_rgb_sha256'),
            'reviewed_state':state,'visual_basis':note,'review_method':'Cached/public image contact sheet inspected with tools.view_image; no external private upload or generative editing.',
            'limits':'Photographic correspondence and depicted design only; physical cast, measured size, finish recipe, installed fixing and stock are not authenticated.'}

    proposals = []
    proposals.append({
        'case_id':'RUST-SKU-COLLISION','offer_refs':['O051','O067'],'existing_canonical_product_ids':['BSI-947F365275C5'],
        'classification':'DUPLICATE_CURRENT_MARKETING_HIGH_CONFIDENCE_COMMERCIAL_FIELDS_CONFLICT',
        'conclusion':'Both current native listings reuse the same four photographic views of the rust-wave panel, the same SKU and the same stated dimensions. No option attribute or description establishes a separate intended finish, size or build. Treat them as duplicate marketing records for the existing Rust design/finish in the catalogue, with conflicting commercial settings; do not certify physical-cast equality.',
        'identity_count_recommendation':{'existing_product_id':'BSI-947F365275C5','canonical_key':'BC-DR-WAVE1|DR-WAVES-RUST','individual_count_increment':0,'design_finish_match':'SUPPORTED_BY_VISUAL_REVIEW_AND_EXISTING_SOURCE_BINDINGS','exact_native_ids_known':True,'exact_cast_or_manufactured_version_certified':False},
        'canonical_alias_proposal':{'preferred_source_offer_ref':'O067','preferred_native_product_id':'6aa01aad7f3077314dd71e8c','preferred_native_variant_id':'ca0fa776-e58d-41a3-b11b-ce9a64f458e4','preferred_sku_retained':'EBAY-188654649217','alias_source_offer_ref':'O051','alias_native_product_id':'6a5a621422d8fb7a65ba5a77','alias_native_variant_id':'ea0b690f-a56b-4c92-9f71-89d093e47a56','relationship':'DUPLICATE_MARKETING_SOURCE_FOR_EXISTING_CATALOGUE_OPTION','preference_basis':'Coordinator proposes the later-created/later-updated O067 as workflow canonical, retaining its native identifiers and current settings. The evidence does not contradict that preference. Newer timestamps do not approve its price or prove physical stock. O051 has the higher-resolution reverse image and that source image must remain retained.','reversible_draft_only':{'legacy_source_offer_ref':'O051','proposed_unique_legacy_sku':'LEGACY-6a5a621422d8fb7a65ba5a77','original_sku_alias_retained':'EBAY-188654649217','proposed_discovery_state':'Hidden from discovery; native administrative implementation not verified','url_access_or_checkout_disabled_claimed':False,'price_policy':'Price on enquiry working proposal avoids choosing between35.33 and65.33; neither stored native price is changed by this review.','execution_status':'NOT_EXECUTED'},'platform_action':'NONE; preserve both native records, photographic sources and all conflicting source values for coordinator review.'},
        'current_native_facts':{'sku_both':'EBAY-188654649217','description_dimensions_cm_both':[35,21,6],'option_attributes_both':{},'O051':{'price_GBP':'35.33','unlimited':True,'qtyInStock_raw':0,'weight_raw_unitless':6.6,'addedOn_UTC':'2026-07-17T17:10:44.243000+00:00','updatedOn_UTC':'2026-09-01T06:47:23.514000+00:00'},'O067':{'price_GBP':'65.33','unlimited':False,'qtyInStock_raw':1,'weight_raw_unitless':11.02,'addedOn_UTC':'2026-09-08T14:24:45.698000+00:00','updatedOn_UTC':'2026-10-09T23:38:43.157000+00:00'}},
        'sale_unit_assessment':'Each native description offers a singular sculpture; each has one variant with no option attributes. Four photographs are four views, not four marketed components. Raw stock settings do not establish physical stock.',
        'photographic_evidence':[photo_pair('O051','O067',i,i,'SAME_PHOTOGRAPHIC_VIEW_DIFFERENT_ENCODING', ['Same front view, background masonry, wave silhouette and rust placement.','Same left oblique view and background masonry.','Same right oblique view and background masonry.','Same reverse view and central hanging plate; O067 is only112×200 while O051 is900×1600.'][i]) for i in range(4)],
        'working_price_recommendation':'Retain both current source prices (£35.33 on O051 and £65.33 on O067) as conflicting commercial evidence. Use Price on enquiry as the standing working proposal; no arbitrary final retail price is chosen. Preserving O067 native settings in the draft does not approve£65.33 or physically validate qty1.',
        'genuinely_missing_evidence':['Which of the two current prices is intended for the canonical offer.','Whether finite stock1 versus Unlimited is intentional; neither proves a physical cast count.','Measured panel weight and exact cast/version linkage; native raw weights lack encoded units.'],
        'evidence_refs':source_refs(['O051','O067'],0,['BSI-947F365275C5'])})

    proposals.append({
        'case_id':'VERDIGRIS-VERSIONS','offer_refs':['O004','O038'],'existing_canonical_product_ids':['BSI-59530C6155C2'],
        'classification':'DIFFERENT_PHOTOGRAPHED_SURFACE_VERSIONS_SAME_DESIGN_FAMILY',
        'conclusion':'The relief design corresponds, but the photographed finish applications differ: O004 has muted blue-green surfaces with fine rust/copper-coloured ridge edges; O038 has bright turquoise surfaces and broad scattered rust/copper-coloured patches. Descriptions, prices and one face dimension also differ. A duplicate exact configuration is not established.',
        'identity_count_recommendation':{'existing_product_id':'BSI-59530C6155C2','canonical_key':'BC-DR-WAVE1|DR-WAVES-VERDIGRIS','individual_count_increment':0,'design_family_match':'SUPPORTED_BY_VISUAL_REVIEW','same_exact_finish_application_or_physical_cast':'NOT_ESTABLISHED','new_named_sale_variant_created':False,'scope_note':'Retain descriptive version qualifiers as source references; no new owner-approved variant name or measured size is invented.'},
        'canonical_alias_proposal':{'preferred_source_offer_ref':'O004','preferred_native_product_id':'6a410e3f16d56f3a046ef1d7','preferred_native_variant_id':'462d3d37-f550-429b-a84c-cca579fb15b1','preferred_source_binding_basis':'Existing canonical primary file id:cnqzTNngPVsAAAAAAAyfVg corresponds to O004; its current stated35×21×6 size and£45 price match the current working row.','other_source_offer_ref':'O038','other_native_product_id':'6a555a757b54f252fef707d1','other_native_variant_id':'1d89ba22-d937-4064-a17c-0240bb153f90','relationship':'SAME_DESIGN_FINISH_FAMILY_DIFFERENT_DEPICTED_SURFACE_VERSION','recommended_mapping_correction':'Preserve O038 as a related bright turquoise/copper/rust source version. Do not describe it as an exact native variant/configuration match to the selected muted-green O004 primary.','platform_action':'NONE; do not delete, merge prices or merge availability.'},
        'current_native_facts':{'O004':{'sku':'SQ0836319','description_dimensions_cm':[35,21,6],'price_GBP':'45.00','stock_unlimited':True},'O038':{'sku':'VDR-1-35.20','description_dimensions_cm':[35,20,6],'price_GBP':'250.00','stock_unlimited':True,'description_sold_claim':True}},
        'photographic_evidence':[photo_pair('O004','O038',0,0,'DIFFERENT_DEPICTED_SURFACE_APPLICATION_SAME_RELIEF_DESIGN','Different broad patina placement, saturation and texture are visible on matching wave geometry. Colour alone is not a chemistry certificate; the differing patch placement is retained as version evidence.')],
        'sale_unit_assessment':'Both descriptions concern one sculpture; O038 explicitly says individually carved and cast. Its SOLD sentence conflicts with the currently Unlimited purchase setting. A repeat commission is an enquiry possibility, not stock evidence.',
        'working_price_recommendation':'Keep£45 attached to selected O004. Keep£250 attached to O038 as a current displayed listing price whose description says SOLD; do not substitute it for O004 or certify availability.',
        'genuinely_missing_evidence':['Whether the maker intends the bright turquoise/rust application as a separately named sale variant or a finish reference within the same named Verdigris product.','Whether35×20×6 and35×21×6 are actual different sizes or rounded/conflicting claims.','Current fulfilment state for O038, since its SOLD description conflicts with its Unlimited setting.'],
        'evidence_refs':source_refs(['O004','O038'],1,['BSI-59530C6155C2'])})

    proposals.append({
        'case_id':'MOON-WATER-OVERLAP','offer_refs':['O015','O059'],'existing_canonical_product_ids':['BSI-70C7029C1DB1','BSI-98376D9FF006'],
        'classification':'SAME_DEPICTED_DESIGN_CONFLICTING_NOMINAL_IDENTITY_AND_VERSION',
        'conclusion':'Both galleries depict the white square-backed basin/catcher design already bound in the master to Moon Water Catcher, rather than the separate25×25 MCP4 White product. The two listings have different photographs/crops and incompatible description/configuration claims. An exact offered-version duplicate is not established.',
        'identity_count_recommendation':{'canonical_depicted_product_id':'BSI-70C7029C1DB1','canonical_key':'BC-MOON-WATER|MOONWATER-WHITE','individual_count_increment':0,'O015_nominal_MCP4_association':'CONFLICTING_TITLE_OR_INTENDED_BOM_ONLY_NOT_THE_BOUND_HERO_DESIGN','O015_O059_depicted_design_association':'SUPPORTED_BY_VISUAL_REVIEW_AND_FROZEN_MASTER_BOUND_HERO_EVIDENCE','O015_O059_exact_current_configuration_match':'NOT_CERTIFIED'},
        'canonical_alias_proposal':{'preferred_source_offer_ref':'O059','preferred_native_product_id':'6a6102307b54f252fe00210b','preferred_native_variant_id':'9d8c0d63-87c6-400e-8a85-51e4208271b3','related_conflicting_source_offer_ref':'O015','related_native_product_id':'6a5559d21b9743318cc70b4b','related_native_variant_id':'40624991-b17a-49e7-bd1d-22ffbc0b118f','proposed_name_for_review':'Moon Water Catcher — White (MWC1)','preference_basis':'O059 has a Moonwater title/SKU and the gallery depicts the bound catcher design. Its size/material/price claims remain source claims with conflicts.','recommended_mapping_correction':'Associate both depicted-design edges with BSI-70C7029C1DB1, retaining configuration conflicts. Keep O015 in identity-conflict quarantine without guessing its originally intended MCP4 product. Do not map O015 as an exact sale variant of BSI-98376D9FF006 MCP4 White based on its Concave Moon title. Do not collapse the two live native product IDs as an exact configuration alias.','quarantine_limits':'Local review disposition only; no native visibility, URL accessibility or checkout state is changed or certified.','platform_action':'NONE; retain legacy title/URL in evidence; proposed title correction is local only.'},
        'current_native_facts':{'O015':{'title':'Concave Moon wall sculpture','sku':'CM-1-50.50','price_GBP':'520.00','description_size_claim':'50×50×6 cm','description_material_claim':'white marble stone finish','stock_unlimited':True},'O059':{'title':'Moonwater wall sculpture','sku':'MWTR-1-50','price_GBP':'800.00','description_size_claim':'50cm diameter×8cm','description_material_claim':'gypsum composite, stone finish','stock_unlimited':True},'current_working_canonical_dimensions':'Approximately51cm high×48cm wide,5–7cm side depth — maker-stated historical approximation; pictured panel unmeasured','current_working_material_conflict':'Maker records say Jesmonite AC730; O059 says gypsum composite. Neither certifies the actual cast.'},
        'photographic_evidence':[photo_pair('O015','O059',0,0,'SAME_DEPICTED_BASIN_CATCHER_DESIGN_NOT_BYTE_IDENTICAL_PHOTOGRAPHS','Both show the white square panel with a deep circular basin, projecting lower rim and the same broad relief layout on brick. Their different framing/crops are not a calibrated measurement or physical-cast test.')],
        'sale_unit_assessment':'Each native description describes one sculpture, with one native variant and no selectable size/build options. A water-related design/name does not prove supplied plumbing, a pump, drainage or water-feature hardware.',
        'working_price_recommendation':'Retain£800 as current O059 listing evidence and£520 as current O015 conflicting evidence. The canonical working row also retains local draft£599.69. No final retail price or exact matched manufactured size is established.',
        'genuinely_missing_evidence':['Which size/build/material the two native variants are intended to fulfil, given50×50×6 versus50diameter×8 versus maker51×48/5–7.','Whether the two live offers intentionally cover distinct versions or one duplicated marketing offer.','Intended canonical retail price and fulfilment/lead time; purchase settings do not verify stock.'],
        'evidence_refs':source_refs(['O015','O059'],2,['BSI-70C7029C1DB1','BSI-98376D9FF006'])})

    proposals.append({
        'case_id':'GOLD-HISTORICAL-OVERLAP','offer_refs':['O002','O039'],'existing_canonical_product_ids':['BSI-0922347CC6AE'],
        'classification':'HISTORICAL_SAME_DESIGN_REFERENCE_EXACT_VERSION_UNRESOLVED',
        'conclusion':'O002 is currently public. O039 is not returned by the collection and its exact canonical product URL returns404; its historically evidenced CDN photograph remains accessible. The two references show the Gold Dune Ripple Spiral design with two spiral curls, but different photography and conflicting dimensions do not establish an exact-version duplicate.',
        'identity_count_recommendation':{'existing_product_id':'BSI-0922347CC6AE','canonical_key':'BC-DR-SPIRAL|DR-SPIRAL-GOLD','individual_count_increment':0,'design_finish_reference':'SUPPORTED_BY_VISUAL_REVIEW','same_exact_size_build_or_cast':'NOT_ESTABLISHED'},
        'canonical_alias_proposal':{'preferred_source_offer_ref':'O002','preferred_native_product_id':'6a40cfc5870e0e6bc1e0bb1d','preferred_native_variant_id':'5ee52805-9618-44bf-87f6-3e8eb08137ae','historical_source_offer_ref':'O039','historical_native_product_id':'6a555a777b54f252fef707d4','historical_native_variant_id':'2d5849b8-b8a6-4a4e-a02a-f165d60f3304','relationship':'HISTORICAL_DESIGN_FINISH_REFERENCE_WITH_SIZE_CONFLICT','recommended_mapping_correction':'Use O002 as the current native source for the selected canonical primary. Preserve O039 as a related historical Gold Spiral version/reference rather than an exact native size/build alias. Preserve its Shopify handle as a cross-platform historical association, not a duplicate within Squarespace.','platform_action':'NONE;404 does not certify account deletion or hidden/draft state.'},
        'current_and_historical_source_facts':{'O002':{'source_state':'CURRENT_PUBLIC','sku':'SQ6244576','price_GBP':'299.00','description_dimensions_cm':[35,21,6]},'O039':{'source_state':'CACHED_NATIVE_ONLY_PRODUCT_PAGE404','sku':'GDRS-1-35.20','source_amount':'200.00','currency':'UNENCODED_IN_CACHED_NATIVE_EXPORT','description_dimensions_cm':[35,20,5],'cached_native_visibility_conflict':'Saved original CSV VisibleYes; cached wall extract VisibleNo. Both are dated source assertions.','historical_shopify_handle':'golden-spiral-dune-ripple'}},
        'photographic_evidence':[photo_pair('O002','O039',0,0,'SAME_GOLD_SPIRAL_DESIGN_DIFFERENT_PHOTOGRAPH_EXACT_CAST_UNRESOLVED','Both show the rippling rectangular relief with two opposing spiral curls and applied gold appearance. O039 is photographed against black/gold patterned wallpaper; O002 is against pale stone. No calibrated scale or same-cast receipt is present.')],
        'sale_unit_assessment':'Each source description describes a singular sculpture. No set price is allocated to an individual and no size is inferred from raw unitless native dimension fields.',
        'working_price_recommendation':'Keep£299 as the current O002 variant price. Retain O039 source amount200.00 with its original unencoded currency. Any separately supported ShopifyGBP price is for the parent Shopify lane to verify; do not inherit currency across platforms or versions.',
        'genuinely_missing_evidence':['Whether35×20×5 and35×21×6 represent separate manufactured sizes or inconsistent approximations.','O039 authenticated admin/visibility state and intended lifecycle; no current account access was used.','Exact physical cast/version relationship and current fulfilment quote for the historical version.'],
        'evidence_refs':source_refs(['O002','O039'],3,['BSI-0922347CC6AE'])})

    proposals.append({
        'case_id':'SILVER-HISTORICAL-OVERLAP','offer_refs':['O003','O064'],'existing_canonical_product_ids':['BSI-1AF0A83FAA37'],
        'classification':'HISTORICAL_DUPLICATE_MARKETING_SOURCE_ALIAS',
        'conclusion':'O064 reuses the seven photographic views currently present on O003, with the same photographed silver/bronze patina and masonry backgrounds, plus a rear view. Both descriptions state25×25×6cm. This supports a historical duplicate-marketing source alias for the existing MCP4 Silver and Bronze option. Only O003 is currently public in the checked inventory; O064 product URL returns404.',
        'identity_count_recommendation':{'existing_product_id':'BSI-1AF0A83FAA37','canonical_key':'BC-MCP-4|MCP4-SILVER-BRONZE-25','individual_count_increment':0,'depicted_configuration_match':'SUPPORTED_HISTORICAL_PHOTOGRAPHIC_RECORD','physical_cast_or_current_hardware_certified':False},
        'canonical_alias_proposal':{'preferred_source_offer_ref':'O003','preferred_native_product_id':'6a410d3d21dbe14148c0a367','preferred_native_variant_id':'733a1644-4674-482e-ac5b-5e42e5f7fbe1','historical_alias_source_offer_ref':'O064','historical_alias_native_product_id':'6aa018ab5e7636290fa6e74c','historical_alias_native_variant_id':'118590fc-f3fa-4cf0-897c-4229cd349073','relationship':'HISTORICAL_DUPLICATE_MARKETING_SOURCE_FOR_EXISTING_CATALOGUE_OPTION','proposed_name_for_review':'Moon Crater Phase4 — Silver and Bronze','recommended_mapping_correction':'Keep the owner-canonical MCP4 name. Preserve O003 legacy title and convex-moon URL as source identifiers, not as geometry or a separate product. Link O064 as historical duplicate photographic source; do not present it as a second currently public product.','platform_action':'NONE; no route, title, archive, stock or price mutation performed.'},
        'current_and_historical_source_facts':{'O003':{'source_state':'CURRENT_PUBLIC','sku':'SQ1605793','price_GBP':'350.00','description_dimensions_cm':[25,25,6],'stock_unlimited':True},'O064':{'source_state':'CACHED_NATIVE_ONLY_PRODUCT_PAGE404','sku':'EBAY-188568590316','source_amount':'80.33','currency':'UNENCODED_IN_CACHED_NATIVE_EXPORT','description_dimensions_cm':[25,25,6],'cached_visibility':'No','cached_stock_setting':'1','native_added_updated_published_clocks':'NOT_AVAILABLE_IN_CACHED_EXPORT'}},
        'photographic_evidence':[photo_pair('O003','O064',left_index,right_index,'SAME_PHOTOGRAPHIC_VIEW_DIFFERENT_ENCODING','Matching camera view, textured silver/bronze patina pattern and surrounding stone/table background.') for left_index,right_index in [(0,0),(1,1),(2,2),(3,3),(4,4),(5,5),(6,7)]],
        'additional_historical_photo_evidence':{'O064_gallery_index':6,'description':'Reverse image shows one central recessed metal keyhole plate. This is historical pictured hardware only; actual installed fixing, attachment, count and load rating are not certified. Standing offered keyhole/French-cleat choices remain intact.'},
        'sale_unit_assessment':'Both descriptions offer one sculpture, not a set. Seven/eight gallery images are views, not quantities; cached stock1 is not independently verified physical stock.',
        'working_price_recommendation':'Refresh the source-price status to£350 currently observed on O003. Keep80.33 as historical native amount with unencoded currency and conflicting commercial context; do not average or promote it to a currentGBP quote.',
        'genuinely_missing_evidence':['O064 authenticated account/hidden/draft/lifecycle state;404 and collection omission are not account absence.','Whether the lower historical amount80.33 was intentional, and its currency in the original source.','Exact physical-cast continuity, actual current fixing and stock/lead time.'],
        'evidence_refs':source_refs(['O003','O064'],4,['BSI-1AF0A83FAA37'])})

    for index, proposal in enumerate(proposals):
        proposal['all_native_metadata_comparison_locator'] = local_ref('CASE_COMPARISONS.json', '/comparisons/' + str(index))
        proposal['master_import_state'] = 'ISOLATED_PROPOSAL_ONLY_AWAITING_COORDINATOR_IMPORT_RECEIPT'
        proposal['physical_measurement_or_stock_confirmation_performed'] = False
        proposal['shared_or_platform_writes_performed'] = 0
    result = {'schema':'boldstone.public-listing-overlap-proposals.v1','created_utc':now(),
        'frozen_master':{'path':str(master_path),'sha256':digest(master_path)},
        'fresh_inventory':{'path':str(OUT/'FRESH_PUBLIC_INVENTORY.json'),'sha256':digest(OUT/'FRESH_PUBLIC_INVENTORY.json')},
        'review_scope':'Five explicitly assigned overlap cases, ten source offers. Public native record identity, depicted design identity, exact configuration and physical cast identity remain separate.',
        'summary':{'cases':5,'source_offers':10,'currently_public_case_products':8,'historical_case_products_with_canonical_url404':2,'current_duplicate_marketing_pairs_supported':1,'historical_duplicate_marketing_pairs_supported':1,'different_photographed_surface_version_pairs':1,'same_design_configuration_unresolved_pairs':2,'individual_count_increment':0},
        'reviewed_image_scope':{'current_native_gallery_images':30,'historically_native_linked_CDN_images':9,'cached_source_selected_previews':10,'images_reviewed_using':'tools.view_image contact sheets; all galleries represented, including reverse/detail/context images','encoded_or_pixel_equality_claimed_as_physical_identity':False},
        'global_limits':['No authenticated/admin/hidden/draft inventory, checkout or physical-stock verification.','All original source records, sealed20October outputs, current master and workbook remain unchanged.','Current public prices are listing observations, not final retail approval or bespoke quotes.','No public collection/account absence equivalence.','No design/finish/quantity inference from titles or number of photographs alone.','No set weight/price division, new measured dimensions, hardware load certification or manufactured-stock count.','No platform mutations, Dropbox calls, messages to others or external private-image uploads.'],
        'proposals':proposals}
    save('OVERLAP_PROPOSALS.json',result)
    print(json.dumps({'path':str(OUT/'OVERLAP_PROPOSALS.json'),'sha256':digest(OUT/'OVERLAP_PROPOSALS.json'),'summary':result['summary']},indent=2))

if __name__ == '__main__':
    main()
