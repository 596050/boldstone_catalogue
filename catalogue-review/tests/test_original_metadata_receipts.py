import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import verified_original_metadata
from media import enrich
from types import SimpleNamespace


class OriginalMetadataReceiptTests(unittest.TestCase):
    def test_catalogue_reads_receipt_without_claiming_download_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'originals').mkdir()
            h='a'*64
            (root/'originals'/(h+'.json')).write_text(json.dumps({'file_id':'id:test',
                'dropbox_content_hash':h,'sha256':'b'*64,'bytes':1234,
                'dimensions':[3872,2592],'checked_utc':'2026-10-30T09:00:00Z'}))
            def catalogue(hash_value):
                return SimpleNamespace(assets={'id:test':{'source':'Dropbox','role':'individual',
                    'inventory_status':'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',
                    'original':{'bytes':1234,'dropbox_content_hash':hash_value}}},paths={},source={})
            cat=catalogue(h); enrich(cat,root)
            self.assertEqual(cat.assets['id:test']['original']['dimensions'],[3872,2592])
            self.assertFalse(cat.assets['id:test']['original']['locally_verified'])
            self.assertNotIn('id:test',cat.paths)
            changed=catalogue('c'*64); enrich(changed,root)
            self.assertIsNone(changed.assets['id:test']['original']['dimensions'])

    def test_dimensions_survive_cache_eviction_but_are_bound_to_exact_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'originals').mkdir()
            h='a'*64; receipt={'file_id':'id:test','dropbox_content_hash':h,'sha256':'b'*64,
                              'bytes':1234,'dimensions':[3872,2592],'checked_utc':'2026-10-30T09:00:00Z'}
            p=root/'originals'/(h+'.json');p.write_text(json.dumps(receipt))
            self.assertEqual(verified_original_metadata(root,h,1234)['dimensions'],[3872,2592])
            self.assertIsNone(verified_original_metadata(root,h,1235))
            self.assertIsNone(verified_original_metadata(root,'c'*64,1234))
            for changes in ({'dropbox_content_hash':'c'*64},{'sha256':''},{'dimensions':[True,200]},
                            {'dimensions':[0,100]},{'dimensions':[1]},{'checked_utc':''},{'bytes':None}):
                p.write_text(json.dumps({**receipt,**changes}))
                self.assertIsNone(verified_original_metadata(root,h,1234),changes)
            for invalid in ('{', 'null', '[]'):
                p.write_text(invalid)
                self.assertIsNone(verified_original_metadata(root,h,1234))

if __name__=='__main__':unittest.main()
