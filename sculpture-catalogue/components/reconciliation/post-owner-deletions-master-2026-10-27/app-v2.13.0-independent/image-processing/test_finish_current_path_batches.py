import copy
import unittest
from pathlib import PurePosixPath
from test_renumber_current_paths import fixture
from renumber_current_paths import plan
from finish_current_path_batches import candidates


class BatchPlanTests(unittest.TestCase):
    def setup_rows(self, names):
        rows=fixture(names)
        return {'groups':plan(rows,'test')}, {'wall':{'entries':copy.deepcopy(rows)},'workshop':{'entries':[]}}

    def test_disjoint_waves_resolve_gaps_without_overwriting(self):
        manifest,snapshot=self.setup_rows(['a-and-b__a-white__002.jpg','a-and-b__a-white__003.jpg','a-and-b__a-white__004.jpg','new.png'])
        completed=False
        for _ in range(12):
            moves,deferred,done=candidates(manifest,snapshot)
            self.assertEqual(deferred,[])
            if not moves:
                self.assertEqual(done,4);completed=True;break
            current={r['id']:r for r in snapshot['wall']['entries']}
            occupied={r['path'].casefold() for r in current.values()}
            for move in moves[:2]:self.assertNotIn(move['to_path'].casefold(),occupied)
            for move in moves[:2]:
                row=current[move['id']];row['path']=move['to_path'];row['name']=PurePosixPath(move['to_path']).name
        self.assertTrue(completed)

    def test_external_deletion_and_content_edit_require_new_plan(self):
        for change in ('delete','bytes','name'):
            manifest,snapshot=self.setup_rows(['old.jpg','older.jpg'])
            if change=='delete':snapshot['wall']['entries'].pop()
            elif change=='bytes':snapshot['wall']['entries'][1]['content_hash']='changed'
            else:snapshot['wall']['entries'][1]['path']='/unexpected/place/x.jpg'
            moves,deferred,done=candidates(manifest,snapshot)
            self.assertEqual(moves,[]);self.assertEqual(len(deferred),1)

    def test_case_only_rename_uses_temporary_name(self):
        manifest,snapshot=self.setup_rows(['A-AND-B__A-WHITE__001.jpg'])
        moves,_,_=candidates(manifest,snapshot)
        self.assertEqual(len(moves),1);self.assertIn('boldstone-rename-',moves[0]['to_path'])


if __name__=='__main__':unittest.main()
