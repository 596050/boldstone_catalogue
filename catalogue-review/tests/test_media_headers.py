"""Image metadata must not invent sizes or let a damaged cache prevent startup."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import MediaCache, dimensions, enrich


class MediaHeaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'image'

    def test_complete_encoded_headers_match_real_images(self):
        from PIL import Image
        for fmt, options in [('PNG', {}), ('JPEG', {}), ('GIF', {}), ('BMP', {}),
                             ('TIFF', {}), ('WEBP', {}), ('WEBP', {'lossless': True})]:
            with self.subTest(format=fmt, options=options):
                Image.new('RGB', (51, 37), 'white').save(self.path, format=fmt, **options)
                self.assertEqual(dimensions(self.path), [51, 37])

    def test_truncated_headers_never_become_small_valid_dimensions(self):
        for raw in (b'RIFF' + bytes(4) + b'WEBPVP8X',
                    b'RIFF' + bytes(4) + b'WEBPVP8L' + bytes(4) + b'\x2f\x00',
                    b'\xff\xd8\xff\xc0\x00\x11\x08\x00',
                    b'\x89PNG\r\n\x1a\n' + bytes(4) + b'IHDR' + bytes(8),
                    b'GIF89a' + bytes(4)):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                self.assertIsNone(dimensions(self.path))

    def test_bitmap_core_header_uses_unsigned_short_dimensions(self):
        self.path.write_bytes(b'BM' + bytes(12) + struct.pack('<IHHHH', 12, 320, 200, 1, 24))
        self.assertEqual(dimensions(self.path), [320, 200])

    def test_top_down_bitmap_height_is_valid_but_negative_width_is_not(self):
        self.path.write_bytes(b'BM' + bytes(12) + struct.pack('<Iii', 40, 320, -200))
        self.assertEqual(dimensions(self.path), [320, 200])
        self.path.write_bytes(b'BM' + bytes(12) + struct.pack('<Iii', 40, -320, 200))
        self.assertIsNone(dimensions(self.path))

    def test_invalid_cache_shapes_are_rebuilt(self):
        self.path.write_bytes(b'cached source')
        cache_path = self.root / 'media-metadata-v1.json'
        for raw in ('[]', 'null', '{"bad": null}', '{"bad": 42}'):
            with self.subTest(raw=raw):
                cache_path.write_text(raw)
                cache = MediaCache(self.root)
                self.assertEqual(cache.inspect(self.path, hashes=True)['bytes'], self.path.stat().st_size)
                cache.flush()
                self.assertIsInstance(json.loads(cache_path.read_text()), dict)

    def test_header_upgrade_rechecks_dimensions_without_rehashing_unchanged_bytes(self):
        self.path.write_bytes(b'GIF89a' + struct.pack('<HH', 51, 37))
        cache = MediaCache(self.root)
        current = cache.inspect(self.path, hashes=True)
        legacy = deepcopy(current)
        legacy.pop('header_version')
        legacy['dimensions'] = [0, 0]
        cache.entries[str(self.path)] = legacy
        with patch('media.hashlib.sha256', side_effect=AssertionError('Unchanged bytes need no new hash')):
            upgraded = cache.inspect(self.path, hashes=True)
        self.assertEqual(upgraded['dimensions'], [51, 37])
        self.assertEqual(upgraded['sha256'], current['sha256'])

    def test_failed_cache_replacement_preserves_previous_snapshot_and_cleans_temp(self):
        cache = MediaCache(self.root)
        cache.entries = {'old': {}}
        cache.flush()
        before = cache.path.read_bytes()
        cache.entries = {'new': {}}
        with patch('media.os.replace', side_effect=OSError('full disk')):
            with self.assertRaises(OSError):
                cache.flush()
        self.assertEqual(cache.path.read_bytes(), before)
        self.assertEqual(list(self.root.glob('.media-metadata-*.tmp')), [])

    def test_invalid_dimensions_in_current_cache_are_rechecked(self):
        self.path.write_bytes(b'GIF89a' + struct.pack('<HH', 51, 37))
        cache = MediaCache(self.root)
        original = cache.inspect(self.path, hashes=True)
        for invalid in ([0, 0], [True, 37], '51x37', [51], 51):
            with self.subTest(invalid=invalid):
                cache.entries[str(self.path)] = {**original, 'dimensions': invalid}
                self.assertEqual(cache.inspect(self.path, hashes=True)['dimensions'], [51, 37])

    def test_invalid_retained_dimensions_are_not_promoted_to_known_metadata(self):
        for invalid in ([0, 100], [True, 100], '100x100', 100):
            with self.subTest(invalid=invalid):
                asset = {'source': 'Dropbox', 'role': 'individual', 'original': {
                    'dropbox_content_hash': 'a' * 64, 'dimensions_hash': 'a' * 64,
                    'recorded_dimensions': invalid}}
                cat = SimpleNamespace(assets={'id:photo': asset}, paths={}, source={})
                enrich(cat, self.root)
                self.assertIsNone(asset['original']['dimensions'])
                self.assertEqual(cat.source['dedupe']['original_dimensions_known'], 0)

    def test_evicted_cached_copy_does_not_remove_source_or_break_catalogue_loading(self):
        asset = {'source': 'Dropbox', 'role': 'individual', 'original': {
            'dropbox_content_hash': 'a' * 64}, 'local_preview': True}
        cat = SimpleNamespace(assets={'id:photo': asset},
                              paths={'id:photo': (self.path, 'cached source')}, source={})
        enrich(cat, self.root)
        self.assertIn('id:photo', cat.assets)
        self.assertNotIn('id:photo', cat.paths)
        self.assertFalse(asset['local_preview'])
        self.assertFalse(asset['original']['locally_verified'])

    def test_partial_hash_cache_does_not_certify_preview_or_crash_loading(self):
        self.path.write_bytes(b'GIF89a' + struct.pack('<HH', 51, 37))
        for missing in ('sha256', 'dropbox_content_hash'):
            with self.subTest(missing=missing):
                cache = MediaCache(self.root)
                record = cache.inspect(self.path, hashes=True)
                native_hash = record['dropbox_content_hash']
                record.pop(missing)
                cache.flush()
                asset = {'source': 'Dropbox', 'role': 'individual', 'original': {
                    'dropbox_content_hash': native_hash}, 'local_preview': True}
                cat = SimpleNamespace(assets={'id:photo': asset},
                    paths={'id:photo': (self.path, 'cached preview')}, source={})
                enrich(cat, self.root)
                self.assertFalse(asset['original']['locally_verified'])
                self.assertIsNone(asset['original']['dimensions'])

    def test_replacement_during_inspection_cannot_pair_old_dimensions_with_new_hash(self):
        original = b'GIF89a' + struct.pack('<HH', 51, 37)
        replacement = b'GIF89a' + struct.pack('<HH', 11, 13)
        self.path.write_bytes(original)
        cache = MediaCache(self.root)
        def replaced(path):
            result = dimensions(path)
            self.path.write_bytes(replacement)
            return result
        with patch('media.dimensions', side_effect=replaced):
            with self.assertRaisesRegex(OSError, 'changed during metadata inspection'):
                cache.inspect(self.path, hashes=True)
        self.assertNotIn(str(self.path), cache.entries)
        current = cache.inspect(self.path, hashes=True)
        self.assertEqual(current['dimensions'], [11, 13])
