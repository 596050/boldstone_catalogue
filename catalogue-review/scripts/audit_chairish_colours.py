"""Reconcile saved native colour receipts with the exact catalogue-backed plan."""
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import sys
import urllib.request


def main(root):
    copy = root / 'catalogue-copy-disclosures'
    read = lambda name: json.loads((copy / name).read_text())
    plan = read('chairish-colour-plan.json')
    receipts = read('chairish-colour-receipts.json')
    expected = {r['sku']: r for r in plan['records']}
    assert len(expected) == len(plan['records'])
    assert len(receipts) == len({r['sku'] for r in receipts})
    assert set(expected) == {r['sku'] for r in receipts}
    assert read('chairish-colour-intent.json')['phase'] == 'VERIFIED'
    sentence = ('All designs can be customised. Completely new commissions can also '
                'be created in collaboration with designer Sally Price.')
    for receipt in receipts:
        target = expected[receipt['sku']]
        assert receipt['id'] == target['native_id'] and receipt['url'] == target['url']
        assert receipt['status'] == 'SAVED_REOPENED_DRAFT_ONLY'
        before, after = receipt['before'], receipt['after']
        assert {k: v for k, v in before.items() if k != 'colour'} == {
            k: v for k, v in after.items() if k != 'colour'}
        assert after['state'] == 'draft'
        assert after['sku'] == target['sku']
        assert after['colour'] == [target['colour_label']]
        assert after['description'] == target['description']
        assert sentence in after['description']
        assert after['price'] == target['price']
        assert len(after['photos']) == target['photo_count']
    with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=30) as response:
        app = json.load(response)
    assert app['source_hash'] == plan['source_hash'], 'Catalogue source changed during colour pass'
    current = {r['id']: r for r in app['products']}
    for r in plan['records']:
        fields = {f['key']: f['value'] for f in current[r['id']]['fields']}
        assert fields['Colour / appearance'] == r['colour_source']
        if r.get('visual_review'):
            visual = r['visual_review']
            assert visual['observation'] and visual['at']
            assert hashlib.sha256(Path(visual['path']).read_bytes()).hexdigest() == visual['sha256']
    report = dict(
        checked_at=datetime.now(timezone.utc).isoformat(),
        status='PASS_SAVED_REOPENED_DRAFT_COLOURS',
        source_revision=app['revision'], source_hash=app['source_hash'],
        plan_revision=plan['source_revision'],
        overall_revision_changed=app['revision'] != plan['source_revision'],
        source_verification=f"All {len(expected)} source appearance values compared exactly with the current app; underlying source hash unchanged. Visual selections retain the source mixed-finish descriptions.",
        visually_reviewed=sum(bool(r.get('visual_review')) for r in plan['records']),
        planned=len(expected), verified=len(receipts),
        changed_in_receipt_loop=sum(r['changed'] for r in receipts),
        separate_initial_trial='BOLD-93ADE7C4103D',
        initial_trial_evidence='chairish-colour-trial-before-save.json',
        native_drafts_created=0, native_drafts_submitted=0,
        unchanged_fields=['SKU', 'title', 'description', 'price', 'photos and order',
                          'other structured fields', 'other taxonomies', 'draft status'],
        colour_counts=dict(Counter(r['colour'] for r in receipts)),
        other_drafts_requiring_colour_review=plan['unassigned'],
        records=[{k: r[k] for k in ('sku', 'id', 'url', 'at', 'colour', 'changed', 'status')}
                 for r in receipts])
    (copy / 'chairish-colour-final-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'planned', 'verified',
        'changed_in_receipt_loop', 'native_drafts_created', 'native_drafts_submitted')}, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
