"""Refresh copy progress from saved native readbacks, without claiming publication."""
from datetime import datetime, timezone
from collections import Counter
import json
from pathlib import Path
import sys


def main():
    root = Path(sys.argv[1]).resolve()
    path = root / 'current-publication-status.json'
    status = json.loads(path.read_text())
    now = datetime.now(timezone.utc).isoformat()
    copies = root / 'catalogue-copy-disclosures'
    wes_submission_path = copies / 'wescover-latest-copy-submission.json'
    wes_submission = json.loads(wes_submission_path.read_text()) if wes_submission_path.exists() else None
    wes_submitted = bool(wes_submission and wes_submission.get('phase') == 'NATIVE_SUBMISSION_RECEIVED')
    manifests = {
        'in6192': 'ebay-in6192-description-readbacks.json',
        'marketplace': 'marketplace-copy-receipts.json',
        'wescover': 'wescover-copy-receipts.json',
        'chairish': 'chairish-copy-receipts.json',
        'saatchi': 'saatchi-copy-receipts.json',
    }
    counts = {}
    for channel, filename in manifests.items():
        receipts = json.loads((copies / filename).read_text())
        skus = {r['sku'] for r in receipts}
        assert len(skus) <= 176
        if channel == 'marketplace':
            assert len({r['listing_id'] for r in receipts}) == len(receipts), 'Repeated native listing receipt'
        target = status['ebay']['in6192'] if channel == 'in6192' else status[
            'facebook_marketplace' if channel == 'marketplace' else channel]
        target['latest_description_refresh'] = {
            'saved_and_reopened_components': len(skus),
            'remaining_components': 176 - len(skus),
            'evidence': 'catalogue-copy-disclosures/' + filename,
            'latest_saved_at': max(r['at'] for r in receipts),
            'scope': 'Customisation and new commissions with Sally Price; applicable handmade finish variation and named companion pieces.',
            'publication': ('DRAFTS_ONLY' if channel in ('in6192', 'chairish') else
                            ('SUBMITTED_NATIVE_CONFIRMATION_RECEIVED_PUBLIC_REVIEW_PENDING' if wes_submitted else
                             'GLOBAL_SUBMISSION_PENDING') if channel == 'wescover' else
                            'PUBLISHED_ARTWORK_RECORD_SAVED_PUBLIC_DESCRIPTION_NOT_RENDERED' if channel == 'saatchi' else
                            'EXISTING_LISTINGS_UPDATED_IN_PLACE'),
        }
        counts[channel] = len(skus)
    if wes_submitted:
        assert counts['wescover'] == wes_submission['records'] == 176
        status['wescover']['latest_description_submission'] = {
            'at': wes_submission['at'], 'records': wes_submission['records'],
            'status': wes_submission['phase'], 'review_notice': wes_submission['review_notice'],
            'evidence': 'catalogue-copy-disclosures/wescover-latest-copy-submission.json',
            'proof': wes_submission['proof'],
            'public_readback': 'catalogue-copy-disclosures/wescover-public-copy-pending.json',
        }
    status['ebay']['in6192']['latest_description_refresh']['verification'] = (
        'catalogue-copy-disclosures/ebay-in6192-description-verification.json')
    sapr = status['ebay']['sapr_2972']
    sapr_copy = {}
    for kind, filename, audit_filename, publication in (
        ('active_offers', 'ebay-sapr_2972_pre_submit-description-readbacks.json',
         'ebay-sapr-pre-submit-verification.json', 'AWAITING_FINAL_TERMS_ACCEPTANCE_NOT_SUBMITTED'),
        ('remaining_drafts', 'ebay-sapr_2972_drafts-description-readbacks.json',
         'ebay-sapr-66-draft-description-verification.json', 'DRAFTS_ONLY'),
    ):
        receipt_path, audit_path = copies / filename, copies / audit_filename
        if not receipt_path.exists() or not audit_path.exists():
            continue
        receipts = json.loads(receipt_path.read_text())
        audit = json.loads(audit_path.read_text())
        assert len({r['sku'] for r in receipts}) == len(receipts) == audit['records']
        assert audit['allDescriptionsReopened'] and audit['nonDescriptionChanges'] == 0
        sapr_copy[kind] = {
            'saved_and_reopened_offers': len(receipts),
            'evidence': 'catalogue-copy-disclosures/' + filename,
            'verification': 'catalogue-copy-disclosures/' + audit_filename,
            'publication': publication,
            'latest_saved_at': max(r['at'] for r in receipts),
        }
    if sapr_copy:
        sapr['latest_description_refresh'] = sapr_copy
        counts['sapr_2972'] = {kind: row['saved_and_reopened_offers'] for kind, row in sapr_copy.items()}
    specifics_path = root / 'ebay-existing-specifics-final-audit.json'
    if specifics_path.exists():
        specifics = json.loads(specifics_path.read_text())
        assert specifics['all_protected_inputs_and_primary_thumbnails_unchanged']
        assert specifics['other_bulk_cells_unchanged']
        sapr['item_specifics_accuracy'] = dict(specifics,
            evidence='ebay-existing-specifics-final-audit.json',
            changes='ebay-existing-specifics-correction-plan.json',
            readbacks='ebay-existing-specifics-staged-readbacks.json')
        sapr['remaining_existing_accuracy_checks'] = (
            'All 20 older offers were compared for dimensions, weight and material. '
            '25 corrections on 16 offers are saved and reopened in the existing revision workspace; '
            'they are not submitted. Other optional attributes and retained postage are not a complete accuracy audit.')
        if 'active_offers' in sapr_copy:
            sapr_copy['active_offers']['additional_staged_changes'] = {
                'offers': specifics['offers_with_specific_corrections'],
                'fields': specifics['corrected_fields'],
                'evidence': 'ebay-existing-specifics-final-audit.json',
            }
    marketplace = status['facebook_marketplace']
    marketplace['prior_material_check_scope'] = {
        key: marketplace.pop(key) for key in (
            'verified_unique_components', 'remaining_unverified', 'receipt_file',
            'uncertain_interrupted_batch', 'next_action') if key in marketplace
    } or marketplace.get('prior_material_check_scope', {})
    marketplace['identity_note'] = ('Some older receipts used advertising/catalogue IDs. '
        'Resolve the actual edit ID through the seller-list UI and verify exact SKU before changing copy. '
        'Do not treat two advertising/edit IDs as two products.')
    marketplace['edit_id_aliases'] = 'catalogue-copy-disclosures/marketplace-edit-id-aliases.json'
    tiktok_path = copies / 'tiktok-copy-receipts.json'
    if tiktok_path.exists():
        receipts = json.loads(tiktok_path.read_text())
        assert len({row['product_id'] for row in receipts}) == len(receipts)
        assert len({row['sku'] for row in receipts}) == len(receipts)
        states = Counter(row['status'] for row in receipts)
        verified = sum(states[state] for state in (
            'SAVED_REOPENED_LIVE', 'DRAFT_SAVED_REOPENED', 'ALREADY_PRESENT_REOPENED'))
        status['tiktok']['latest_description_refresh'] = {
            'records_with_receipts': len(receipts),
            'saved_and_reopened_components': verified,
            'by_status': dict(states),
            'remaining_existing_native_records': 164 - len(receipts),
            'catalogue_components_without_native_receipt': 176 - len(receipts),
            'latest_saved_at': max(row.get('verified_at', row['at']) for row in receipts),
            'evidence': 'catalogue-copy-disclosures/tiktok-copy-receipts.json',
            'scope': 'Append Sally Price customisation, applicable handmade variation and named companions; preserve all other native fields.',
            'publication': 'Existing live records updated through native review; inactive records saved as drafts without activation.',
        }
        counts['tiktok'] = {'records': len(receipts), 'reopened': verified, 'by_status': dict(states)}
    status['browser_current_status'] = 'AVAILABLE; EXACT PUBLICATION BLOCKERS PRESERVED IN NATIVE FORMS'
    status.pop('browser_update_notice', None)
    status['description_disclosures_pending_native_channels'] = [
        'eBay sapr_2972 active revisions await terms approval',
        'Wescover public propagation awaits review',
        'Saatchi Art incomplete drafts await required production facts',
    ]
    tiktok_refresh = status['tiktok'].get('latest_description_refresh', {})
    if tiktok_refresh.get('remaining_existing_native_records', 164) or tiktok_refresh.get('by_status', {}).get('SUBMITTED_FOR_REVIEW'):
        status['description_disclosures_pending_native_channels'].append('TikTok remaining records and pending native review')
    status['recorded_utc'] = now
    path.write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps({'at': now, 'latest_descriptions_verified': counts}, indent=2))


if __name__ == '__main__':
    main()
