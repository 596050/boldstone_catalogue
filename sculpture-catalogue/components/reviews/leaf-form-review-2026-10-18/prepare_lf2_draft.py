"""Prepare the second individual position without changing the current LF1 owner question."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    output = HERE / 'lf2-white/component-review.draft.json'
    assert not output.exists(), 'Draft already prepared'
    progress_path = ROOT / 'components/reviews/specification_review_progress.json'
    progress = read(progress_path)
    before, before_sha = copy.deepcopy(progress), sha(progress_path)
    cp = read(ROOT / 'components/reviews/walkthrough_checkpoint.json')
    assert cp['current_component_layout_id'] == 'LEAF-FORM-LF1-WHITE' and not cp['current_answer_recorded']
    source_path = HERE / 'lf1-white/component-review.json'
    source = read(source_path)
    meta = read(HERE / 'metadata-links.json')
    selected = next(x for x in meta['selected'] if x['label'] == 'LF2_B')
    file_id, folder_id = selected['file']['file_id'], selected['folder']['file_id']
    links = {x['file_name']: x for x in meta['previews']}
    now = datetime.now(timezone.utc).isoformat()
    card = copy.deepcopy(source)
    card.update({'prepared_utc': now, 'family_review_number': 2,
        'component_layout_id': 'LEAF-FORM-LF2-WHITE', 'size_finish_variant_id': 'LEAF-FORM-LF2-WHITE',
        'proposed_name': 'Leaf Form 2 — White (LF2)', 'display_name': 'Leaf Form 2 — White (LF2)',
        'draft_state': 'PREPARED_NOT_PRESENTED; OWNER NAME AND ALL SIX GROUPS UNAPPROVED',
        'scope': 'Individual LF2/PositionB orientation, separately reviewable/purchasable as one panel. Historical maker row37describes this position separately from row36LF1. No actual mould inventory, cast identity or full specifications are confirmed.',
        'primary_image_id': file_id, 'primary_folder_id': folder_id,
        'primary_image_link': links[file_id]['copy_link_url'], 'primary_folder_link': links[folder_id]['copy_link_url'],
        'pair_target_position': 'Left', 'garden_target_position': 'Left', 'exhibition_target_position': 'Right',
        'opposite_position_reference_id': source['primary_image_id'],
        'individual_sale_unit': {'quantity': 1, 'description': 'One LF2/PositionB panel', 'live_listing_prepared_or_published': False},
        'next_review_after_keep': {'component_id': 'BC-LEAF-FORM', 'review_number': 67,
            'variant_id': 'LEAF-FORM-GOLD', 'variant_only_review': True, 'label': 'Leaf Form — Gold reference'},
        'draft_basis': rel(source_path), 'draft_basis_sha256': sha(source_path)})
    for item in card['specification_review_items']:
        item['proposal_id'] = item['proposal_id'].replace('LF1', 'LF2')
        item['basis'] = item['basis'].replace('row36', 'row37').replace('rows34/36', 'rows34/37')
    dimension = card['specification_review_items'][0]
    dimension['basis'] = 'Maker rows34/37and the two-panel listing explicitly provide a35×35cmper-panel standard, with6cmlisting depth and5–7cmmaker side depth. Related LF1single-offer40×20description remains a separate family source conflict; neither it nor photographs measures this LF2cast.'
    material = card['specification_review_items'][2]
    material['display'] = 'White marble stone finish / Jesmonite AC730 — historical LF2maker standard; actual cast recipe unconfirmed'
    material['basis'] = 'Historical row37specifies AC730white standard for LF2. Related LF1single-listinggypsum wording is retained as family evidence, not transferred as this LF2cast recipe.'
    price = card['specification_review_items'][4]
    price.update({'display': '£350 per LF2panel — proposal using related LF1single-offer price; exact LF2offer unconfirmed',
        'value': {'proposed_price_gbp': 350, 'related_LF1_single_listing_price_gbp': 350,
            'exact_LF2_standalone_offer_confirmed': False, 'owner_individual_price_approved': False,
            'pair_listing_price_gbp_not_allocated': 600},
        'status': 'UNAPPROVED PRICE PROPOSAL; RELATED LF1PRICE ONLY',
        'basis': 'Use350GBPas a discussion proposal from related LF1single listing only. No exact LF2standalone Squarespace/Shopify counterpart is established, and pair600GBPis not divided.'})
    mapping = card['platform_mapping']
    mapping['related_LF1_single_offer'] = mapping.pop('single_offer')
    mapping['single_offer'] = {'squarespace_id': None, 'shopify_handle': None, 'sku': None,
        'status': 'EXACT LF2STANDALONE OFFER UNCONFIRMED'}
    mapping['dropbox_listing_level']['single_image_applies_to_this_position'] = False
    mapping['dropbox_listing_level']['single_image_scope'] = 'Related LF1opposite-position source only'
    mapping['individual_component_level'].update({'component_layout_id': card['component_layout_id'],
        'maker_code': 'LF2-35x35', 'maker_position': 'B'})
    card['photo_coverage'].update({'opposite_LF2_clean_front_inherited_as_LF1': False,
        'clean_LF2_reference_available': True, 'clean_reference_installation_provenance_confirmed': False,
        'scope': 'LF2is left in exact pair001/garden003, right in exhibition039. Clean white001PNGdepicts LF2; native brick-wallLF2references also exist. Finished rear and verified indoor home/client provenance remain missing.'})
    card['open_gaps'][0] = 'Owner LF2name and depicted component-position identity'
    card['open_gaps'][5] = 'Exact standalone LF2Squarespace/Shopify counterpart/shared SKU'
    protected_paths = [ROOT / 'components/reviews/user_classifications.json', ROOT / 'components/checkpoint.json', ROOT / 'checkpoint.json',
        ROOT / 'components/reviews/walkthrough_checkpoint.json', ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'], source_path]
    protected = {str(path): sha(path) for path in protected_paths}
    write(HERE / 'lf2-white/before-draft-preparation.json', {'recorded_utc': now,
        'progress': before, 'progress_sha256': before_sha, 'protected_sha256': protected})
    write(output, card)
    parent = progress['reviews']['BC-LEAF-FORM']
    assert 'LEAF-FORM-LF2-WHITE' not in parent['component_layouts']
    parent['component_layouts']['LEAF-FORM-LF2-WHITE'] = {
        'reviewed_utc': now, 'review_number': 67, 'proposed_name': card['proposed_name'],
        'component_layout_id': card['component_layout_id'], 'draft_state': card['draft_state'],
        'identity_confirmed': False, 'specifications_approved': False, 'physical_specs_verified': False,
        'specification_proposals': copy.deepcopy(card['specification_review_items']),
        'primary_image_id': file_id, 'primary_folder_id': folder_id, 'review_record': rel(output),
        'platform_mapping': mapping, 'photo_coverage': card['photo_coverage'],
        'individual_sale_unit': card['individual_sale_unit'], 'gaps': card['open_gaps']}
    parent['pending_component_layouts'][0]['draft_review_record'] = rel(output)
    progress['updated_utc'] = now
    assert len(card['specification_review_items']) == 6 and all(not x['owner_approved'] for x in card['specification_review_items'])
    assert all(sha(Path(path)) == digest for path, digest in protected.items()) and sha(progress_path) == before_sha
    write(progress_path, progress)
    assert read(progress_path) == progress
    print(json.dumps({'status': 'PASS', 'LF2_individual_record_prepared_with_six_unapproved_groups': True,
        'LF1_current_owner_question_unchanged': True, 'no_owner_approval_or_platform_counterpart_inferred': True}))


if __name__ == '__main__':
    main()
