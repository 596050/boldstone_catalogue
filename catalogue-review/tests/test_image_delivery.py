"""Image delivery tests use fake Dropbox streams, temporary caches and HTTP."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from image_delivery import ImageDelivery, ImageUnavailable, ThumbnailCache
from image_delivery_worker import stream_original, thumbnail, load_thumbnail
from fetch_original import OriginalError
from store import Conflict
from test_original_concurrency import OriginalConcurrencyTests, TARGET


def content_hash(data):
    return hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4*1024*1024]).digest()
        for i in range(0, len(data), 4*1024*1024))).hexdigest()


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_cache_is_bounded_and_evicts_least_recently_used(self):
        cache = ThumbnailCache(self.root, limit=20)
        data = b'\xff\xd8\xff' + b'a'*7
        cache.put('first', data)
        cache.put('second', data)
        cache.get('first')
        cache.put('third', data)
        self.assertIsNone(cache.get('second'))
        self.assertEqual(cache.get('first'), data)
        self.assertEqual(sum(p.stat().st_size for p in cache.root.iterdir()), 20)
        self.assertEqual(cache.path('first').stat().st_mode & 0o777, 0o600)

    def test_restart_prunes_cache_and_rejects_invalid_data(self):
        cache = ThumbnailCache(self.root, limit=100)
        for i in range(5): cache.put(str(i), b'\xff\xd8\xff'+b'a'*7)
        cache = ThumbnailCache(self.root, limit=10)
        self.assertEqual(len(list(cache.root.glob('*.jpg'))), 1)
        with self.assertRaises(ImageUnavailable): cache.put('bad', b'<html>')
        cache.path('corrupt').write_bytes(b'bad')
        self.assertIsNone(cache.get('corrupt'))
        self.assertFalse(cache.path('corrupt').exists())

    def test_stable_key_changes_with_content_and_local_revision(self):
        spec = {'id':'id:x','hash':'a'*64,'bytes':100,'local_stamp':['path',100,1,1]}
        self.assertNotEqual(ImageDelivery.key(spec),ImageDelivery.key({**spec,'hash':'b'*64}))
        self.assertNotEqual(ImageDelivery.key(spec),ImageDelivery.key({**spec,'local_stamp':['path',100,2,2]}))

    def test_concurrent_thumbnail_requests_share_one_fetch(self):
        service = ImageDelivery(self.root, self.root)
        entered, release = threading.Event(), threading.Event()
        calls = []
        @contextmanager
        def worker(spec, action):
            calls.append(action); entered.set(); release.wait(2)
            data = b'\xff\xd8\xfftest'
            yield {'mime':'image/jpeg','bytes':len(data)}, BytesIO(data)
        service.worker = worker
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(service.thumbnail, {'id':'id:x','hash':'a'}) for _ in range(8)]
            self.assertTrue(entered.wait(1)); release.set()
            self.assertEqual(len({f.result() for f in futures}), 1)
        self.assertEqual(calls, ['thumbnail'])

    def test_failed_thumbnail_wakes_waiters_and_has_a_bounded_cooldown(self):
        service = ImageDelivery(self.root, self.root)
        @contextmanager
        def worker(*args):
            yield {'mime':'image/jpeg','bytes':20}, BytesIO(b'incomplete')
        service.worker = worker
        with self.assertRaises(ImageUnavailable): service.thumbnail({'id':'id:x'})
        self.assertEqual(service.pending, {})
        with self.assertRaisesRegex(ImageUnavailable, 'temporarily'): service.thumbnail({'id':'id:x'})
        self.assertFalse(list(service.cache.root.glob('*.jpg')))

    def test_thumbnail_has_bounded_dimensions_and_transparency_background(self):
        from PIL import Image
        source = BytesIO()
        Image.new('RGBA',(2200,1800),(255,0,0,0)).save(source,'PNG');source.seek(0)
        result = thumbnail(source)
        with Image.open(BytesIO(result)) as image:
            self.assertLessEqual(image.width,1024); self.assertLessEqual(image.height,768)
            self.assertEqual(image.mode,'RGB')
            self.assertEqual(image.getpixel((0,0)),(255,255,255))

    def test_thumbnail_reads_real_sdk_preview_result_metadata_field(self):
        from datetime import datetime
        from dropbox.files import FileMetadata, PreviewResult
        from PIL import Image
        source=BytesIO();Image.new('RGB',(10,12),'white').save(source,'PNG');data=source.getvalue()
        spec={'id':'id:test','hash':content_hash(data),'bytes':len(data),'native':True}
        metadata=FileMetadata(name='test.png',id=spec['id'],client_modified=datetime(2026,1,1),
            server_modified=datetime(2026,1,1),rev='abc123abc',size=len(data),content_hash=spec['hash'],path_display='/BOLDSTONE MASTER/test.png')
        result=PreviewResult(file_metadata=metadata)
        response=SimpleNamespace(iter_content=lambda chunk_size:iter([data]),close=lambda:None)
        @contextmanager
        def connect(project):
            yield SimpleNamespace(files_get_thumbnail_v2=lambda *a,**k:(result,response)),'/BOLDSTONE MASTER'
        with patch('image_delivery_worker.connection',connect):
            value=load_thumbnail(self.root,spec)
        self.assertTrue(value.startswith(b'\xff\xd8\xff'))


class StreamTests(unittest.TestCase):
    def fixture(self, data, **changes):
        spec = {'id':'id:known','hash':content_hash(data),'bytes':len(data)}
        meta = SimpleNamespace(id=spec['id'],content_hash=spec['hash'],size=len(data),path_display='/BOLDSTONE MASTER/Products/test.jpg')
        for key,value in changes.items():setattr(meta,key,value)
        response = SimpleNamespace(closed=False)
        def close():response.closed=True
        response.close=close
        response.iter_content=lambda chunk_size: (data[i:i+chunk_size] for i in range(0,len(data),chunk_size))
        return spec,SimpleNamespace(files_download=lambda fid:(meta,response)),response

    def test_original_stream_is_exact_across_dropbox_hash_boundaries(self):
        data = b'\xff\xd8\xff'+b'a'*(4*1024*1024+85001)
        spec,client,response=self.fixture(data)
        output=BytesIO();stream_original(client,spec,'/BOLDSTONE MASTER',output)
        head,body=output.getvalue().split(b'\n',1)
        self.assertEqual(json.loads(head),{'mime':'image/jpeg','bytes':len(data)})
        self.assertEqual(body,data);self.assertTrue(response.closed)

    def test_wrong_id_hash_size_or_root_never_sends_headers(self):
        for values in ({'id':'id:other'},{'content_hash':'b'*64},{'size':1},{'path_display':'/Elsewhere/x.jpg'}):
            with self.subTest(values=values):
                spec,client,response=self.fixture(b'\xff\xd8\xffabc',**values);output=BytesIO()
                with self.assertRaises(OriginalError):stream_original(client,spec,'/BOLDSTONE MASTER',output)
                self.assertEqual(output.getvalue(),b'');self.assertTrue(response.closed)

    def test_truncated_or_corrupted_bytes_never_finish_http_body(self):
        data=b'\xff\xd8\xff'+b'a'*200000
        for damage in ('hash','short'):
            spec,client,response=self.fixture(data);output=BytesIO()
            if damage=='hash':
                spec['hash']='c'*64
                old=client.files_download;meta,resp=old('id:known');meta.content_hash=spec['hash']
            else:
                response.iter_content=lambda chunk_size:iter([data[:-1]])
            with self.assertRaises(OriginalError):stream_original(client,spec,'/BOLDSTONE MASTER',output)
            body=output.getvalue().split(b'\n',1)[1]
            self.assertLess(len(body),len(data));self.assertTrue(response.closed)

    def test_browser_unsafe_content_is_rejected(self):
        spec,client,response=self.fixture(b'<svg onload="bad">');output=BytesIO()
        with self.assertRaises(OriginalError):stream_original(client,spec,'/BOLDSTONE MASTER',output)
        self.assertEqual(output.getvalue(),b'')


class ImageHTTPTests(unittest.TestCase):
    setUp = OriginalConcurrencyTests.setUp
    tearDown = OriginalConcurrencyTests.tearDown
    server = OriginalConcurrencyTests.server
    request = OriginalConcurrencyTests.request

    def test_thumbnail_fetch_does_not_block_reads_or_review_saves(self):
        entered,release=threading.Event(),threading.Event()
        def slow(spec):
            entered.set();release.wait(4);return b'\xff\xd8\xffabc'
        self.app.images=SimpleNamespace(thumbnail=slow)
        base=self.server()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(lambda:urllib.request.urlopen(base+'/api/image?id='+TARGET+'&size=thumb').read())
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.request(base,'/api/health',timeout=.5)['status'],'ok')
                result=self.request(base,'/api/reviews',{'kind':'product','product_id':'A','item_id':'','version':0,'data':{'notes':'During image load'}},timeout=.5)
                self.assertEqual(result['data']['notes'],'During image load')
            finally:release.set()
            self.assertEqual(future.result(),b'\xff\xd8\xffabc')

    def test_changed_content_during_fetch_is_not_returned(self):
        def change(spec):
            self.asset['original']['dropbox_content_hash']='b'*64
            return b'\xff\xd8\xffabc'
        self.app.images=SimpleNamespace(thumbnail=change);base=self.server()
        with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(base+'/api/image?id='+TARGET+'&size=thumb')
        self.assertEqual(caught.exception.code,409)

    def test_deleted_and_missing_images_cannot_start_native_requests(self):
        self.asset['source_unavailable']=True
        with self.assertRaises(KeyError):self.app.image_spec(TARGET)
        self.asset.pop('source_unavailable')
        self.store.save('deletion','',TARGET,{'state':'deleted'},0,'source1',{})
        with self.assertRaises(KeyError):self.app.image_spec(TARGET)

    def test_known_native_image_does_not_require_a_local_download(self):
        self.cat.paths={}
        spec=self.app.image_spec(TARGET,self.asset['original']['dropbox_content_hash'])
        self.assertTrue(spec['native']);self.assertIsNone(spec['local'])
        with self.assertRaises(Conflict):self.app.image_spec(TARGET,'outdated')

    def test_stream_has_no_disk_cache_and_never_exposes_a_temporary_url(self):
        data=self.image.read_bytes()
        @contextmanager
        def worker(spec,action):yield {'mime':'image/png','bytes':len(data)},BytesIO(data)
        self.app.images=SimpleNamespace(worker=worker)
        base=self.server()
        with urllib.request.urlopen(base+'/api/image?id='+TARGET) as response:
            self.assertEqual(response.read(),data)
            self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            self.assertIsNone(response.headers.get('Location'))

    def test_metadata_only_original_receipt_does_not_create_local_path(self):
        self.info['path']=None
        with patch('server.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(self.info))) as proc:
            self.app.original(self.body)
        self.assertIn('--metadata-only',proc.call_args.args[0])
        self.assertEqual(self.cat.paths[TARGET][1],'cached source')
        self.assertEqual(self.asset['original']['dimensions'],[1,1])


if __name__=='__main__':unittest.main()
