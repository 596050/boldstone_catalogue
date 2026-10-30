import copy
from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from renumber_current_paths import WALL, PROJECT, apply, compare, plan, validate_result


def fixture(names):
    parent = {'id': 'folder', 'kind': 'folder', 'path': WALL+'/A & B/A White', 'name': 'A White'}
    rows = [parent]
    for i, name in enumerate(names):
        rows.append({'kind': 'file', 'id': f'id:{i}', 'parent_id': 'folder',
                     'path': parent['path']+'/'+name, 'name': name, 'rev': 'rev',
                     'content_hash': 'hash'+str(i), 'size': i+5, 'read_only': False,
                     'file_lock_present': False})
    return rows


class CurrentRenameTests(unittest.TestCase):
    def test_gap_closure_keeps_numeric_order_and_extensions(self):
        g = plan(fixture(['a-and-b__a-white__023.JPG','a-and-b__a-white__002.png']), 'test')[0]
        self.assertEqual([r['new_name'] for r in g['files']], ['a-and-b__a-white__001.png','a-and-b__a-white__002.JPG'])

    def test_current_then_moved_then_new(self):
        g = plan(fixture(['z.png','old__old__010.jpg','a-and-b__a-white__020.jpg','old__old__002.jpg']), 'test')[0]
        self.assertEqual([r['id'] for r in g['files']], ['id:2','id:3','id:1','id:0'])

    def test_occupied_target_stages_without_overwriting(self):
        g = plan(fixture(['a-and-b__a-white__002.jpg','a-and-b__a-white__003.jpg']), 'test')[0]
        self.assertEqual(len(g['steps']), 2)
        occupied = {r['path'].casefold(): r['id'] for r in g['files']}
        for step in g['steps']:
            for m in step['moves']:
                self.assertNotIn(m['to_path'].casefold(), occupied)
            for m in step['moves']:
                del occupied[m['from_path'].casefold()]
                occupied[m['to_path'].casefold()] = m['id']

    def test_noop_is_idempotent(self):
        original = fixture(['old__old__023.JPG','new.png'])
        g = plan(original, 'test')[0]
        for row in original[1:]:
            desired = next(r for r in g['files'] if r['id'] == row['id'])
            row.update(name=desired['new_name'], path=desired['new_path'])
        self.assertEqual(plan(original, 'test')[0]['steps'], [])

    def test_scope_and_lock_rejection(self):
        for change in ('scope', 'locked', 'missing_hash'):
            rows = fixture(['a.jpg'])
            if change == 'scope': rows[0]['path'] = '/outside/Other'
            if change == 'locked': rows[1]['file_lock_present'] = True
            if change == 'missing_hash': rows[1]['content_hash'] = None
            with self.subTest(change=change), self.assertRaises(ValueError): plan(rows, 'test')

    def test_independent_readback_rejects_content_membership_parent_and_revision_changes(self):
        row = fixture(['x.jpg'])[1]
        expected = {row['id']: row}
        paths = {row['id']: row['path']}
        compare(expected, copy.deepcopy(expected), paths, {row['id']: 'rev'})
        for field in ('size','content_hash','parent_id','path','name','rev'):
            actual = copy.deepcopy(expected); actual[row['id']][field] = 'changed'
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare(expected, actual, paths, {row['id']: 'rev'})
        with self.assertRaises(ValueError): compare(expected, {}, paths)

    def test_real_sdk_success_and_partial_failure_are_separate(self):
        from dropbox.files import FileMetadata, RelocationBatchResultEntry, RelocationBatchV2Result, RelocationBatchErrorEntry
        rows = fixture(['x.jpg', 'y.jpg']); parent = rows[0]
        item = FileMetadata(id='id:0', name='a.jpg', size=5, rev='abcdef123',
                            content_hash='a'*64, client_modified=datetime(2026, 1, 1),
                            server_modified=datetime(2026, 1, 1),
                            path_lower=(parent['path']+'/a.jpg').lower(), path_display=parent['path']+'/a.jpg')
        rows[1]['content_hash'] = 'a'*64
        moves = [{'id':'id:0','to_path':parent['path']+'/a.jpg'}, {'id':'id:1','to_path':parent['path']+'/b.jpg'}]
        result = RelocationBatchV2Result(entries=[RelocationBatchResultEntry.success(item),
                                    RelocationBatchResultEntry.failure(RelocationBatchErrorEntry.too_many_write_operations)])
        receipt = validate_result(result, moves, {r['id']:r for r in rows[1:]}, parent)
        self.assertEqual([r['state'] for r in receipt], ['success', 'failed'])
        item.id = 'id:wrong'
        with self.assertRaises(ValueError): validate_result(result, moves, {r['id']:r for r in rows[1:]}, parent)

    def test_uncertain_submission_is_journaled_and_not_repeated(self):
        import sys
        sys.path.insert(0, str(PROJECT/'catalogue-review'))
        class Fake:
            calls = 0
            def files_move_batch_v2(self, *args, **kwargs):
                self.calls += 1
                raise TimeoutError('Response lost after submission')
        client = Fake()
        @contextmanager
        def connection(_): yield client, '/BOLDSTONE MASTER'
        rows = fixture(['x.jpg']); groups = plan(rows, 'test')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'manifest.json').write_text(json.dumps({'groups':groups,'counts':{'renames':1}}))
            with patch('delete_dropbox.connection', connection), patch('renumber_current_paths.read_folder', return_value={rows[1]['id']:rows[1]}):
                with self.assertRaises(TimeoutError): apply(root)
                self.assertTrue((root/'operations/0001/001/intent.json').exists())
                with self.assertRaisesRegex(RuntimeError, 'reconciliation'): apply(root)
                self.assertEqual(client.calls, 1)


if __name__ == '__main__': unittest.main()
