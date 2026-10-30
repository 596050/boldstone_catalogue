from pathlib import Path
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import json
import hashlib

JOB = Path(__file__).resolve().parent
names = ['17.19.02 (1)', '17.19.02', '17.18.30 (7)', '17.18.30 (6)', '17.18.30 (5)', '17.18.30 (4)', '17.18.30 (3)', '17.18.30 (2)', '17.18.30 (1)', '17.18.29 (2)', '17.18.29', '17.18.27', '17.18.26']
paths = [Path('/Users/tprice/Downloads') / ('WhatsApp Image 2026-10-22 at ' + n + '.jpeg') for n in names]
visual = {
    1: [(1, 0, False), (3, 270, False)],
    2: [(2, 270, False), (1, 0, False)],
    3: [(2, 270, True), (1, 0, False)],
    4: [(1, 0, False), (3, 270, True)],
    5: [(2, 270, True), (1, 0, True), (3, 270, True)],
    6: [(2, 270, True), (1, 0, True), (3, 270, True)],
    7: [(2, 270, True), (1, 0, True), (3, 270, True)],
    8: [(2, 270, True), (1, 0, True), (3, 270, True)],
    9: [(1, 0, True), (2, 0, True), (3, 0, True)],
    10: [(1, 0, True), (2, 0, True), (3, 0, True)],
    11: [(2, 0, True), (3, 0, True)],
    12: [(2, 0, True), (3, 0, True)],
    13: [(1, 0, True), (2, 0, True), (3, 0, True)],
}
quads = {
    (3, 1): [(119, 54), (1110, 89), (1064, 1073), (100, 1028)],
    (4, 2): [(560, 90), (1481, 118), (1440, 1022), (545, 1012)],
    (5, 1): [(209, 309), (500, 300), (472, 710), (197, 661)],
    (5, 2): [(499, 300), (881, 290), (861, 768), (472, 709)],
    (5, 3): [(912, 279), (1480, 269), (1429, 866), (861, 768)],
    (6, 1): [(144, 267), (698, 274), (739, 797), (198, 839)],
    (6, 2): [(724, 284), (1128, 293), (1150, 709), (751, 755)],
    (6, 3): [(1146, 293), (1426, 306), (1445, 664), (1151, 708)],
    (7, 1): [(79, 217), (531, 219), (541, 673), (87, 668)],
    (7, 2): [(566, 222), (1019, 223), (1012, 674), (569, 674)],
    (7, 3): [(1046, 220), (1504, 233), (1491, 677), (1041, 676)],
    (8, 1): [(149, 245), (577, 246), (585, 669), (157, 669)],
    (8, 2): [(610, 248), (1034, 253), (1038, 679), (609, 678)],
    (8, 3): [(1067, 249), (1497, 256), (1484, 682), (1064, 679)],
    (9, 1): [(118, 284), (482, 284), (484, 638), (120, 636)],
    (9, 2): [(648, 281), (1000, 283), (997, 635), (649, 636)],
    (9, 3): [(1162, 279), (1523, 281), (1523, 630), (1161, 632)],
    (10, 1): [(175, 274), (593, 273), (595, 685), (175, 683)],
    (10, 2): [(611, 271), (1025, 268), (1020, 681), (614, 681)],
    (10, 3): [(1056, 271), (1477, 276), (1466, 685), (1050, 682)],
    (11, 1): [(120, 198), (793, 193), (790, 869), (130, 871)],
    (11, 2): [(851, 202), (1516, 212), (1500, 871), (844, 870)],
    (12, 1): [(177, 205), (789, 208), (789, 810), (198, 811)],
    (12, 2): [(840, 211), (1427, 221), (1408, 799), (840, 800)],
    (13, 1): [(181, 368), (519, 370), (521, 694), (180, 694)],
    (13, 2): [(804, 359), (1121, 359), (1120, 677), (811, 677)],
    (13, 3): [(1138, 361), (1451, 366), (1455, 669), (1135, 669)],
}
ref_ids = ['cnqzTNngPVsAAAAAAA534Q', 'cnqzTNngPVsAAAAAAA533w', 'cnqzTNngPVsAAAAAAA533Q']
ref_quads = [[(354, 175), (1224, 170), (1224, 1047), (358, 1039)], [(336, 127), (1273, 128), (1273, 1080), (325, 1073)], [(393, 152), (1268, 146), (1262, 1023), (395, 1027)]]

def features(image, quad):
    # Perspective normalization is numeric inspection in memory. No edited
    # or reconstructed listing photograph is saved by this comparison.
    rows, values = [], []
    for (x, y), (u, v) in zip([(0, 0), (159, 0), (159, 159), (0, 159)], quad):
        rows.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]])
        values.extend([u, v])
    transform = np.linalg.solve(np.array(rows, dtype=float), np.array(values, dtype=float))
    normalized = image.transform((160, 160), Image.Transform.PERSPECTIVE, transform, Image.Resampling.BICUBIC).convert('L').filter(ImageFilter.GaussianBlur(.6))
    gray = np.asarray(normalized, dtype=float)
    local = gray - np.asarray(normalized.filter(ImageFilter.GaussianBlur(8)), dtype=float)
    gy, gx = np.gradient(gray)
    return local, np.hypot(gx, gy)

def corr(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float(np.sum(a*b) / (np.sqrt(np.sum(a*a)*np.sum(b*b)) + 1e-9))

def score(source, target):
    return max(.65*abs(corr(np.roll(source[0], (dy, dx), (0, 1))[12:-12, 12:-12], target[0][12:-12, 12:-12])) + .35*corr(np.roll(source[1], (dy, dx), (0, 1))[12:-12, 12:-12], target[1][12:-12, 12:-12]) for dy in (-3, 0, 3) for dx in (-3, 0, 3))

refs = {i+1: features(ImageOps.exif_transpose(Image.open(JOB / 'originals' / (name + '.jpeg'))), quad) for i, (name, quad) in enumerate(zip(ref_ids, ref_quads))}
photos = []
for num, path in enumerate(paths, 1):
    image = ImageOps.exif_transpose(Image.open(path))
    panels = []
    for pos, (member, rotation, full) in enumerate(visual[num], 1):
        panel = {'left_to_right_position': pos, 'component_number': member, 'rotation_clockwise_degrees': rotation, 'whole_outline_visible': full}
        quad = quads.get((num, pos))
        if quad:
            target = features(image, quad)
            ranking = []
            for identity, source in refs.items():
                for k in range(4):
                    ranking.append({'component': identity, 'rotation_clockwise_degrees': (-90*k) % 360, 'score': round(score([np.rot90(a, k) for a in source], target), 5)})
            ranking.sort(key=lambda r: r['score'], reverse=True)
            panel['numeric_ranking'] = ranking[:3]
            panel['diagnostic_quad'] = quad
            panel['numeric_top_agrees_with_visual'] = (ranking[0]['component'], ranking[0]['rotation_clockwise_degrees']) == (member, rotation)
        else:
            panel['numeric_scope'] = 'Truncated face: visual ridge pattern and overlapping wider photographs; no whole-face numeric score or isolated-image qualification.'
            panel['supporting_wider_photo_numbers'] = [3, 5, 6, 7, 8] if member == 2 else [4, 5, 6, 7, 8] if member == 3 else [3, 4, 5, 6, 7, 8]
        panels.append(panel)
    photos.append({'image_number': num, 'local_path': str(path), 'source_filename': path.name, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'source_bytes': path.stat().st_size, 'image_role': 'Detail / partial arrangement' if num <= 4 else 'Full arrangement on brick wall', 'panels': panels})
    print(json.dumps({'image': num, 'left_to_right': [p['component_number'] for p in panels], 'full_panels': [p['whole_outline_visible'] for p in panels], 'numeric': [p.get('numeric_ranking', [None])[0] for p in panels], 'mismatches': [p['left_to_right_position'] for p in panels if p.get('numeric_top_agrees_with_visual') is False]}))
result = {'scope': 'Current White numbered folder originals plus visual review and diagnostic in-memory normalization; scores are not probabilities or physical-cast verification.', 'reference_file_ids': ['id:' + x for x in ref_ids], 'images': photos, 'source_photos': 13, 'panel_appearances': 33, 'whole_visible_panel_appearances': 27, 'detail_or_partial_photo_count': 4, 'full_arrangement_photo_count': 9, 'listing_images_edited_or_created': 0, 'native_writes': 0, 'master_writes': 0}
(JOB / 'panel-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
