"""Offline rendering, output-preservation and catalogue-input regressions."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
import fetch_and_resize as images
import gen_social as social


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_transparency_is_white_in_padded_and_unpadded_jpegs(self):
        for mode in ('RGBA', 'P'):
            source = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
            if mode == 'P':
                source = source.convert('P')
                source.info['transparency'] = source.getpixel((0, 0))
            for pad in (False, True):
                dest = self.root / f'{mode}-{pad}.jpg'
                images.render(source, {'size': (40, 40), 'pad': pad, 'q': 95}, dest)
                with Image.open(dest) as output:
                    self.assertEqual(output.size, (40, 40) if pad else (20, 20))
                    self.assertTrue(all(channel > 250 for channel in output.getpixel((10, 10))))
        partial = Image.new('RGBA', (20, 20), (255, 0, 0, 128))
        dest = self.root / 'partial.jpg'
        images.render(partial, {'size': (20, 20), 'pad': False, 'q': 95}, dest)
        with Image.open(dest) as output:
            red, green, blue = output.getpixel((10, 10))
            self.assertGreater(red, 250)
            self.assertTrue(120 < green < 135 and 120 < blue < 135)

    def test_failed_render_preserves_existing_output_and_cleans_partial_file(self):
        dest = self.root / '01.jpg'
        dest.write_bytes(b'previous verified image')
        def fail(_image, filename, *_args, **_kwargs):
            Path(filename).write_bytes(b'partial write')
            raise OSError('disk full')
        with patch.object(Image.Image, 'save', fail):
            with self.assertRaisesRegex(OSError, 'disk full'):
                images.render(Image.new('RGB', (2, 2)), {'size': (4, 4), 'pad': True, 'q': 82}, dest)
        self.assertEqual(dest.read_bytes(), b'previous verified image')
        self.assertEqual(list(self.root.iterdir()), [dest])

    def test_cached_slugs_cannot_escape_or_merge_product_folders(self):
        data = self.root / '_data'
        data.mkdir()
        for slugs in (['../outside'], ['/absolute'], [''], ['same', 'same']):
            (data / 'site_images.json').write_text(json.dumps([{'slug': s, 'title': s, 'images': ['unused']} for s in slugs]))
            with patch.object(images, 'DATA', data), patch.object(images, 'ROOT', self.root), patch.object(sys, 'argv', ['fetch_and_resize.py']), patch.object(images.requests, 'get') as request:
                with self.assertRaises(ValueError):
                    images.main()
                request.assert_not_called()

    def test_failed_refresh_preserves_previous_catalogue_cache(self):
        data = self.root / '_data'
        data.mkdir()
        (data / 'products_master.json').write_text(json.dumps([{'title': 'A sculpture'}]))
        cache = data / 'site_images.json'
        cache.write_text('previous verified catalogue')
        with patch.object(images, 'DATA', data), patch.object(sys, 'argv', ['fetch_and_resize.py', '--refresh']), patch.object(images.requests, 'get') as request, patch.object(images.time, 'sleep'):
            request.return_value.status_code = 503
            with self.assertRaisesRegex(RuntimeError, 'cache was preserved'):
                images.main()
        self.assertEqual(cache.read_text(), 'previous verified catalogue')

    def test_social_title_collisions_fail_before_overwriting_captions(self):
        with patch.object(social, 'ROOT', self.root):
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                social.write([{'title': 'Same title!'}, {'title': 'Same title?'}])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fractional_prices_and_long_captions_keep_their_complete_product_link(self):
        self.assertEqual(social.price({'price': '12.50'}), '£12.50')
        self.assertEqual(social.price({'price': '200'}), '£200')
        self.assertEqual(social.price({'price': 'NaN'}), '')
        product = {'title': 'Long sculpture name ' * 12, 'type': 'wall sculpture', 'tags': [], 'desc': 'A sculpture. ' * 50,
                   'variants': [], 'handle': 'long', 'price': '12.50'}
        for platform in ('threads', 'x'):
            body, _ = social.build(product, platform)
            self.assertIn(social.link(product), body)
            length = len(body) - (len(social.link(product)) - 23 if platform == 'x' else 0)
            self.assertLessEqual(length, social.RULES[platform]['limit'])

    def test_wxr_empty_selection_does_not_overwrite_export(self):
        scripts = self.root / 'scripts'
        scripts.mkdir()
        shutil.copy(Path(__file__).resolve().parents[1] / 'build_wxr.py', scripts)
        shutil.copy(Path(__file__).resolve().parents[1] / 'content_paths.py', scripts)
        output = self.root / '_import'
        output.mkdir()
        dest = output / 'boldstone_blog_TEST.xml'
        dest.write_text('previous import')
        result = subprocess.run([sys.executable, str(scripts / 'build_wxr.py'), 'missing'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No articles matched', result.stderr)
        self.assertEqual(dest.read_text(), 'previous import')

    def test_wxr_escapes_folder_names_and_keeps_cdata_text(self):
        scripts = self.root / 'scripts'
        scripts.mkdir()
        shutil.copy(Path(__file__).resolve().parents[1] / 'build_wxr.py', scripts)
        shutil.copy(Path(__file__).resolve().parents[1] / 'content_paths.py', scripts)
        article = self.root / 'blog' / 'shell&wave' / 'article.md'
        article.parent.mkdir(parents=True)
        article.write_text('---\ntitle: "Shell & Wave ]]>"\ntags: ["Sculpture"]\n---\n# A sculpture\n\nA description.')
        result = subprocess.run([sys.executable, str(scripts / 'build_wxr.py')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        tree = ET.parse(self.root / '_import' / 'boldstone_blog_ALL.xml')
        self.assertEqual(tree.findtext('./channel/item/title'), 'Shell & Wave ]]>')
        self.assertTrue(tree.findtext('./channel/item/link').endswith('/shell%26wave'))

    def test_invalid_article_xml_cannot_replace_a_usable_import(self):
        scripts = self.root / 'scripts'
        scripts.mkdir()
        for name in ('build_wxr.py', 'content_paths.py'):
            shutil.copy(Path(__file__).resolve().parents[1] / name, scripts)
        article = self.root / 'blog' / 'sculpture' / 'article.md'
        article.parent.mkdir(parents=True)
        article.write_text('---\ntitle: Sculpture\n---\nInvalid XML control character: \x01')
        dest = self.root / '_import' / 'boldstone_blog_ALL.xml'
        dest.parent.mkdir()
        dest.write_text('previous valid import')
        result = subprocess.run([sys.executable, str(scripts / 'build_wxr.py')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(dest.read_text(), 'previous valid import')


if __name__ == '__main__':
    unittest.main()
