"""Apply the owner's scoped removal through the app's version-checked save API."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return json.load(response)


def index(library):
    return ({a['id']: a for a in library['images']},
            {(r['kind'], r['product_id'], r['item_id']): r for r in library['reviews']})


def candidate(row, images, reviews):
    aid, pid = row['asset_id'], row['product_id']
    image = images.get(aid)
    record = reviews.get(('image', pid, aid))
    types = reviews.get(('asset', '', aid), {}).get('data', {}).get('types', (image or {}).get('types', []))
    return record if image and 'in_situ' in types and record and 'listing' in record['data'].get('uses', []) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    plan = json.loads((ROOT / 'plan.json').read_text())
    if not args.apply:
        print(json.dumps({'planned_choices': len(plan['targets']), 'apply': False}))
        return
    boot = get('/api/bootstrap')
    token = boot['csrf_token']
    images, reviews = index(get('/api/library'))
    results = []
    log = ROOT / 'apply-results.jsonl'
    for row in plan['targets']:
        outcome = None
        for attempt in range(3):
            record = candidate(row, images, reviews)
            if not record:
                outcome = {'state': 'already_clear_or_no_longer_applicable'}
                break
            before = record['data']
            desired = {**before, 'uses': [u for u in before['uses'] if u != 'listing']}
            if desired.get('primary'):
                desired['primary'] = False
            body = {'kind': 'image', 'product_id': row['product_id'], 'item_id': row['asset_id'],
                    'version': record['version'], 'member_versions': record.get('member_versions'), 'data': desired}
            request = urllib.request.Request(BASE + '/api/reviews', data=json.dumps(body).encode(),
                        headers={'Content-Type': 'application/json', 'X-Review-Token': token}, method='POST')
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    saved = json.load(response)
                expected = {k: v for k, v in desired.items() if k != 'reviewed_content_hash'}
                actual = {k: v for k, v in saved['data'].items() if k != 'reviewed_content_hash'}
                if expected != actual:
                    raise RuntimeError('Save returned an unexpected image choice; inspect the receipt.')
                reviews[('image', row['product_id'], row['asset_id'])] = saved
                outcome = {'state': 'updated', 'before': before, 'after': saved['data'],
                           'before_version': record['version'], 'after_version': saved['version']}
                break
            except urllib.error.HTTPError as error:
                detail = json.loads(error.read()).get('error', str(error))
                if error.code == 409 and attempt < 2:
                    images, reviews = index(get('/api/library'))
                    continue
                outcome = {'state': 'failed', 'http_status': error.code, 'error': detail}
                break
        result = {'at': datetime.now(timezone.utc).isoformat(),
                  **{k: row[k] for k in ('product_id', 'product_name', 'asset_id', 'name', 'image_url', 'folder_url')},
                  **outcome}
        results.append(result)
        with log.open('a') as handle:
            handle.write(json.dumps(result) + '\n')
        if result['state'] == 'failed':
            print(json.dumps({'state': 'stopped', 'result': result}))
            return
    print(json.dumps({'updated': sum(r['state'] == 'updated' for r in results),
                      'skipped': sum(r['state'] != 'updated' for r in results),
                      'unique_images': len({r['asset_id'] for r in results if r['state'] == 'updated'}),
                      'primary_choices_cleared': sum(bool(r.get('before', {}).get('primary')) for r in results)}))


if __name__ == '__main__':
    main()
