from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Application
from store import ReviewStore, Conflict

class FieldSaveTests(unittest.TestCase):
    def test_field_save_keeps_cas_audit_and_original_without_image_projection(self):
        with TemporaryDirectory() as tmp:
            app=Application.__new__(Application)
            field={'key':'Brand','value':'','section':'Channel details'}
            app.catalogue=SimpleNamespace(products={'A':{}},source={'register_sha256':'source'},
                                          fields=lambda pid:{'Brand':field})
            app.store=ReviewStore(tmp)
            app.projection=Mock(side_effect=AssertionError('Gallery must not be rebuilt for a text save'))
            request={'kind':'field','product_id':'A','item_id':'Brand','version':0,
                     'data':{'decision':'edit','value':'Boldstone','certainty':'source_claim'}}
            saved=app.save(request)
            self.assertEqual(saved['data']['value'],'Boldstone')
            self.assertEqual(saved['original'],field)
            self.assertEqual(saved['version'],1)
            self.assertEqual(len(app.store.history()),1)
            with self.assertRaises(Conflict):app.save(request)
            with self.assertRaises(ValueError):app.save({**request,'item_id':'Unknown','version':1})
            self.assertEqual(len(app.store.history()),1)
            app.projection.assert_not_called()

if __name__=='__main__':unittest.main()
