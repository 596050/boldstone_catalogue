from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib
import json
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from filename_overlay import apply_filename_overlay


class FilenameOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.root=Path(self.temp.name)
        proof=json.dumps({'status':'PASS'}).encode();(self.root/'verification.json').write_bytes(proof)
        self.value={'namespace_id':'202238505','at':'2026-10-26T20:00:00',
                    'verification':str(self.root/'verification.json'),'verification_sha256':hashlib.sha256(proof).hexdigest(),
                    'files':[{'id':'id:one','path':'/BOLDSTONE MASTER/Products/01 Wall Sculptures/A/A White/a__a-white__001.jpg',
                              'parent_id':'id:folder','rev':'rev1','content_hash':'hash1'}]}
        self.cat=SimpleNamespace(products={},source={},assets={'id:one':{'original':{'dropbox_content_hash':'hash1'},'name':'old.jpg'}})
        self.write()

    def write(self):
        data=json.dumps(self.value).encode();(self.root/'files.json').write_bytes(data)
        (self.root/'filename-readback.json').write_text(json.dumps({'path':str(self.root/'files.json'),'sha256':hashlib.sha256(data).hexdigest()}))

    def tearDown(self):self.temp.cleanup()

    def test_verified_current_name_updates_id_without_changing_bytes(self):
        apply_filename_overlay(self.cat,self.root)
        self.assertEqual(self.cat.assets['id:one']['name'],'a__a-white__001.jpg')
        self.assertEqual(self.cat.assets['id:one']['original'],{'dropbox_content_hash':'hash1'})

    def test_later_inventory_or_organisation_wins(self):
        for kind in ('inventory','organisation'):
            with self.subTest(kind=kind):
                cat=deepcopy(self.cat)
                if kind=='organisation':cat.assets['id:one']['provenance']={'organisation_verified_at':'2026-10-27'}
                apply_filename_overlay(cat,self.root,'2026-10-27' if kind=='inventory' else '')
                self.assertEqual(cat.assets['id:one']['name'],'old.jpg')

    def test_workshop_names_refresh_even_with_later_wall_inventory(self):
        self.value['files'][0]['path']='/BOLDSTONE MASTER/Products/Workshop and Moulding/A/a__001.jpg';self.write()
        apply_filename_overlay(self.cat,self.root,'2026-10-27')
        self.assertEqual(self.cat.assets['id:one']['name'],'a__001.jpg')

    def test_corrupt_manifest_or_verification_not_consumed(self):
        (self.root/'files.json').write_text('{}')
        with self.assertRaises(ValueError):apply_filename_overlay(self.cat,self.root)
        self.write();(self.root/'verification.json').write_text('{"status":"FAIL"}')
        with self.assertRaises(ValueError):apply_filename_overlay(self.cat,self.root)
        self.assertEqual(self.cat.assets['id:one']['name'],'old.jpg')

    def test_changed_bytes_or_unknown_ids_do_not_receive_an_old_path(self):
        self.cat.assets['id:one']['original']['dropbox_content_hash']='new-bytes'
        apply_filename_overlay(self.cat,self.root)
        self.assertEqual(self.cat.assets['id:one']['name'],'old.jpg')

if __name__=='__main__':unittest.main()
