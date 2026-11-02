"""Audit native draft readbacks against fresh catalogue availability."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.request import urlopen


def main(root):
    folder = root / 'catalogue-copy-disclosures'
    read = lambda name: json.loads((folder / name).read_text())
    plan = read('chairish-fulfilment-plan.json')
    receipts = read('chairish-fulfilment-receipts.json')
    targets = {r['sku']: r for r in plan['records']}
    assert len(targets) == len(plan['records']) == len(receipts)
    assert {r['sku'] for r in receipts} == set(targets)
    assert read('chairish-fulfilment-intent.json')['phase'] == 'VERIFIED'
    with urlopen('http://127.0.0.1:8767/api/specifications', timeout=30) as response:
        current = json.load(response)
    assert current['source_hash'] == plan['source_hash']
    products = {p['id']: p for p in current['products']}
    allowed = {'id_description', 'id_period_made', 'id_lead_time'}
    sentence = ('All designs can be customised. Completely new commissions can also '
                'be created in collaboration with designer Sally Price.')
    for receipt in receipts:
        r = targets[receipt['sku']]
        assert (receipt['id'], receipt['url']) == (r['native_id'], r['url'])
        assert receipt['status'] == 'SAVED_REOPENED_DRAFT_ONLY'
        before, after = receipt['before'], receipt['after']
        for k in ('sku', 'title', 'price', 'photos', 'taxonomy', 'colour', 'state'):
            assert before[k] == after[k], (r['sku'], k)
        assert [f for f in before['fields'] if f['id'] not in allowed] == [
            f for f in after['fields'] if f['id'] not in allowed]
        assert after['state'] == 'draft' and after['description'] == r['description']
        assert after['description'].count(sentence) == 1
        values = {f['id']: f['value'] for f in after['fields']}
        assert values['id_period_made'] == 'NOT_MADE' and values['id_lead_time'] == 'W2'
        p = products[r['catalogue_id']]
        source = {f['key']: f['value'] for f in p['fields'] + p['listing_fields']}
        assert source['Availability'] == r['availability']
        assert source['Lead time'] == r['source_lead_time']
    report = dict(status='PASS_SAVED_REOPENED_MADE_TO_ORDER_DRAFTS',
        verified_at=datetime.now(timezone.utc).isoformat(), count=len(receipts),
        source_hash=current['source_hash'], source_revision=current['revision'],
        native_period='NOT_MADE', native_lead_time='14 days',
        description_dispatch='Within 10 working days', native_submissions=0,
        protected_fields_unchanged=True,
        limitations=['Native 14-day setting is two calendar weeks; holiday schedules must fit the displayed deadline.',
            'Draft settings do not resolve programme eligibility, origin, shipping, discounts or publication.'],
        records=[{k:r[k] for k in ('catalogue_id','sku','id','url','at','status')} for r in receipts])
    (folder / 'chairish-fulfilment-final-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ('status','count','native_submissions','protected_fields_unchanged')}))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
