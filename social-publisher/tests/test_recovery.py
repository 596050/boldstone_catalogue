import copy
import json
import sqlite3
import subprocess
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chrome import Chrome
from common import Hold, atomic_json, canonical, digest
from engine import Engine
from journal import Store
from publisher import restore
from settings import Settings
from workflow import Workflow, render
from build_manifest import build


class FakePlatform:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.prepares = 0
        self.clicks = 0
        self.verifications = 0
        self.remote = set()
        self.prepare_error = None
        self.timeout_after_click = False
        self.verification_error = None

    def prepare(self, job):
        self.prepares += 1
        if self.prepare_error:
            raise self.prepare_error

    def submit(self, job):
        self.clicks += 1
        self.remote.add(job['id'])
        if self.timeout_after_click:
            raise Hold('APPLE_EVENT_TIMEOUT', retryable=True)

    def verify(self, job, native_url=None):
        self.verifications += 1
        if self.verification_error:
            raise self.verification_error
        if job['id'] not in self.remote:
            raise Hold('NATIVE_POST_NOT_FOUND')
        evidence = self.directory / (job['id'] + '-evidence.json')
        atomic_json(evidence, {'id': job['id'], 'caption': job['payload']['caption'], 'native_url': native_url})
        return {'native_url': native_url or 'https://www.instagram.com/p/fixture-' + job['id'] + '/',
                'caption_verified': True, 'author_verified': True, 'photo_verified': True,
                'evidence_path': str(evidence), 'evidence_sha256': digest(evidence.read_bytes())}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.state = self.directory / 'state'
        self.settings = Settings()
        self.media = self.directory / 'original.png'
        self.media.write_bytes(b'\x89PNG\r\n\x1a\nfixture-original')
        self.manifest = self.directory / 'manifest.json'
        self.source = {'schema_version': 1, 'batch_id': 'fixture', 'publish_authorized': True,
                       'posts': [{'post_key': 'BSI-TEST', 'title': 'Fixture sculpture', 'alt_text': 'White relief on a pale wall',
                                  'media_path': str(self.media), 'sha256': digest(self.media.read_bytes()),
                                  'targets': {'boldstone_instagram': {'caption': 'Fixture sculpture\nA complete caption.'}}}]}
        self.write_manifest()
        self.jobs = self.settings.jobs(self.manifest)
        self.adapter = FakePlatform(self.directory)
        self.clock = [1000.0]

    def write_manifest(self):
        atomic_json(self.manifest, self.source)

    def engine(self, store):
        return Engine(store, self.adapter, self.settings.policy, now=lambda: self.clock[0])

    def test_success_requires_native_receipt_and_is_not_replayed(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            report = self.engine(store).run()
            self.assertTrue(report['complete'])
            self.assertEqual(report['counts'], {'PUBLISHED': 1})
            self.engine(store).run()
        with Store(self.state) as store:
            self.engine(store).run()
        self.assertEqual(self.adapter.clicks, 1)

    def test_timeout_after_real_submission_reconciles_without_second_click(self):
        self.adapter.timeout_after_click = True
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            self.engine(store).run()
            self.assertEqual(store.get(self.jobs[0]['id'])['state'], 'OUTCOME_UNKNOWN')
        with Store(self.state) as store:
            self.assertTrue(self.engine(store).run()['complete'])
        self.assertEqual(self.adapter.clicks, 1)

    def test_process_dies_after_intent_before_click_never_retries_click(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            store.change(self.jobs[0]['id'], 'READY')
            store.intent(self.jobs[0]['id'])
        with Store(self.state) as store:
            report = self.engine(store).run()
            self.assertEqual(report['counts'], {'OUTCOME_UNKNOWN': 1})
            with self.assertRaisesRegex(Hold, 'Reconcile'):
                store.change(self.jobs[0]['id'], 'QUEUED')
        self.assertEqual(self.adapter.clicks, 0)

    def test_caption_failure_does_not_count_as_success(self):
        self.adapter.verification_error = Hold('NATIVE_CAPTION_MISMATCH')
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            report = self.engine(store).run()
            self.assertFalse(report['complete'])
            self.assertEqual(report['counts'], {'OUTCOME_UNKNOWN': 1})
            self.engine(store).run()
        self.assertEqual(self.adapter.clicks, 1)

    def test_exponential_prepare_backoff_is_bounded(self):
        self.adapter.prepare_error = Hold('CONTROL_MISSING', retryable=True)
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            self.engine(store).run()
            row = store.get(self.jobs[0]['id'])
            self.assertEqual(row['next_attempt'], 1010)
            self.engine(store).run()
            self.assertEqual(self.adapter.prepares, 1)
            for point in [1010, 1030, 1070]:
                self.clock[0] = point
                self.engine(store).run()
            self.assertEqual(store.get(row['id'])['state'], 'BLOCKED')
            self.assertEqual(self.adapter.prepares, 4)
        self.assertEqual(self.adapter.clicks, 0)

    def test_reversible_preparation_recovers_after_process_death(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            store.change(self.jobs[0]['id'], 'PREPARING')
        with Store(self.state) as store:
            self.assertEqual(store.get(self.jobs[0]['id'])['state'], 'QUEUED')
            self.assertTrue(self.engine(store).run()['complete'])

    def test_verification_backoff_persists_through_restart(self):
        self.adapter.verification_error = Hold('NATIVE_POST_NOT_FOUND')
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            self.engine(store).run()
            self.assertEqual(store.get(self.jobs[0]['id'])['next_attempt'], 1010)
        with Store(self.state) as store:
            self.engine(store).run()
            self.assertEqual(self.adapter.verifications, 1)
            self.clock[0] = 1010
            self.engine(store).run()
            self.assertEqual(self.adapter.verifications, 2)
        self.assertEqual(self.adapter.clicks, 1)

    def test_automatic_reconciliation_is_bounded_but_exact_url_can_finish(self):
        self.adapter.verification_error = Hold('NATIVE_POST_NOT_FOUND')
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            for attempt in range(15):
                self.clock[0] += 1000
                self.engine(store).run()
            self.assertEqual(self.adapter.verifications, self.settings.policy['max_reconcile_attempts'])
            self.adapter.verification_error = None
            self.engine(store).reconcile(self.jobs[0]['id'], 'https://www.instagram.com/p/recovered/')
            self.assertEqual(store.get(self.jobs[0]['id'])['state'], 'PUBLISHED')
        self.assertEqual(self.adapter.clicks, 1)

    def test_competing_process_cannot_claim_same_state(self):
        with Store(self.state):
            with self.assertRaises(Hold) as context:
                Store(self.state)
            self.assertEqual(context.exception.code, 'RUNNER_ALREADY_ACTIVE')

    def test_repeated_enqueue_is_idempotent(self):
        with Store(self.state) as store:
            self.assertEqual(store.enqueue(self.jobs), 1)
            self.assertEqual(store.enqueue(self.jobs), 0)

    def test_changed_caption_cannot_bypass_existing_product_guard(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            self.source['posts'][0]['targets']['boldstone_instagram']['caption'] += ' Changed.'
            self.write_manifest()
            with self.assertRaises(Hold) as context:
                store.enqueue(self.settings.jobs(self.manifest))
            self.assertEqual(context.exception.code, 'EXISTING_PRODUCT_GUARD')

    def test_renaming_product_does_not_bypass_identical_content_guard(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            self.source['posts'][0]['post_key'] = 'RENAMED'
            self.write_manifest()
            self.assertEqual(store.enqueue(self.settings.jobs(self.manifest)), 0)

    def test_manifest_requires_explicit_batch_authorization(self):
        self.source['publish_authorized'] = False
        self.write_manifest()
        with self.assertRaises(Hold) as context:
            self.settings.jobs(self.manifest)
        self.assertEqual(context.exception.code, 'MANIFEST_NOT_AUTHORIZED')

    def test_previous_published_manifest_is_rejected(self):
        self.source['posts'][0]['status'] = 'PUBLISHED_ALL_THREE_NATIVE_READBACK'
        self.write_manifest()
        with self.assertRaises(Hold):
            self.settings.jobs(self.manifest)

    def test_file_tampering_fails_before_queuing(self):
        self.media.write_bytes(b'changed')
        with self.assertRaises(Hold) as context:
            self.settings.jobs(self.manifest)
        self.assertEqual(context.exception.code, 'MEDIA_HASH_CHANGED')

    def test_promised_product_tag_must_be_explicit(self):
        self.source['posts'][0]['targets']['boldstone_instagram']['caption'] += ' Tap the product tag.'
        self.write_manifest()
        with self.assertRaises(Hold) as context:
            self.settings.jobs(self.manifest)
        self.assertEqual(context.exception.code, 'PRODUCT_TAG_REQUIRED')

    def test_profile_change_holds_queued_work_before_browser_use(self):
        job = self.jobs[0]
        self.settings.profiles['boldstone_instagram']['account_name'] = 'Changed account'
        with self.assertRaises(Hold) as context:
            Workflow(self.settings, None, self.state).context({'id': job['id'], 'payload': job['payload']})
        self.assertEqual(context.exception.code, 'PROFILE_CHANGED')

    def test_restore_old_backup_keeps_later_intent(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            store.backup()
            old_backup = self.directory / 'old.sqlite3'
            old_backup.write_bytes((self.state / 'outbox-backup.sqlite3').read_bytes())
            store.change(self.jobs[0]['id'], 'READY')
            store.intent(self.jobs[0]['id'])
        result = restore(self.state, old_backup)
        self.assertEqual(result['counts_after_intent_recovery'], {'OUTCOME_UNKNOWN': 1})
        with Store(self.state) as store:
            self.engine(store).run()
        self.assertEqual(self.adapter.clicks, 0)

    def test_restored_backup_recovers_confirmed_receipt_from_ledger(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            store.backup()
            old_backup = self.directory / 'old.sqlite3'
            old_backup.write_bytes((self.state / 'outbox-backup.sqlite3').read_bytes())
            self.engine(store).run()
        result = restore(self.state, old_backup)
        self.assertEqual(result['counts_after_intent_recovery'], {'PUBLISHED': 1})
        self.assertEqual(self.adapter.clicks, 1)

    def test_invalid_evidence_cannot_be_marked_published(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            store.change(self.jobs[0]['id'], 'READY')
            store.intent(self.jobs[0]['id'])
            self.adapter.remote.add(self.jobs[0]['id'])
            receipt = self.adapter.verify(store.get(self.jobs[0]['id']))
            Path(receipt['evidence_path']).write_text('tampered')
            with self.assertRaises(Hold):
                store.published(self.jobs[0]['id'], receipt)

    def test_torn_ledger_is_held_instead_of_erased(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            store.change(self.jobs[0]['id'], 'READY')
            store.intent(self.jobs[0]['id'])
        with (self.state / 'intent-ledger.jsonl').open('ab') as stream:
            stream.write(b'{"kind":"PUBLISH_INTENT"')
        with self.assertRaises(Hold) as context:
            Store(self.state)
        self.assertEqual(context.exception.code, 'LEDGER_TORN_WRITE')

    def test_tampered_ledger_hash_chain_is_detected(self):
        with Store(self.state) as store:
            store.enqueue(self.jobs)
            store.change(self.jobs[0]['id'], 'READY')
            store.intent(self.jobs[0]['id'])
        path = self.state / 'intent-ledger.jsonl'
        path.write_text(path.read_text().replace('PUBLISH_INTENT', 'PUBLISH_INTENX'))
        with self.assertRaises(Hold):
            Store(self.state)

    def test_historical_receipt_survives_database_rebuild(self):
        with Store(self.state) as store:
            store.import_history(self.jobs[0], {'native_url': 'https://www.instagram.com/p/existing/'})
        (self.state / 'outbox.sqlite3').unlink()
        with Store(self.state) as store:
            report = self.engine(store).run()
            self.assertEqual(report['counts'], {'HISTORICAL_VERIFIED': 1})
        self.assertEqual(self.adapter.clicks, 0)

    def test_meta_account_id_cannot_be_changed_in_navigation(self):
        p = self.settings.profile('boldstone_facebook')
        with self.assertRaises(Hold) as context:
            Settings.check_url(p, p['compose_url'].replace('103781478537396', '123'))
        self.assertEqual(context.exception.code, 'WRONG_META_ACCOUNT')

    def test_lookalike_and_non_https_hosts_are_rejected(self):
        p = self.settings.profile('sally_linkedin')
        for url in ['https://www.linkedin.com.attacker.example/', 'http://www.linkedin.com/', 'https://user@www.linkedin.com/']:
            with self.assertRaises(Hold):
                Settings.check_url(p, url)

    def test_chrome_closed_or_unbound_never_opens_it(self):
        calls = []
        chrome = Chrome(self.settings, self.state, execute=lambda *args, **kwargs: calls.append(args))
        with self.assertRaises(Hold) as context:
            chrome.bound('boldstone_instagram', mutation=True)
        self.assertEqual(context.exception.code, 'RESERVED_TAB_NOT_BOUND')
        self.assertEqual(calls, [])

    def test_chrome_active_reserved_tab_is_paused(self):
        chrome = Chrome(self.settings, self.state)
        chrome.bindings['sally_linkedin'] = {'window_id': 1, 'tab_id': 2, 'url': 'https://www.linkedin.com/feed/'}
        chrome.inventory = lambda: {'frontmost': 'com.google.Chrome', 'windows': [{'window_id': 1, 'active_tab_id': 2, 'mode': 'normal', 'tabs': [{'tab_id': 2, 'url': 'https://www.linkedin.com/feed/'}]}]}
        with self.assertRaises(Hold) as context:
            chrome.bound('sally_linkedin', mutation=True)
        self.assertEqual(context.exception.code, 'FOREGROUND_TAB_PAUSED')
        chrome.bound('sally_linkedin', mutation=False)

    def test_user_navigation_is_never_overwritten(self):
        chrome = Chrome(self.settings, self.state)
        chrome.bindings['sally_linkedin'] = {'window_id': 1, 'tab_id': 2, 'url': 'https://www.linkedin.com/feed/'}
        chrome.inventory = lambda: {'frontmost': 'com.apple.finder', 'windows': [{'window_id': 1, 'active_tab_id': 3, 'mode': 'normal', 'tabs': [{'tab_id': 2, 'url': 'https://www.linkedin.com/messaging/'}]}]}
        with self.assertRaises(Hold) as context:
            chrome.bound('sally_linkedin', mutation=True)
        self.assertEqual(context.exception.code, 'TAB_NAVIGATED_EXTERNALLY')

    def test_dirty_composer_cannot_be_navigated_away_from_even_in_recovery(self):
        chrome = Chrome(self.settings, self.state)
        chrome.bindings['sally_linkedin'] = {'window_id': 1, 'tab_id': 2, 'url': 'https://www.linkedin.com/feed/', 'dirty': True}
        chrome.inventory = lambda: {'frontmost': 'com.apple.finder', 'windows': [{'window_id': 1, 'active_tab_id': 3, 'mode': 'normal', 'tabs': [{'tab_id': 2, 'url': 'https://www.linkedin.com/feed/'}]}]}
        chrome.apple = lambda args: self.fail('Navigation must not be attempted: a beforeunload dialog could interrupt the user')
        with self.assertRaises(Hold) as context:
            chrome.navigate('sally_linkedin', 'https://www.linkedin.com/sharing/compose', recovery=True)
        self.assertEqual(context.exception.code, 'DRAFT_NEEDS_INSPECTION')

    def test_shared_readback_tab_can_be_bound_without_navigation(self):
        chrome = Chrome(self.settings, self.state)
        chrome.inventory = lambda: {'frontmost': 'com.apple.finder', 'windows': [{'window_id': 1, 'active_tab_id': 3, 'mode': 'normal', 'tabs': [{'tab_id': 2, 'url': 'about:blank'}]}]}
        chrome.apple = lambda args: self.fail('Binding must not navigate or activate a tab')
        self.assertEqual(chrome.bind('verification', 1, 2)['url'], 'about:blank')

    def test_apple_event_has_internal_and_external_timeout(self):
        def timeout(*args, **kwargs):
            self.assertEqual(kwargs['timeout'], 8)
            raise subprocess.TimeoutExpired('osascript', 8)
        chrome = Chrome(self.settings, self.state, execute=timeout)
        with self.assertRaises(Hold) as context:
            chrome.inventory()
        self.assertEqual(context.exception.code, 'APPLE_EVENT_TIMEOUT')
        self.assertIn('with timeout of 5 seconds', (ROOT / 'chrome.applescript').read_text())

    def test_source_contains_no_focus_or_native_keyboard_commands(self):
        import re
        for file in ['chrome.applescript', 'Run.applescript']:
            source = '\n'.join(line.split('--')[0] for line in (ROOT / file).read_text().splitlines())
            self.assertIsNone(re.search(r'\b(activate|keystroke)\b|key code|make new (window|tab)|set (?:the )?frontmost', source, re.I))

    def test_workflows_are_configurable_and_all_variables_resolve(self):
        for name, p in self.settings.profiles.items():
            context = {**p, 'caption': 'full caption', 'title': 'title', 'alt_text': 'image alt',
                       'product_tag': {'name': 'Sculpture - White', 'price_text': '£34.20'}}
            render(self.settings.workflow(p), context)

    def test_missing_readiness_guard_cannot_create_an_unguarded_adapter(self):
        shutil.copytree(ROOT / 'workflows', self.directory / 'workflows')
        config = self.directory / 'profiles.json'
        atomic_json(config, self.settings.data)
        workflow = self.directory / 'workflows' / 'instagram.json'
        recipe = json.loads(workflow.read_text())
        recipe['ready'] = [g for g in recipe['ready'] if g.get('purpose') != 'caption']
        atomic_json(workflow, recipe)
        with self.assertRaises(Hold) as context:
            Settings(config)
        self.assertEqual(context.exception.code, 'WORKFLOW_GUARDS_MISSING')

    def test_running_worker_notices_account_configuration_edited_on_disk(self):
        shutil.copytree(ROOT / 'workflows', self.directory / 'workflows')
        config = self.directory / 'profiles.json'
        atomic_json(config, self.settings.data)
        loaded = Settings(config)
        changed = json.loads(config.read_text())
        changed['profiles']['sally_linkedin']['account_name'] = 'Different account'
        atomic_json(config, changed)
        with self.assertRaises(Hold) as context:
            loaded.profile('sally_linkedin')
        self.assertEqual(context.exception.code, 'CONFIG_CHANGED')

    def test_wrong_native_purchase_destination_is_unconfirmed(self):
        job = copy.deepcopy(self.jobs[0])
        job['payload']['caption'] += ' https://boldstonesculpture.com/buy/p/sculpture'
        workflow = Workflow(self.settings, None, self.state)
        with self.assertRaises(Hold) as context:
            workflow.purchase_links(job, ['https://boldstonesculpture.com/buy/p/different'])
        self.assertEqual(context.exception.code, 'NATIVE_PURCHASE_LINK_MISMATCH')

    def test_facebook_outbound_wrapper_preserves_exact_destination(self):
        job = copy.deepcopy(self.jobs[0])
        url = 'https://boldstonesculpture.com/buy/p/sculpture?utm_source=facebook'
        job['payload']['caption'] += ' ' + url
        from urllib.parse import quote
        result = Workflow(self.settings, None, self.state).purchase_links(job, ['https://l.facebook.com/l.php?u=' + quote(url, safe='')])
        self.assertEqual(result[0]['expected'], url)

    def test_manifest_builder_cannot_replay_a_published_source(self):
        source = self.directory / 'old-posts.json'
        atomic_json(source, [{'title': 'Already posted', 'status': 'PUBLISHED_ALL_THREE_NATIVE_READBACK'}])
        with self.assertRaises(Hold) as context:
            build(source, self.directory / 'new.json', 'fixture', True)
        self.assertEqual(context.exception.code, 'ALREADY_PUBLISHED_MANIFEST')

    def test_manifest_builder_defaults_to_prepared_and_does_not_touch_browser(self):
        source = self.directory / 'prepared.json'
        atomic_json(source, [{'catalogue_id': 'BSI-NEW', 'sku': 'TEST', 'title': 'New sculpture', 'alt_text': 'Original',
                              'media_path': str(self.media), 'sha256': digest(self.media.read_bytes()), 'captions': {'facebook': 'New sculpture'}}])
        result = build(source, self.directory / 'new.json', 'new-batch')
        self.assertFalse(result['publish_authorized'])
        self.assertEqual(result['browser_actions'], 0)


if __name__ == '__main__':
    unittest.main()

