"""Reconcile attempted deliveries and resume only this batch's unsubmitted jobs."""
from pathlib import Path
import json, sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path[:0] = [str(ROOT / 'social-publisher'), str(ROOT / 'outputs/google-social-catchup-20261120')]
from common import atomic_json, digest, utc
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from engine import Engine
from journal import Store
import hold_google_unpublished

hold_google_unpublished.OUT = OUT
settings = Settings()
state = ROOT / 'social-publisher/state'
requested = settings.jobs(OUT / 'manifest.json')
assert len(requested) == 9

with Store(state) as store:
    chrome = GoogleFastChrome(settings, state)
    # Read the exact reserved tabs before adopting their already inspected routes.
    permitted = {
        'verification': 'https://www.linkedin.com/in/sally-price-1193858a/',
        'boldstone_google_business_profile': settings.profile('boldstone_google_business_profile')['inventory_url'],
    }
    for name, route in permitted.items():
        binding = chrome.bindings[name]
        inventory = chrome.state_for(binding)
        _, tab = chrome.find(inventory, binding['window_id'], binding['tab_id'])
        if tab['url'] == binding['url']:
            continue
        assert tab['url'] == route and not chrome.target_foreground(inventory, binding)
        actual = {**binding, 'url': tab['url']}
        snapshot = chrome.evaluate(actual, {'op': 'snapshot', 'fullDocument': True, 'includeHTML': True}, readonly=True)
        assert not snapshot.get('editors')
        if name == 'verification':
            assert 'Sally Price' in snapshot['text'] and 'Resources' in snapshot['text']
        else:
            assert 'Your posts' in snapshot['text'] and 'Ammonite Grande I (Left) - White' in snapshot['text']
        proof = {'utc': utc(), 'previous_binding': dict(binding), 'observed_tab': tab, 'snapshot': snapshot,
                 'same_reserved_tab_and_owner': True, 'no_composer_fields': True}
        path = OUT / (name + '-inspected-route-adoption.json')
        atomic_json(path, proof)
        binding.update(url=tab['url'], dirty=False)
        binding.pop('pending_url', None)
        chrome.save_bindings()
        store.event('INSPECTED_RESERVED_ROUTE_ADOPTED', profile_id=name,
                    evidence_path=str(path), evidence_sha256=digest(path.read_bytes()))
    chrome.close()

    # Never replay either attempted submission, even if its native record lags.
    for jid, native in [
        ('2a9e5ce5325ad446cf7344c2b42a151e', 'https://www.google.com/local/business/15009857378722117958/promote/updates/3900787434995532726/edit'),
        ('3c4461c8a2d3b7f948c2ed2d0582e39a', None),
    ]:
        job = store.get(jid)
        assert store.has_intent(jid)
        if job['state'] == 'PUBLISHED':
            continue
        chrome = GoogleFastChrome(settings, state)
        try:
            Engine(store, Workflow(settings, chrome, state), settings.policy).reconcile(jid, native_url=native)
        except Exception as error:
            print(json.dumps({'job_id': jid, 'reconciliation_error': str(error), 'code': getattr(error, 'code', type(error).__name__)}), flush=True)
        finally:
            chrome.close()
        print(json.dumps({'job_id': jid, 'state': store.get(jid)['state']}), flush=True)

    for expected in requested:
        jid = expected['id']
        job = store.get(jid)
        assert job['content_hash'] == expected['content_hash']
        if job['state'] == 'PUBLISHED' or store.has_intent(jid):
            continue
        chrome = GoogleFastChrome(settings, state)
        try:
            profile = job['payload']['profile_id']
            binding = chrome.bindings[profile]
            if chrome.target_foreground(chrome.state_for(binding), binding):
                print(json.dumps({'job_id': jid, 'state': 'USER_USING_RESERVED_TAB', 'no_changes': True}), flush=True)
                continue
            if job['state'] == 'BLOCKED':
                store.event('AUTHORIZED_BATCH_UNSUBMITTED_RESUMED', job_id=jid, batch_id=job['payload']['batch_id'])
                store.change(jid, 'QUEUED')
            Engine(store, Workflow(settings, chrome, state), settings.policy).run(job_id=jid)
            current = store.get(jid)
            if current['state'] != 'PUBLISHED' and store.has_intent(jid) and profile == 'boldstone_google_business_profile':
                hold_google_unpublished.hold_unpublished(store, settings, chrome, jid)
        except Exception as error:
            print(json.dumps({'job_id': jid, 'error': str(error), 'code': getattr(error, 'code', type(error).__name__)}), flush=True)
        finally:
            chrome.close()
        job = store.get(jid)
        print(json.dumps({'job_id': jid, 'title': job['payload']['title'], 'profile_id': job['payload']['profile_id'], 'state': job['state'], 'last_error': job['last_error']}), flush=True)

    rows = []
    for expected in requested:
        job = store.get(expected['id'])
        rows.append({k: job[k] for k in ['id', 'post_key', 'state', 'receipt', 'last_error']} | {
            'title': job['payload']['title'], 'profile_id': job['payload']['profile_id'], 'has_intent': store.has_intent(job['id'])})
    atomic_json(OUT / 'recovery-results.json', {'utc': utc(), 'requested_deliveries': 9, 'results': rows,
                                              'complete': all(r['state'] == 'PUBLISHED' for r in rows)})
    store.export()
    store.backup()
