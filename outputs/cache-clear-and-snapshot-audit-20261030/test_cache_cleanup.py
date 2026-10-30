from pathlib import Path
from unittest import mock
from types import SimpleNamespace
import base64
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
import cache_cleanup as c


class CacheSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name).resolve()
        self.cache=self.root/'cache';self.cache.mkdir()
        self.patch=mock.patch.object(c,'CACHE',self.cache);self.patch.start()
        self.path=self.cache/'example.original';self.path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'example'*50)
        sha,dh,ident=c.hashes(self.path)
        self.row={'path':str(self.path),'relative':'example.original','sha256':sha,'dropbox_content_hash':dh,
                  'bytes':self.path.stat().st_size,'identity':ident,'metadata':c.native.metadata(self.path),
                  'atime_ns':self.path.stat().st_atime_ns}
        self.blob={'storage':'dropbox','sha256':sha,'dropbox_content_hash':dh,'bytes':self.row['bytes'],
                   'cloud':{'id':'id:test','revision':'r1'}}
        self.cloud={'id:test':{'id':'id:test','revision':'r1','content_hash':dh,'bytes':self.row['bytes'],'downloadable':True}}

    def tearDown(self):
        self.patch.stop();self.tmp.cleanup()

    def test_valid_verified_candidate(self):
        self.assertIsNone(c.eligible(self.row,self.blob,set(),set(),self.cloud))

    def test_new_active_or_open_path_is_retained(self):
        self.assertIsNotNone(c.eligible(self.row,self.blob,{str(self.path)},set(),self.cloud))
        self.assertIsNotNone(c.eligible(self.row,self.blob,set(),{str(self.path)},self.cloud))

    def test_changed_file_is_retained(self):
        self.path.write_bytes(b'changed')
        self.assertIsNotNone(c.eligible(self.row,self.blob,set(),set(),self.cloud))

    def test_changed_cloud_revision_is_retained(self):
        self.cloud['id:test']['revision']='r2'
        self.assertIsNotNone(c.eligible(self.row,self.blob,set(),set(),self.cloud))

    def test_cloud_identity_and_missing_original_are_checked(self):
        self.assertIsNotNone(c.eligible(self.row,self.blob,set(),set(),{}))
        self.cloud['id:test']['id']='id:different'
        self.assertIsNotNone(c.eligible(self.row,self.blob,set(),set(),self.cloud))

    def test_outside_or_symlink_path_is_retained(self):
        outside=self.root/'outside';outside.write_bytes(self.path.read_bytes())
        row={**self.row,'path':str(outside)}
        self.assertIsNotNone(c.eligible(row,self.blob,set(),set(),self.cloud))
        self.path.unlink();self.path.symlink_to(outside)
        self.assertIsNotNone(c.eligible(self.row,self.blob,set(),set(),self.cloud))

    def test_retirement_requires_explicit_apply(self):
        with self.assertRaisesRegex(ValueError,'--apply'):c.retire()
        self.assertTrue(self.path.is_file())

    def test_archive_content_is_hash_verified(self):
        p=self.root/'images.zip'
        data=self.path.read_bytes()
        with zipfile.ZipFile(p,'w') as z:z.writestr('image',data)
        blob={**self.blob,'storage':'existing-archive','archive':str(p),'member':'image'}
        self.assertEqual(c.data_for(blob,{}),data)
        blob['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'differs'):c.data_for(blob,{})

    def test_restore_refuses_existing_destination(self):
        m={'records':[self.row],'blobs':{self.row['sha256']:self.blob}}
        with mock.patch.object(c,'manifest',return_value=m):
            with self.assertRaises(FileExistsError):c.restore(str(self.path),apply=True)

    def test_restore_preserves_bytes_and_metadata(self):
        data=self.path.read_bytes();dest=self.cache/'restored.original'
        m={'records':[self.row],'blobs':{self.row['sha256']:self.blob}}
        with mock.patch.object(c,'manifest',return_value=m),mock.patch.object(c,'write_restored',side_effect=lambda b,m,p:p.write_bytes(data)):
            c.restore(str(self.path),dest,True)
        self.assertEqual(dest.read_bytes(),data)
        self.assertEqual(c.native.metadata(dest),self.row['metadata'])

    def test_manifest_tampering_rejected(self):
        path=self.root/'cache-manifest.json';path.write_text('{}')
        (self.root/'cache-manifest.sha256.json').write_text(json.dumps({'sha256':'0'*64}))
        with mock.patch.object(c,'HERE',self.root):
            with self.assertRaisesRegex(ValueError,'changed'):c.manifest()

    def test_cloud_restore_streams_and_checks_exact_bytes(self):
        data=self.path.read_bytes()
        response=mock.Mock()
        response.iter_content.return_value=iter([data[:10],data[10:]])
        meta=SimpleNamespace(id='id:test',rev='r1',content_hash=self.row['dropbox_content_hash'],size=len(data))
        client=mock.Mock();client.files_download.return_value=(meta,response)
        dest=self.cache/'streamed'
        c.write_restored(self.blob,{},dest,client)
        self.assertEqual(dest.read_bytes(),data)
        response.iter_content.assert_called_once();response.close.assert_called_once()
        response.iter_content.return_value=iter([b'changed'])
        with self.assertRaisesRegex(ValueError,'differs'):c.write_restored(self.blob,{},self.cache/'corrupt',client)

    def test_extended_attributes_restore_exactly(self):
        key=b'com.boldstone.cleanup-test';value=b'metadata to preserve'
        c.native.native(c.native.LIB.setxattr,os.fsencode(self.path),key,value,len(value),0,1)
        row={**self.row,'metadata':c.native.metadata(self.path),'xattrs_base64':{os.fsdecode(key):base64.b64encode(value).decode('ascii')}}
        data=self.path.read_bytes();dest=self.cache/'with-attributes'
        m={'records':[row],'blobs':{row['sha256']:self.blob}}
        with mock.patch.object(c,'manifest',return_value=m),mock.patch.object(c,'write_restored',side_effect=lambda b,m,p:p.write_bytes(data)):
            c.restore(str(self.path),dest,True)
        self.assertEqual(c.native.metadata(dest),row['metadata'])


if __name__=='__main__':unittest.main()
