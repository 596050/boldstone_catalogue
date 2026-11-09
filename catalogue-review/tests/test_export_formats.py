"""Cached originals keep their actual formats even when their cache suffix does not."""
import csv
import hashlib
from io import BytesIO
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exports import create_export, image_type, image_type_from_header
import test_review


class ExportFormatTests(unittest.TestCase):
    setUp = test_review.ReviewTests.setUp
    tearDown = test_review.ReviewTests.tearDown
    save = test_review.ReviewTests.save

    def encoded(self, format):
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (13, 11), 'white').save(stream, format=format)
        return stream.getvalue()

    def test_all_supported_original_formats_are_identified_from_bytes(self):
        for format, mime, extension in [('JPEG', 'image/jpeg', '.jpg'),
                                       ('PNG', 'image/png', '.png'),
                                       ('GIF', 'image/gif', '.gif'),
                                       ('WEBP', 'image/webp', '.webp'),
                                       ('TIFF', 'image/tiff', '.tiff'),
                                       ('BMP', 'image/bmp', '.bmp'),
                                       ('AVIF', 'image/avif', '.avif')]:
            with self.subTest(format=format):
                self.image.write_bytes(self.encoded(format))
                self.assertEqual(image_type(self.image), (mime, extension))

    def test_avif_compatible_brands_are_read_beyond_the_old_sixteen_byte_probe(self):
        header = struct.pack('>I4s4sI4s4s', 24, b'ftyp', b'mif1', 0, b'mif1', b'avif')
        self.image.write_bytes(header)
        self.assertEqual(image_type(self.image), ('image/avif', '.avif'))

    def test_sequence_and_extended_file_type_boxes_are_recognized(self):
        for header in (struct.pack('>I4s4sI', 16, b'ftyp', b'avis', 0),
                       struct.pack('>I4sQ4sI4s', 1, b'ftyp', 28, b'mif1', 0, b'avif')):
            with self.subTest(header=header):
                self.assertEqual(image_type_from_header(header), ('image/avif', '.avif'))

    def test_an_avif_word_outside_the_file_type_box_is_not_an_avif_brand(self):
        movie = struct.pack('>I4s4sI', 16, b'ftyp', b'isom', 0) + b'\x00\x00\x00\x0cmdatavif'
        for data in (movie, b'not an image avif', b'\x89PNG invalid',
                     struct.pack('>I4s4s', 12, b'ftyp', b'avif')):
            with self.subTest(data=data):
                self.assertEqual(image_type_from_header(data), ('application/octet-stream', '.bin'))

    def test_bitmap_and_avif_exports_keep_original_bytes_and_matching_file_extensions(self):
        self.save('product', 'A', '', {'decision': 'include'})
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['advertising']})
        for format, extension in [('BMP', '.bmp'), ('AVIF', '.avif')]:
            with self.subTest(format=format):
                source = self.encoded(format)
                self.image.write_bytes(source)
                result = create_export(self.cat, self.store, include_media=True)
                root = Path(result['path'])
                with (root / 'image-decisions-and-tags.csv').open(encoding='utf-8-sig') as stream:
                    row = next(r for r in csv.DictReader(stream) if r['asset_id'] == 'image')
                output = root / row['media_file']
                self.assertEqual(output.suffix, extension)
                self.assertEqual(output.read_bytes(), source)
                self.assertEqual(row['media_sha256'], hashlib.sha256(source).hexdigest())
                self.assertEqual(self.image.read_bytes(), source)

    def verified_fixture(self, data):
        self.image.write_bytes(data)
        self.cat.assets['image']['original'] = {'sha256': hashlib.sha256(data).hexdigest(),
            'dropbox_content_hash': hashlib.sha256(hashlib.sha256(data).digest()).hexdigest(),
            'bytes': len(data), 'locally_verified': True}
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['advertising']})

    def exported_image(self):
        result = create_export(self.cat, self.store, include_media=True)
        root = Path(result['path'])
        with (root / 'image-decisions-and-tags.csv').open(encoding='utf-8-sig') as stream:
            row = next(r for r in csv.DictReader(stream) if r['asset_id'] == 'image')
        return root, row

    def test_changed_cached_bytes_are_withheld_instead_of_exporting_unreviewed_media(self):
        self.verified_fixture(self.encoded('PNG'))
        self.image.write_bytes(self.encoded('BMP'))
        root, row = self.exported_image()
        self.assertEqual(row['media_file'], '')
        self.assertEqual(row['media_sha256'], '')
        self.assertIn('cached bytes changed', row['export_status'])
        self.assertEqual(row['source_url'], self.cat.assets['image']['url'])
        self.assertEqual(list((root / 'media').rglob('*.*')), [])

    def test_unchanged_verified_bytes_are_copied_without_modifying_the_source(self):
        source = self.encoded('PNG')
        self.verified_fixture(source)
        root, row = self.exported_image()
        self.assertEqual((root / row['media_file']).read_bytes(), source)
        self.assertEqual(self.image.read_bytes(), source)

    def test_distinct_preview_reference_keeps_its_own_bytes_and_hash(self):
        from PIL import Image
        source = self.encoded('PNG')
        self.verified_fixture(source)
        preview = self.root / 'preview.png'
        Image.new('RGB', (3, 2), 'white').save(preview, format='PNG')
        derivative = preview.read_bytes()
        self.assertNotEqual(derivative, source)
        self.cat.paths['image'] = (preview, 'cached preview')
        root, row = self.exported_image()
        self.assertTrue(row['media_file'].startswith('preview-references/advertising/'))
        self.assertEqual((root / row['media_file']).read_bytes(), derivative)
        self.assertEqual(row['media_sha256'], hashlib.sha256(derivative).hexdigest())
        self.assertEqual(row['export_status'], 'Preview reference only')
        self.assertEqual(self.image.read_bytes(), source)


if __name__ == '__main__':
    unittest.main()
