from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'image-processing'))
import complete_path_renaming as completion
from shared_link_verification import original_url, link_proof


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class SharedLinkVerificationTests(unittest.TestCase):
    def original(self, name, slug):
        url = 'https://www.dropbox.com/scl/fi/frozen-token/' + slug + '?rlkey=frozen-key&dl=0'
        return {'id': 'id:original', 'name': name, 'url_sha256': digest(url)}, url

    def test_encoded_and_dropbox_hyphen_slugs_match_exact_original_bytes(self):
        for name, slug in [('Analysis output 1.png', 'Analysis-output-1.png'),
                           ('Image Oct 17, 2026, 01_28_59 PM.png', 'Image-Oct-17-2026-01_28_59-PM.png'),
                           ('Simple space.png', 'Simple%20space.png')]:
            with self.subTest(name=name):
                old, url = self.original(name, slug)
                current = url.replace(slug, 'new-numbered-name__001.png')
                self.assertEqual(original_url(old, current), url)

    def test_changed_link_token_or_query_cannot_be_accepted(self):
        old, url = self.original('Old name.png', 'Old-name.png')
        for changed in [url.replace('frozen-token', 'new-token'), url.replace('frozen-key', 'new-key')]:
            self.assertIsNone(original_url(old, changed))

    def test_reconstructed_url_requires_live_same_id_readback(self):
        old, url = self.original('Old name.png', 'Old-name.png')
        current = url.replace('Old-name.png', 'new.png')
        owned = [{'url': current, 'record': {**old, 'url_sha256': digest(current)}}]
        calls = []
        client = SimpleNamespace(sharing_get_shared_link_metadata=lambda **kw: calls.append(kw) or SimpleNamespace(id=old['id']))
        self.assertTrue(link_proof(client, old, owned)['original_url_reconstructed_hash_verified'])
        self.assertEqual(calls, [{'url': url}])
        client.sharing_get_shared_link_metadata = lambda **kw: SimpleNamespace(id='id:wrong')
        self.assertIsNone(link_proof(client, old, owned))

    def test_unverified_or_inaccessible_original_is_not_a_pass(self):
        old, url = self.original('Old name.png', 'Old-name.png')
        current = url.replace('Old-name.png', 'new.png')
        client = SimpleNamespace(sharing_get_shared_link_metadata=lambda **kw: (_ for _ in ()).throw(RuntimeError('unavailable')))
        owned = [{'url': current, 'record': {**old, 'url_sha256': digest(current)}}]
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            link_proof(client, old, owned)
        old['url_sha256'] = '0' * 64
        self.assertIsNone(link_proof(client, old, owned))


class FinalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'rename'; self.root.mkdir()
        self.runtime = Path(self.temp.name) / 'runtime'; self.runtime.mkdir()
        (self.runtime / 'server-token').write_text('test-token')
        (self.root / 'verification.json').write_text('{"status":"FAIL","original_evidence":true}')
        (self.root / 'completion-error.json').write_text('{"original_error":true}')
        self.originals = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.calls = []; self.pass_verification = True
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(completion, 'save', self.save))
        self.stack.enter_context(patch.object(completion, 'command', self.command))
        self.batches = self.stack.enter_context(patch.object(completion, 'finish_batches', side_effect=AssertionError('No renames in recovery')))
        self.http = self.stack.enter_context(patch.object(completion.urllib.request, 'urlopen',
            side_effect=lambda *a, **kw: BytesIO(b'{"last_checked":"9999-01-01","state":"ready"}')))

    def save(self, path, value, immutable=False):
        if immutable and path.exists() and json.loads(path.read_text()) != value:
            raise ValueError('Immutable artifact changed')
        path.write_text(json.dumps(value))

    def command(self, script, root, lease, extra=()):
        self.calls.append(script)
        self.assertEqual(script, 'verify_current_path_renames.py')
        output = Path(extra[1]); proof = output/'verification.json'
        self.save(proof, {'status': 'PASS' if self.pass_verification else 'FAIL'})
        if not self.pass_verification:
            raise RuntimeError('Verification failed')
        self.save(output/'current-filename-paths.json', {'at': '2026-10-27T11:00:00+00:00',
            'verification': str(proof), 'verification_sha256': completion.sha(proof)})

    def test_finalization_rechecks_without_renames_and_preserves_failed_evidence(self):
        completion.finish(self.root, self.runtime, finalize_only=True)
        self.assertEqual(self.calls, ['verify_current_path_renames.py']); self.batches.assert_not_called()
        for name, value in self.originals.items(): self.assertEqual((self.root/name).read_bytes(), value)
        pointer = json.loads((self.root/'verification-current.json').read_text())
        self.assertEqual(pointer['sha256'], completion.sha(Path(pointer['path'])))
        done = json.loads((self.root/'completion.json').read_text())
        self.assertEqual(done['verification'], pointer['path']); self.assertTrue(done['finalization_only'])
        self.assertFalse(json.loads((self.runtime/'native-writer-reservation.json').read_text())['active'])
        self.assertEqual(self.http.call_count, 2)

    def test_failed_recheck_keeps_queue_held_without_publishing(self):
        self.pass_verification = False
        with self.assertRaisesRegex(RuntimeError, 'Verification failed'):
            completion.finish(self.root, self.runtime, finalize_only=True)
        self.assertTrue(json.loads((self.runtime/'native-writer-reservation.json').read_text())['active'])
        self.assertFalse((self.runtime/'filename-readback.json').exists())
        self.assertFalse((self.root/'completion.json').exists()); self.http.assert_not_called()
        for name, value in self.originals.items(): self.assertEqual((self.root/name).read_bytes(), value)

    def test_unresolved_native_request_blocks_even_read_only_finalization(self):
        folder = self.root/'bulk-operations/001'; folder.mkdir(parents=True)
        (folder/'intent.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'still needs readback'):
            completion.finish(self.root, self.runtime, finalize_only=True)
        self.assertEqual(self.calls, []); self.http.assert_not_called()

    def test_completed_pass_cannot_be_restarted_or_reserve_writer_again(self):
        completion.finish(self.root, self.runtime, finalize_only=True)
        reservation = (self.runtime/'native-writer-reservation.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'already has a completion receipt'):
            completion.finish(self.root, self.runtime, finalize_only=True)
        self.assertEqual((self.runtime/'native-writer-reservation.json').read_bytes(), reservation)
        self.assertEqual(self.calls, ['verify_current_path_renames.py'])

    def test_completed_synchronous_receipts_allow_fresh_full_readback(self):
        folder = self.root/'operations/0027/001'; folder.mkdir(parents=True)
        original = {'id': 'one', 'size': 10, 'content_hash': 'hash', 'client_modified': 'date'}
        self.save(folder/'intent.json', {'moves': [{'id': 'one', 'to_path': '/new'}], 'preflight': {'one': original}})
        self.save(folder/'submission.json', {'mode': 'individual'})
        self.save(folder/'terminal.json', {'results': [{'id': 'one', 'state': 'success', 'file': {**original, 'path': '/new'}}]})
        completion.no_pending_requests(self.root)
        for change in [{'id': 'wrong'}, {'content_hash': 'changed'}, {'path': '/elsewhere'}]:
            self.save(folder/'terminal.json', {'results': [{'id': 'one', 'state': 'success', 'file': {**original, 'path': '/new', **change}}]})
            with self.assertRaisesRegex(RuntimeError, 'still needs readback'): completion.no_pending_requests(self.root)


if __name__ == '__main__': unittest.main()
