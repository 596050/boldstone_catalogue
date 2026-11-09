"""Fragmented image signatures keep streaming identity checks intact."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fetch_original import OriginalError
from image_delivery_worker import mime_type, stream_original


def content_hash(data):
    return hashlib.sha256(b''.join(hashlib.sha256(data[offset:offset + 4 * 1024 * 1024]).digest()
        for offset in range(0, len(data), 4 * 1024 * 1024))).hexdigest()


class FragmentedFormatTests(unittest.TestCase):
    def fixture(self, data, chunks):
        spec = {'id': 'id:known', 'hash': content_hash(data), 'bytes': len(data)}
        metadata = SimpleNamespace(id=spec['id'], content_hash=spec['hash'], size=spec['bytes'],
                                   path_display='/BOLDSTONE MASTER/Products/image')
        response = SimpleNamespace(closed=False, iter_content=lambda chunk_size: iter(chunks))
        response.close = lambda: setattr(response, 'closed', True)
        return spec, SimpleNamespace(files_download=lambda file_id: (metadata, response)), response

    def test_one_byte_jpeg_chunks_and_empty_keepalives_stream_exactly_once(self):
        data = b'\xff\xd8\xff' + b'a' * 8192
        spec, client, response = self.fixture(data, [b'', *(data[i:i+1] for i in range(len(data)))])
        output = BytesIO()
        stream_original(client, spec, '/BOLDSTONE MASTER', output)
        header, body = output.getvalue().split(b'\n', 1)
        self.assertEqual(json.loads(header), {'mime': 'image/jpeg', 'bytes': len(data)})
        self.assertEqual(body, data)
        self.assertTrue(response.closed)

    def test_split_compatible_brand_avif_retains_its_original_bytes(self):
        from PIL import Image
        encoded = BytesIO()
        Image.new('RGB', (13, 11), 'white').save(encoded, format='AVIF')
        # The existing compatible avif brand remains, with a generic major brand.
        data = encoded.getvalue()
        data = data[:8] + b'mif1' + data[12:]
        spec, client, response = self.fixture(data, [data[i:i+3] for i in range(0, len(data), 3)])
        output = BytesIO()
        stream_original(client, spec, '/BOLDSTONE MASTER', output)
        header, body = output.getvalue().split(b'\n', 1)
        self.assertEqual(json.loads(header)['mime'], 'image/avif')
        self.assertEqual(body, data)
        self.assertTrue(response.closed)

    def test_corrupt_fragmented_payload_never_completes_a_verified_original(self):
        data = b'\xff\xd8\xff' + b'a' * 8192
        damaged = data[:-1] + b'b'
        spec, client, response = self.fixture(data, [damaged[i:i+7] for i in range(0, len(damaged), 7)])
        output = BytesIO()
        with self.assertRaises(OriginalError):
            stream_original(client, spec, '/BOLDSTONE MASTER', output)
        body = output.getvalue().split(b'\n', 1)[1]
        self.assertLess(len(body), len(data))
        self.assertTrue(response.closed)

    def test_tiff_stays_an_export_format_without_becoming_a_browser_stream(self):
        with self.assertRaises(OriginalError):
            mime_type(b'II*\x00' + bytes(16))

    def test_empty_trailing_chunk_cannot_release_corrupt_final_payload_before_verification(self):
        data = b'\xff\xd8\xff' + b'a' * 8192
        damaged = data[:-1] + b'b'
        spec, client, response = self.fixture(data, [damaged[:4096], damaged[4096:], b''])
        output = BytesIO()
        with self.assertRaises(OriginalError):
            stream_original(client, spec, '/BOLDSTONE MASTER', output)
        body = output.getvalue().split(b'\n', 1)[1]
        self.assertLess(len(body), len(data))
        self.assertTrue(response.closed)
