"""Exercise the shipped Vision worker using generated local images only."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(platform.system() == 'Darwin' and shutil.which('swiftc'),
                     'The local Vision worker requires macOS and Swift')
class SimilarityWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tuple(int(n) for n in platform.mac_ver()[0].split('.')[:1]) < (14,):
            raise unittest.SkipTest('Vision revision 2 requires macOS 14')
        cls.build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.build.cleanup)
        cls.binary = Path(cls.build.name) / 'vision-worker'
        source = Path(__file__).resolve().parents[1] / 'similarity_worker.swift'
        subprocess.run(['swiftc', '-O', str(source), '-o', str(cls.binary)],
                       capture_output=True, check=True, timeout=120)

    def setUp(self):
        from PIL import Image, ImageDraw
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = []
        for index, color in enumerate(['red', 'blue']):
            path = self.root / f'{index}.png'
            image = Image.new('RGB', (256, 256), 'white')
            draw = ImageDraw.Draw(image)
            draw.rectangle((20 + index * 60, 30, 150, 220), fill=color)
            image.save(path)
            self.paths.append(path)
        self.before = [p.read_bytes() for p in self.paths]

    def entry(self, aid, index=None):
        data = self.before[index] if index is not None else aid.encode()
        return {'id': aid, 'key': hashlib.sha256(data).hexdigest(),
                'path': str(self.paths[index]) if index is not None else None}

    def run_worker(self, reverse=False):
        request = {'groups': [[self.entry('A', 0), self.entry('B', 1),
                               self.entry('A-copy', 0), self.entry('missing')],
                              [self.entry('separate', 1)]],
                   'reverse': reverse, 'cache': str(self.root / 'features'),
                   'status': str(self.root / 'status.json'), 'result': str(self.root / 'result.json')}
        path = self.root / 'request.json'
        path.write_text(json.dumps(request))
        subprocess.run([str(self.binary), str(path)], capture_output=True, check=True, timeout=60)
        return json.loads((self.root / 'result.json').read_text())

    def test_orders_nearest_images_within_groups_and_reuses_feature_cache(self):
        first = self.run_worker()
        self.assertEqual(first['order'], ['A', 'A-copy', 'B', 'missing', 'separate'])
        self.assertEqual(first['analysed'], 4)
        self.assertEqual(first['missing_ids'], ['missing'])
        self.assertEqual(first['new_features'], 2)
        second = self.run_worker(reverse=True)
        self.assertEqual(second['order'], ['B', 'A-copy', 'A', 'missing', 'separate'])
        self.assertEqual(second['cached_features'], 4)
        self.assertEqual(second['new_features'], 0)
        self.assertEqual([p.read_bytes() for p in self.paths], self.before)

    def test_missing_and_undecodable_previews_are_retained(self):
        self.paths[0].unlink()
        self.paths[1].write_bytes(b'not an image')
        result = self.run_worker()
        self.assertEqual(result['order'], ['A', 'B', 'A-copy', 'missing', 'separate'])
        self.assertEqual(result['analysed'], 0)
        self.assertEqual(result['total'], 5)
        self.assertEqual(result['missing_ids'], result['order'])


if __name__ == '__main__':
    unittest.main()
