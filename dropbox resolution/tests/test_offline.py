"""Tests shipped with the handover; no network or real Dropbox operations."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'blueprint'))
import bootstrap
from dropbox_hash import BLOCK_SIZE, dropbox_content_hash

class ShortReader(io.BytesIO):
    def read(self,size=-1):
        return super().read(min(size,97) if size>=0 else 97)

class HashTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(dropbox_content_hash(io.BytesIO(b'')),hashlib.sha256(b'').hexdigest())
    def test_small(self):
        expected=hashlib.sha256(hashlib.sha256(b'abc').digest()).hexdigest()
        self.assertEqual(dropbox_content_hash(io.BytesIO(b'abc')),expected)
    def test_exact_block(self):
        data=b'k'*BLOCK_SIZE
        self.assertEqual(dropbox_content_hash(io.BytesIO(data)),hashlib.sha256(hashlib.sha256(data).digest()).hexdigest())
    def test_multiple_blocks(self):
        data=b'a'*BLOCK_SIZE+b'b'*111
        expected=hashlib.sha256(hashlib.sha256(data[:BLOCK_SIZE]).digest()+hashlib.sha256(data[BLOCK_SIZE:]).digest()).hexdigest()
        self.assertEqual(dropbox_content_hash(io.BytesIO(data)),expected)
    def test_short_reads(self):
        data=b'x'*(BLOCK_SIZE+1001)
        self.assertEqual(dropbox_content_hash(ShortReader(data)),dropbox_content_hash(io.BytesIO(data)))

class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index=bootstrap.load_index(ROOT)
    def test_exact_order(self):
        self.assertEqual([r['batch_id'] for r in self.index[:11]],['S01','S02','H01','J001','J002','J003','I00','M001','M002','M003','M004'])
    def test_scope_counts(self):
        expected={'Metadata review':8377,'Duplicate review':2015,'BMP source review':642,'Folder review':423,'Existing JPG QA':13}
        for stream,count in expected.items():
            self.assertEqual(sum(r['item_count'] for r in self.index if r['workstream']==stream),count)
    def test_no_metadata_id_duplicates(self):
        ids=[]
        for r in self.index:
            if r['workstream']=='Metadata review':
                ids += [row['Dropbox file ID'] for row in bootstrap.read_csv(ROOT/r['manifest'])]
        self.assertEqual(len(ids),len(set(ids)))
    def test_no_deletion_or_bmp_id_duplicates(self):
        for stream,key in [('Duplicate review','Delete file ID'),('BMP source review','Original Dropbox ID')]:
            ids=[]
            for r in self.index:
                if r['workstream']==stream:
                    ids += [row[key] for row in bootstrap.read_csv(ROOT/r['manifest'])]
            self.assertEqual(len(ids),len(set(ids)))
    def test_safe_member(self):
        self.assertEqual(bootstrap.safe_member(ROOT,'README.md'),ROOT/'README.md')
        with self.assertRaises(ValueError): bootstrap.safe_member(ROOT,'../escape')
        with self.assertRaises(ValueError): bootstrap.safe_member(ROOT,'/absolute')
    def test_supplemental_row_counts(self):
        self.assertEqual([len(bootstrap.read_csv(ROOT/'supplemental_identity'/n)) for n in ['Historical_29_Inventory_Review_Rows.csv','Historical_18_Identity_Review_Rows.csv','Historical_14_Held_Folder_Rows.csv']],[29,18,14])
    def test_saved_states_not_overwritten(self):
        states={r['batch_id']:r['saved_status'].lower() for r in self.index}
        self.assertIn('partial',states['I00'])
        self.assertIn('partial',states['J001'])
        self.assertTrue('fail' in states['S02'] or 'fail' in self.index[1]['attempt_result'].lower())

class StateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.database=Path(cls.temp.name)/'historical.sqlite3'
        cls.result=bootstrap.init_state(ROOT,cls.database)
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
    def test_import_counts(self):
        counts=self.result['counts']
        for key,value in {'batches':350,'protections':1813,'exclusions':257,'holds':7,'observations':208,'lineage':13,'operations':0,'approvals':0}.items():
            self.assertEqual(counts[key],value)
        self.assertEqual(self.result['remote_calls'],0)
    def test_existing_db_refused(self):
        with self.assertRaises(FileExistsError):bootstrap.init_state(ROOT,self.database)
    def test_append_only_event(self):
        with sqlite3.connect(self.database) as c:
            with self.assertRaises(sqlite3.IntegrityError): c.execute('DELETE FROM events')
    def test_immutable_members(self):
        with sqlite3.connect(self.database) as c:
            with self.assertRaises(sqlite3.IntegrityError): c.execute("UPDATE batch_members SET row_number=999 WHERE batch_id='S01'")
    def test_import_does_not_claim_current_namespace(self):
        with sqlite3.connect(self.database) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM observations WHERE namespace_id IS NOT NULL').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM observations WHERE is_historical=1').fetchone()[0],208)
    def test_foreign_keys_and_integrity(self):
        with sqlite3.connect(self.database) as c:
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])

if __name__=='__main__':unittest.main()
