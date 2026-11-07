"""Compare original detail texture with each group panel; never edit upload assets."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFont

OUT = Path(__file__).parent
records = json.loads((OUT / 'crater-matching-inputs.json').read_text())
inputs = {r['role']: r for r in records}
cv2.setNumThreads(2)
cv2.setRNGSeed(20261107)

def load(record, limit):
    path = Path(record['local_path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
    with Image.open(path) as source:
        source.seek(0)
        rgb = ImageOps.exif_transpose(source).convert('RGB')
        rgb.thumbnail((limit, limit))
        return rgb, cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY)

group_rgb, group = load(inputs['group'], 4000)
height, width = group.shape
boxes = [(int(a * width), int(.38 * height), int(b * width), int(.69 * height))
         for a, b in [(.07, .285), (.30, .495), (.505, .71), (.725, .94)]]
sift = cv2.SIFT_create(nfeatures=18000, contrastThreshold=.02)
target_points, target_descriptors = sift.detectAndCompute(group, None)
results = []
for role in ['I', 'II', 'III']:
    _, query = load(inputs[role], 2600)
    query_points, query_descriptors = sift.detectAndCompute(query, None)
    comparisons = []
    for position, (left, top, right, bottom) in enumerate(boxes, 1):
        indices = [n for n, point in enumerate(target_points)
                   if left <= point.pt[0] <= right and top <= point.pt[1] <= bottom]
        points = [target_points[n] for n in indices]
        descriptors = target_descriptors[indices]
        matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=100))
        nearest = matcher.knnMatch(query_descriptors, descriptors, k=2)
        good = [m for pair in nearest if len(pair) == 2
                for m, n in [pair] if m.distance < .7 * n.distance]
        # One target feature cannot independently validate several query features.
        unique = {}
        for match in sorted(good, key=lambda m: m.distance):
            unique.setdefault(match.trainIdx, match)
        good = list(unique.values())
        record = dict(position_from_left=position, ratio_matches=len(good), inliers=0)
        if len(good) >= 10:
            source_xy = np.float32([query_points[m.queryIdx].pt for m in good])
            target_xy = np.float32([points[m.trainIdx].pt for m in good])
            matrix, mask = cv2.findHomography(source_xy, target_xy, cv2.RANSAC, 5,
                                              maxIters=10000, confidence=.999)
            if matrix is not None and mask is not None:
                inside = mask.ravel().astype(bool)
                n = int(inside.sum())
                projected = cv2.perspectiveTransform(source_xy.reshape(-1, 1, 2), matrix).reshape(-1, 2)
                errors = np.linalg.norm(projected - target_xy, axis=1)
                hull = cv2.convexHull(target_xy[inside]) if n >= 3 else None
                area = float(cv2.contourArea(hull)) if hull is not None else 0
                record.update(inliers=n, inlier_ratio=n / len(good),
                              median_inlier_reprojection_error_px=float(np.median(errors[inside])) if n else None,
                              target_inlier_hull_area_px2=area,
                              homography=matrix.tolist())
        comparisons.append(record)
    ordered = sorted(comparisons, key=lambda r: r['inliers'], reverse=True)
    best, runner = ordered[:2]
    unique_match = (best['inliers'] >= 20 and best.get('inlier_ratio', 0) >= .4
                    and best.get('target_inlier_hull_area_px2', 0) >= 5000
                    and best['inliers'] >= 3 * max(runner['inliers'], 1))
    results.append(dict(role=role, input=inputs[role], comparisons=comparisons,
                        status='UNIQUE_TEXTURE_MATCH_REQUIRES_VISUAL_CONFIRMATION' if unique_match else 'AMBIGUOUS_OR_INSUFFICIENT_MATCH',
                        candidate_position=best['position_from_left'] if unique_match else None))
    print(json.dumps({'role': role, 'inliers_by_position': [r['inliers'] for r in comparisons],
                      'status': results[-1]['status'], 'candidate_position': results[-1]['candidate_position']}), flush=True)

proof = dict(status='DIAGNOSTIC_ONLY_NO_IDENTITY_OR_PUBLICATION_CHANGE',
             checked_utc=datetime.now(timezone.utc).isoformat(),
             method='SIFT, Lowe ratio 0.7, unique target features, independent per-panel RANSAC homographies',
             documentation='https://docs.opencv.org/4.13.0/d1/de0/tutorial_py_feature_homography.html',
             opencv_version=cv2.__version__, group_input=inputs['group'], group_analysis_size=[width, height],
             panel_boxes=boxes, original_files_unchanged=True, native_or_app_writes=0, records=results)
(OUT / 'crater-texture-matching.json').write_text(json.dumps(proof, indent=2) + '\n')
draw = ImageDraw.Draw(group_rgb)
font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 36)
for position, box in enumerate(boxes, 1):
    draw.rectangle(box, outline='yellow', width=6)
    draw.text((box[0], box[1] - 45), f'Position {position}', fill='yellow', font=font)
group_rgb.thumbnail((1600, 1600))
group_rgb.save(OUT / 'crater-analysis-position-guide.jpg', quality=90)
