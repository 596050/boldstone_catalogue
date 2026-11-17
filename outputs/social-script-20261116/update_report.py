#!/usr/bin/env python3
"""Read the local outbox and publish reviewable native receipts for this batch."""
import html
import json
import sqlite3
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
WORKSPACE = OUT.parents[1]
sys.path.insert(0, str(WORKSPACE / 'social-publisher'))
from common import atomic_json, digest, utc

state = WORKSPACE / 'social-publisher/state'
manifest = json.loads((OUT / 'manifest.json').read_text())
shopping_receipts_path = WORKSPACE / 'outputs/commerce-tag-repair-20261117/repair-receipts.json'
shopping_receipts = json.loads(shopping_receipts_path.read_text()).get('deliveries', []) if shopping_receipts_path.exists() else []
shopping_by_job = {row['job_id']: row for row in shopping_receipts}
with sqlite3.connect('file:' + str(state / 'outbox.sqlite3') + '?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    records = [dict(row) for row in db.execute('SELECT id,state,payload,receipt,last_error FROM jobs')]
rows = []
for record in records:
    payload = json.loads(record['payload'])
    if payload.get('batch_id') != manifest['batch_id']:
        continue
    receipt = json.loads(record['receipt']) if record['receipt'] else {}
    verified = False
    if record['state'] == 'PUBLISHED' and all(receipt.get(key) is True for key in ('caption_verified', 'author_verified', 'photo_verified')):
        evidence = Path(receipt['evidence_path'])
        verified = evidence.is_file() and digest(evidence.read_bytes()) == receipt['evidence_sha256']
    shopping_verified = None
    if payload['platform'] in ('facebook', 'instagram'):
        shopping_verified = bool(verified and payload.get('product_tag') and
                                 json.loads(evidence.read_text()).get('product_tag_readback', {}).get('ok') is True)
        repaired = shopping_by_job.get(record['id'], {})
        if repaired.get('verified') is True and repaired.get('evidence_path'):
            repaired_evidence = Path(repaired['evidence_path'])
            shopping_verified = repaired_evidence.is_file() and digest(repaired_evidence.read_bytes()) == repaired.get('evidence_sha256')
    rows.append({'job_id': record['id'], 'title': payload['title'], 'catalogue_id': payload['catalogue_id'],
                 'platform': payload['platform'], 'profile_id': payload['profile_id'], 'state': record['state'],
                 'verified': verified, 'native_url': receipt.get('native_url'), 'verified_utc': receipt.get('verified_utc'),
                 'commerce_tag_required': payload['platform'] in ('facebook', 'instagram'),
                 'commerce_tag_verified': shopping_verified,
                 'evidence_path': receipt.get('evidence_path'), 'evidence_sha256': receipt.get('evidence_sha256'),
                 'last_error': record['last_error']})
counts = {platform: sum(row['verified'] and row['platform'] == platform for row in rows)
          for platform in ('facebook', 'instagram', 'linkedin')}
verified = sum(row['verified'] for row in rows)
intents = []
for line in (state / 'intent-ledger.jsonl').read_text().splitlines():
    try:
        event = json.loads(line)
    except ValueError:
        continue  # A live writer may not have finished its final line yet.
    if event['kind'] == 'PUBLISH_INTENT' and event.get('job', {}).get('id') in {row['job_id'] for row in rows}:
        intents.append(event)
report = {'utc': utc(), 'batch_id': manifest['batch_id'], 'status': 'PUBLISHED_NATIVE_READBACK' if verified == 15 else 'IN_PROGRESS',
          'prepared_sculptures': 5, 'prepared_deliveries': 15, 'verified_deliveries': verified,
          'verified_by_platform': counts, 'new_publish_intents': len(intents), 'helper_installed': True, 'deliveries': rows}
report['blockers'] = [{'platform': row['platform'], 'job_id': row['job_id'], 'detail': row['last_error']}
                      for row in rows if not row['verified'] and row['state'] == 'BLOCKED']
report['shopping_tags_required'] = sum(row['commerce_tag_required'] for row in rows)
report['shopping_tags_verified'] = sum(row['commerce_tag_verified'] is True for row in rows)
report['shopping_tags_missing'] = report['shopping_tags_required'] - report['shopping_tags_verified']
report['blockers'] += [{'platform': row['platform'], 'job_id': row['job_id'],
                        'detail': 'PRODUCT_TAG_MISSING: published with caption/photo verification but no verified Commerce tag; mobile tagging or replacement decision pending'}
                       for row in rows if row['verified'] and row['commerce_tag_required'] and not row['commerce_tag_verified']]
if report['blockers']:
    report['status'] = 'PARTIALLY_PUBLISHED_ACTION_REQUIRED'
atomic_json(OUT / 'publication-receipts.json', report)
previous = json.loads((OUT / 'final-status.json').read_text())
previous.update(status=report['status'], updated_utc=report['utc'], new_posts_verified=verified,
                new_posts_submitted=verified, new_posts_submitted_with_native_proof=verified, new_publish_intents=len(intents),
                helper_installed=True, verified_by_platform=counts, blocker=report['blockers'] or None,
                publication_report=str(OUT / 'publication-report.html'))
previous.update(shopping_tags_required=report['shopping_tags_required'],
                shopping_tags_verified=report['shopping_tags_verified'],
                shopping_tags_missing=report['shopping_tags_missing'])
atomic_json(OUT / 'final-status.json', previous)
table = []
for post in manifest['posts']:
    cells = ['<td>' + html.escape(post['title']) + '</td>']
    for platform in ('facebook', 'instagram', 'linkedin'):
        row = next((row for row in rows if row['catalogue_id'] == post.get('catalogue_id', post['post_key']) and row['platform'] == platform), None)
        if row and row['verified']:
            label = 'Published · shopping tag missing' if row.get('commerce_tag_required') and not row.get('commerce_tag_verified') else 'Published · verified'
            cells.append('<td><a href="' + html.escape(row['native_url'], quote=True) + '">' + label + '</a></td>')
        else:
            cells.append('<td>' + html.escape((row or {}).get('state', 'PENDING')) + '</td>')
    table.append('<tr>' + ''.join(cells) + '</tr>')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Boldstone publication receipts</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#20322d}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:14px;border-bottom:1px solid #d9e1dc}a{color:#245e71}</style><h1>Boldstone · five sculptures</h1><p>' + str(verified) + ' of 15 deliveries verified on the native platforms. Historical posts are excluded.</p><p>' + html.escape(report['utc']) + '</p><table><thead><tr><th>Sculpture</th><th>Facebook</th><th>Instagram</th><th>LinkedIn</th></tr></thead><tbody>' + ''.join(table) + '</tbody></table><p><a href="prepared-posts.html">Reviewed photographs and captions</a> · <a href="publication-receipts.json">Detailed receipts</a></p></html>'
page = page.replace('Historical posts are excluded.',
                    'These receipts verify captions, authors, photographs and caption links. Commerce shopping tags: ' +
                    str(report['shopping_tags_verified']) + ' of ' + str(report['shopping_tags_required']) +
                    ' verified. <a href="../commerce-tag-repair-20261117/review.html">Commerce repair review</a>. Historical posts are excluded.')
(OUT / 'publication-report.html').write_text(page)
print(json.dumps({key: report[key] for key in ('utc', 'status', 'verified_deliveries', 'verified_by_platform', 'new_publish_intents')}, indent=2))
