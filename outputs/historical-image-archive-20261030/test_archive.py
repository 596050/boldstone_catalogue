from pathlib import Path
from unittest import TestCase, main, mock
import hashlib
import json
import os
import tempfile
import zipfile
import archive_images as a
import viewer


class ArchiveTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve();self.here=self.root/'archive';self.here.mkdir()
        self.runtime=self.root/'runtime';(self.runtime/'native-jobs').mkdir(parents=True)
        self.patches=[mock.patch.object(a,'ROOT',self.root),mock.patch.object(a,'HERE',self.here),
                      mock.patch.object(a,'RUNTIME',self.runtime)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def row(self,name='image.jpg',data=b'\xff\xd8\xff'+b'abcd'*800):
        p=self.root/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(data)
        s=p.stat();sha,dh,identity=a.hashes(p)
        return {'path':name,'bytes':len(data),'sha256':sha,'dropbox_content_hash':dh,'identity':identity,
                'metadata':a.native.metadata(p),'atime_ns':s.st_atime_ns}

    def setup_archive(self,rows):
        blobs={r['sha256']:{'sha256':r['sha256'],'bytes':r['bytes'],'dropbox_content_hash':r['dropbox_content_hash'],
                           'source_path':r['path'],'storage':'archive','member':'images/'+r['sha256']} for r in rows}
        m={'records':rows,'blobs':blobs,'archive':'historical-images.zip','protected_paths':[]}
        a.write(self.here/'manifest.json',m)
        a.write(self.here/'manifest.sha256.json',{'sha256':a.native.digest(self.here/'manifest.json')})
        a.build_archive();a.verify_archive();return m

    def test_block_hash_matches_dropbox_boundary_and_empty(self):
        for n in (0,4194304,4194304+9):
            p=self.root/str(n);p.write_bytes(b'x'*n)
            sha,dh,_=a.hashes(p)
            data=p.read_bytes()
            expected=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,n,4194304))).hexdigest()
            self.assertEqual(dh,expected);self.assertEqual(sha,hashlib.sha256(data).hexdigest())

    def test_hash_rejects_symlink_and_hard_link(self):
        p=self.root/'real';p.write_bytes(b'real');link=self.root/'link';link.symlink_to(p)
        with self.assertRaises(ValueError):a.hashes(link)
        os.link(p,self.root/'hard')
        with self.assertRaises(ValueError):a.hashes(p)

    def test_duplicate_images_have_one_archive_member_and_exact_restore(self):
        r=self.row('a.jpg');q=self.row('nested/b.jpg');m=self.setup_archive([r,q])
        with zipfile.ZipFile(self.here/m['archive']) as z:self.assertEqual(len(z.namelist()),2)
        dest=self.root/'restored/image.jpg';a.restore(r,dest,m)
        self.assertEqual(dest.read_bytes(),(self.root/r['path']).read_bytes())
        self.assertEqual(a.native.metadata(dest),r['metadata'])

    def test_restore_wont_overwrite(self):
        r=self.row();m=self.setup_archive([r]);dest=self.root/'keep';dest.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):a.restore(r,dest,m)
        self.assertEqual(dest.read_bytes(),b'keep')

    def test_wrong_archive_content_is_rejected(self):
        r=self.row();m=self.setup_archive([r]);b=m['blobs'][r['sha256']]
        b['sha256']='0'*64
        with self.assertRaises(ValueError):a.load_image(m,b)

    def test_manifest_modification_is_rejected(self):
        r=self.row();self.setup_archive([r]);p=self.here/'manifest.json';p.write_text(p.read_text()+' ')
        with self.assertRaises(ValueError):a.manifest()

    def test_retirement_requires_authorisation_switch(self):
        with self.assertRaises(ValueError):a.retire(False)

    def test_retirement_skips_changed_and_newly_referenced_images(self):
        r=self.row('eligible.jpg',b'first');s=self.row('active.jpg',b'active');t=self.row('changed.jpg',b'old')
        self.setup_archive([r,s,t]);a.write(self.here/'access-verification.json',{'status':'PASS'})
        (self.root/t['path']).write_bytes(b'new')
        with mock.patch.object(a,'cloud_inventory',return_value={'files':[]}),\
             mock.patch.object(a,'fresh_dependencies',return_value={str(self.root/s['path'])}),\
             mock.patch.object(a,'open_files',return_value=set()):
            a.retire(True)
        self.assertFalse((self.root/r['path']).exists())
        self.assertTrue((self.root/s['path']).exists());self.assertEqual((self.root/t['path']).read_bytes(),b'new')
        self.assertEqual(a.read(self.here/'retirement-complete.json')['files'],1)

    def test_cloud_revision_mismatch_preserves_local_copy(self):
        r=self.row();m=self.setup_archive([r]);b=m['blobs'][r['sha256']]
        b.update(storage='dropbox',cloud={'id':'id:test','revision':'old'})
        a.write(self.here/'access-verification.json',{'status':'PASS'})
        current={'files':[{'id':'id:test','revision':'new','content_hash':r['dropbox_content_hash'],'bytes':r['bytes'],'downloadable':True}]}
        with mock.patch.object(a,'manifest',return_value=m),mock.patch.object(a,'cloud_inventory',return_value=current),\
             mock.patch.object(a,'fresh_dependencies',return_value=set()),mock.patch.object(a,'open_files',return_value=set()):
            a.retire(True)
        self.assertTrue((self.root/r['path']).exists())
        self.assertEqual(a.read(self.here/'retirement-complete.json')['files'],0)

    def test_load_rejects_wrong_dropbox_id_without_consuming_bytes(self):
        r=self.row();m=self.setup_archive([r]);b=m['blobs'][r['sha256']]
        b.update(storage='dropbox',cloud={'id':'id:expected','revision':'rev1'})
        metadata=mock.Mock(id='id:wrong',rev='rev1',content_hash=r['dropbox_content_hash'],size=r['bytes'])
        response=mock.Mock();client=mock.Mock();client.files_download.return_value=(metadata,response)
        with self.assertRaises(ValueError):a.load_image(m,b,client)
        response.close.assert_called_once()

    def test_viewer_detects_original_image_format(self):
        self.assertEqual(viewer.image_type(b'\xff\xd8\xffsomething'),'image/jpeg')
        self.assertEqual(viewer.image_type(b'\x89PNG\r\n'),'image/png')
        self.assertEqual(viewer.image_type(b'not image'),'application/octet-stream')


if __name__=='__main__':main()
