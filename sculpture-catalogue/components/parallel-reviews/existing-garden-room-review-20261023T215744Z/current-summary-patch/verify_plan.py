"""Rehearse only the assigned five-option note plan in memory."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import html
import json

H = Path(__file__).resolve().parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
jsha = lambda x: hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
p = read(H / 'patch-plan.json')
src, cov = Path(p['source_register']['path']), Path(p['source_coverage']['path'])
checks = []

def check(name, condition):
    checks.append({'check': name, 'pass': bool(condition)})
    if not condition:
        raise AssertionError(name)

check('Frozen source register hash', sha(src) == p['source_register']['sha256'])
check('Frozen coverage hash', sha(cov) == p['source_coverage']['sha256'])
for e in p['source_native_evidence']:
    check('Sealed evidence ' + Path(e['path']).name, sha(e['path']) == e['sha256'])
g, coverage_doc = read(src), read(cov)
candidate = copy.deepcopy(g)
original = {x['product_id']: x for x in g['options']}
proposed = {x['product_id']: x for x in candidate['options']}
coverage = {x['option_id']: x for x in coverage_doc['coverage']}
expected = {'BSI-3C849B547D50', 'BSI-F95020D6821C', 'BSI-830A4594D176', 'BSI-3DEA4D29C4A2', 'BSI-489226D6FF87'}
check('Exactly five assigned targets', set(p['exact_target_option_ids']) == expected and len(p['items']) == 5 and {x['option_id'] for x in p['items']} == expected)
for item in p['items']:
    oid = item['option_id']
    old, new = original[oid], proposed[oid]
    guard, change, history = item['guards'], item['replace_current_fields'], item['append_history']
    check(oid + ' full option guard', jsha(old) == item['option_sha256_before'])
    check(oid + ' exact prior fields', all(old[k] == v for k, v in guard['context_fields'].items()))
    check(oid + ' existing Available role', coverage[oid]['in_situ'] == guard['coverage_in_situ'] and coverage[oid]['in_situ']['status'] == 'Available' and old['photo_coverage'] == guard['option_photo_coverage'])
    check(oid + ' file and actual parent', old['context_file_id'] == coverage[oid]['in_situ']['reference']['file_id'] == guard['verified_native_reference']['file_id'] and old['context_folder_id'] == coverage[oid]['in_situ']['reference']['folder_id'] == guard['verified_native_reference']['folder_id'])
    check(oid + ' allowed fields', set(change) <= {'context_status', 'context_description'} and 'context_description' in change)
    if oid == 'BSI-3C849B547D50':
        check(oid + ' Azure status unchanged', set(change) == {'context_description'} and 'leaning' in change['context_description'])
    else:
        check(oid + ' pending to already Available', old['context_status'] == 'Review pending' and change.get('context_status') == 'Available')
    check(oid + ' dated full history', history['field'] == 'historical_context_summary_revisions' and history['field'] not in old and history['entry']['prior_context_fields'] == guard['context_fields'] and history['entry']['recorded_utc'].startswith('2026-10-23T'))
    check(oid + ' no approvals or physical claims', history['entry']['explicit_owner_image_approval_added'] is False and history['entry']['physical_verification_added'] is False and history['entry']['image_role_changed'] is False)
    new.update(copy.deepcopy(change))
    new[history['field']] = [copy.deepcopy(history['entry'])]
    check(oid + ' all other fields exact', {k: v for k, v in old.items() if k not in change} == {k: v for k, v in new.items() if k not in change and k != history['field']})
    check(oid + ' earlier history exact', all(new[k] == v for k, v in old.items() if k.startswith('historical_')))
changed = [oid for oid in original if original[oid] != proposed[oid]]
check('Only five assigned records differ', set(changed) == expected)
check('All other register sections identical', {k: v for k, v in g.items() if k != 'options'} == {k: v for k, v in candidate.items() if k != 'options'})
check('188 retained identities and order', [x['product_id'] for x in g['options']] == [x['product_id'] for x in candidate['options']] and len(candidate['options']) == 188)
check('187 active options unchanged', len(candidate['active_option_ids']) == 187 and candidate['active_option_ids'] == g['active_option_ids'])
check('All photo roles unchanged', all(x.get('photo_coverage') == proposed[x['product_id']].get('photo_coverage') for x in g['options']))
check('Five description and four status changes only', sum(original[oid].get('context_description') != proposed[oid].get('context_description') for oid in original) == 5 and sum(original[oid].get('context_status') != proposed[oid].get('context_status') for oid in original) == 4)
check('Source files unchanged', sha(src) == p['source_register']['sha256'] and sha(cov) == p['source_coverage']['sha256'])
receipt = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_LOCAL_REHEARSAL_ONLY', 'plan_path': str(H / 'patch-plan.json'), 'plan_sha256': sha(H / 'patch-plan.json'), 'checks_passed': len(checks), 'checks': checks, 'changed_option_ids_in_memory': changed, 'current_descriptions_changed_in_memory': 5, 'current_statuses_changed_in_memory': 4, 'history_entries_added_in_memory': 5, 'source_files_unchanged': True, 'canonical_writes': 0, 'dropbox_writes': 0, 'current_workbook_updated': False, 'publication_status': 'Awaiting main writer combined cleanup', 'prior_failed_verifier_attempt': str(H / 'verification-attempt-1-failure.json')}
(H / 'verification-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
escape = lambda s: html.escape(str(s), quote=True)
sections = []
for item in p['items']:
    prior = item['guards']['context_fields']['context_status']
    current = item['replace_current_fields'].get('context_status', prior)
    sections.append('<section><h2>' + escape(item['name']) + '</h2><p><a href="' + escape(item['image_url']) + '">Image</a> · <a href="' + escape(item['folder_url']) + '">Containing folder</a></p><dl><dt>Current status</dt><dd>' + escape(prior) + '</dd><dt>Proposed status</dt><dd>' + escape(current) + '</dd><dt>Proposed description</dt><dd>' + escape(item['replace_current_fields']['context_description']) + '</dd></dl></section>')
(H / 'corrections.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Five catalogue description corrections</title><style>body{font:17px/1.5 system-ui;max-width:900px;margin:48px auto;padding:0 24px;color:#222}section{border-top:1px solid #ccc;margin-top:32px;padding-top:16px}dt{font-weight:650}dd{margin:0 0 12px}a{color:#075691}</style><h1>Five catalogue description corrections</h1><p>Prepared for the main catalogue merge. The selected images and their existing roles remain the same. Earlier descriptions will be retained in dated history.</p>' + ''.join(sections) + '</html>')
print(json.dumps({'status': receipt['status'], 'checks_passed': len(checks), 'plan_sha256': receipt['plan_sha256'], 'receipt_sha256': sha(H / 'verification-receipt.json'), 'canonical_writes': 0}))
