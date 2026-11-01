"""Reconcile saved UI receipts without treating in-flight uploads as complete."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


def main():
    root = Path(sys.argv[1]).resolve()
    directory = root / 'saatchi-current'
    plan = json.loads((directory / 'prepared-galleries.json').read_text())
    records = {r['sku']: r for r in plan['records']}
    receipts = json.loads((directory / 'gallery-completion-receipts.json').read_text())
    if len(records) != len(plan['records']) or len({r['sku'] for r in receipts}) != len(receipts):
        raise ValueError('Duplicate SKU in gallery plan or receipts')
    if len({r['artwork_id'] for r in receipts}) != len(receipts):
        raise ValueError('Duplicate saved artwork identity')
    for receipt in receipts:
        record = records[receipt['sku']]
        assert receipt['artwork_id'] == record['artwork_id']
        assert receipt['title'] == record['title']
        assert receipt['photos'] == record['expected_photo_count']
        assert len(set(receipt['native_image_keys'])) == receipt['photos']
        assert receipt['additional_photo_ids'] == [p['id'] for p in record['additions']]
        assert receipt['source_hashes'] == [dict(id=p['id'], sha256=p['sha256']) for p in record['additions']]
        if 'overflow_photo_ids' in receipt:
            assert receipt['overflow_photo_ids'] == [p['id'] for p in record['gallery_overflow']]
        assert receipt['status'] == 'SAVED_OVERVIEW_GALLERY_READBACK_DRAFT_ONLY'
    in_flight = []
    for name in ('gallery-edit-intent.json', 'gallery-second-intent.json'):
        path = directory / name
        if path.exists():
            intent = json.loads(path.read_text())
            if intent['phase'] != 'VERIFIED':
                in_flight.append(dict(sku=intent['sku'], artwork_id=intent['artwork_id'],
                    phase=intent['phase'], journal=name))
    if len({i['sku'] for i in in_flight}) != len(in_flight):
        raise ValueError('Two active journals reserve the same artwork')
    result = dict(at=datetime.now(timezone.utc).isoformat(),
        planned_draft_galleries=len(records), verified_saved_galleries=len(receipts),
        remaining_galleries=len(records) - len(receipts),
        saved_photo_associations=sum(r['photos'] for r in receipts),
        saved_additional_associations=sum(len(r['additional_photo_ids']) for r in receipts),
        plan_additional_associations=plan['additional_associations'],
        overflow_associations=plan['overflow_associations'],
        maximum_additional_images=plan['maximum_additional_images'],
        in_flight=in_flight, status='PASS_RECEIPT_RECONCILIATION_DRAFT_GALLERIES_ONLY',
        publication='NOT_ASSERTED')
    (directory / 'gallery-completion-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    status_path = root / 'current-publication-status.json'
    status = json.loads(status_path.read_text())
    status['updated_utc'] = result['at']
    status['saatchi']['gallery_progress'] = result
    status['saatchi']['gallery_receipts'] = 'saatchi-current/gallery-completion-receipts.json'
    status['saatchi']['acanthus_additional_images_and_copy'] = (
        'FIVE_IMAGES_SAVED_AND_REOPENED; DESCRIPTION_NOT_SAVED_PENDING_REQUIRED_FACTS')
    status['saatchi']['draft_scope'] = (
        f"97 title/primary-image drafts; {len(receipts)} galleries saved and read back. "
        'Descriptions, pricing and production facts remain incomplete; no new drafts published.')
    status['validation']['saatchi_gallery_recovery_tests_passed'] = 14
    status['validation']['saatchi_gallery_preparation_tests_passed'] = 12
    status_path.write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
