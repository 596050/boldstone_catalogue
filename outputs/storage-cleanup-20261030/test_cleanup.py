"""Destructive-path tests use only disposable files created by this test."""
from pathlib import Path
import gzip
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
import cleanup as worker
import storage_primitives as native

class CleanupChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cleanup-test-',dir=Path(__file__).parent)
        self.root=Path(self.temp.name)
        worker.ROOT=self.root;worker.HERE=self.root/'receipts';worker.HERE.mkdir()
        worker.AUDIT=self.root/'audit';worker.AUDIT.mkdir()
        worker.PROTECTED=set();worker.OPENED=set()

    def tearDown(self):self.temp.cleanup()

    def write(self,name,value):
        (worker.AUDIT/name).write_text(json.dumps(value))

    def test_cow_preserves_metadata_and_independent_edits(self):
        a,b,tmp=(self.root/x for x in ('keeper','target','clone'))
        payload=b'Original independent file\n'*40000
        a.write_bytes(payload);b.write_bytes(payload)
        os.chmod(b,0o640);os.utime(b,ns=(1730000000000000000,1730000000123456789))
        native.creation_time(a,1710000000123456789);native.creation_time(b,1720000000987654321)
        native.native(native.LIB.setxattr,os.fsencode(a),b'com.boldstone.test',b'keeper',6,0,1)
        native.native(native.LIB.setxattr,os.fsencode(b),b'com.boldstone.test',b'target',6,0,1)
        subprocess.run(['chmod','+a','user:tprice allow read',str(b)],check=True,capture_output=True)
        metadata=native.metadata(b);sha=native.digest(b)
        native.clone_with_metadata(a,b,tmp)
        self.assertEqual(native.metadata(tmp),metadata);self.assertEqual(native.digest(tmp),sha)
        native.swap(tmp,b)
        self.assertEqual(native.metadata(b),metadata)
        with b.open('r+b') as stream:stream.write(b'Independent write')
        self.assertEqual(native.digest(a),sha);self.assertEqual(native.digest(tmp),sha)
        self.assertNotEqual(native.digest(b),sha)

    def test_existing_archive_verified_before_retirement(self):
        folder=self.root/'export';folder.mkdir();p=folder/'data.txt';p.write_bytes(b'important data')
        archive=self.root/'export.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:z.write(p,'data.txt')
        self.write('verified-test-export-candidates.json',{'results':[{'status':'PASS_BYTE_IDENTICAL_ARCHIVE','directory':'export','archive':'export.zip','allocated_bytes':p.stat().st_blocks*512}]})
        result=worker.archive_exports();self.assertEqual(result['files_retired'],1);self.assertFalse(folder.exists())
        with zipfile.ZipFile(archive) as z:self.assertEqual(z.read('data.txt'),b'important data')

    def test_changed_archive_refuses_to_remove_original(self):
        folder=self.root/'export';folder.mkdir();p=folder/'data.txt';p.write_bytes(b'important data')
        archive=self.root/'export.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('data.txt',b'wrong data')
        self.write('verified-test-export-candidates.json',{'results':[{'status':'PASS_BYTE_IDENTICAL_ARCHIVE','directory':'export','archive':'export.zip','allocated_bytes':1}]})
        with self.assertRaisesRegex(RuntimeError,'bytes differ'):worker.archive_exports()
        self.assertEqual(p.read_bytes(),b'important data')

    def test_database_restoration_before_retirement(self):
        p=self.root/'history.sqlite3';data=b'Old review record\n'*5000;p.write_bytes(data)
        sha=native.digest(p);meta=native.metadata(p)
        self.write('verified-test-export-candidates.json',{'results':[]})
        self.write('database-archive-candidates.json',[{'path':'history.sqlite3','sha256':sha}])
        result=worker.archive_databases();self.assertEqual(result['files'],1);self.assertFalse(p.exists())
        info=worker.load(self.root/'history.sqlite3.gz.restore.json')
        worker.restore_to(self.root/'history.sqlite3.gz',p,info)
        self.assertEqual(p.read_bytes(),data);self.assertEqual(native.metadata(p),meta)

    def test_protected_and_symlink_paths_are_rejected(self):
        p=self.root/'live';p.write_bytes(b'protected');worker.PROTECTED={str(p)}
        with self.assertRaisesRegex(RuntimeError,'Protected'):worker.guarded(p)
        link=self.root/'alias';link.symlink_to(p)
        with self.assertRaisesRegex(RuntimeError,'regular in-scope'):worker.guarded(link)

    def test_dedup_keeps_paths_and_contents(self):
        files=[];data=b'Identical local evidence\n'*5000
        for name in ('keeper.png','copy.png'):
            p=self.root/name;p.write_bytes(data);files.append({'path':name,'bytes':len(data)})
        with gzip.open(worker.AUDIT/'exact-duplicates.json.gz','wt') as stream:
            json.dump([{'sha256':hashlib.sha256(data).hexdigest(),'files':files}],stream)
        result=worker.deduplicate();self.assertEqual(result['cloned_files_this_run'],1)
        for name in ('keeper.png','copy.png'):self.assertEqual((self.root/name).read_bytes(),data)

    def test_metadata_mismatch_retains_original_and_continues(self):
        files=[];data=b'Important evidence\n'*5000
        for name in ('keeper.png','copy.png'):
            p=self.root/name;p.write_bytes(data);files.append({'path':name,'bytes':len(data)})
        original_meta=native.metadata(self.root/'copy.png')
        with gzip.open(worker.AUDIT/'exact-duplicates.json.gz','wt') as stream:
            json.dump([{'sha256':hashlib.sha256(data).hexdigest(),'files':files}],stream)
        original_clone=native.clone_with_metadata
        def altered_clone(keeper,destination,temporary):
            original_clone(keeper,destination,temporary)
            native.native(native.LIB.setxattr,os.fsencode(temporary),b'com.boldstone.unexpected',b'value',5,0,1)
        native.clone_with_metadata=altered_clone
        try:
            result=worker.deduplicate()
            self.assertEqual(result['cloned_files_this_run'],0)
            self.assertEqual(len(result['skipped']),1)
            self.assertEqual((self.root/'copy.png').read_bytes(),data)
            self.assertEqual(native.metadata(self.root/'copy.png'),original_meta)
        finally:native.clone_with_metadata=original_clone

if __name__=='__main__':unittest.main()
