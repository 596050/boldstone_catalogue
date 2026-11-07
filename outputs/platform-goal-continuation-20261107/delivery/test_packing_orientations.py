"""Find conservative carton envelopes for a rotated, cushioned artwork prism.

This is a geometric packing plan, not a measured parcel or drop-test result.
All original product measurements, price fields and native listings stay intact.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, itertools, math
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
app = json.loads((ROOT / 'outputs/platform-goal-continuation-20261106/resume-2355/specifications-current.json').read_text())
drafts = json.loads((ROOT / 'outputs/platform-goal-continuation-20261106/resume-2203/ebay-sapr-drafts-current.json').read_text())['records']
products = {next(f['value'] for f in p['fields'] + p['listing_fields'] if f['key'] == 'Seller SKU'): p for p in app['products']}
assert len(drafts) == 66 and len({r['sku'] for r in drafts}) == 66
padding, wall, tolerance = 5., .5, .5
maximum = np.array([61., 46., 46.])
clearance = 2 * (padding + wall) + tolerance

def axis_matrix(axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    if axis == 0:
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)
    if axis == 1:
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)

rotations = [axis_matrix(axis, math.radians(deg / 4))
             for axis in range(3) for deg in range(361)]
# Broader rotations are exploratory: an unsuccessful search is not an impossibility proof.
rng = np.random.default_rng(20261107)
q = rng.normal(size=(100000, 4))
q /= np.linalg.norm(q, axis=1)[:, None]
w, x, y, z = q.T
random_rotations = np.stack([
    1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w),
    2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w),
    2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)
], axis=1).reshape(-1, 3, 3)
matrices = np.concatenate([np.array(rotations), random_rotations])
assert np.max(np.abs(matrices @ matrices.transpose(0, 2, 1) - np.eye(3))) < 1e-10
assert np.min(np.linalg.det(matrices)) > .999999
absolute = np.abs(matrices)
signs = np.array(list(itertools.product([-1, 1], repeat=3)))
results = []
for draft in drafts:
    p = products[draft['sku']]
    shipment = p['us_shipping']
    dims = np.array(shipment.get('artwork_upper_cm', []), dtype=float)
    weight = shipment.get('artwork_upper_kg')
    record = dict(catalogue_id=p['id'], sku=draft['sku'], title=p['retail_name'],
                  original_estimated_carton_cm=shipment.get('packed_cm'),
                  source_app_revision=app['revision'], measured=False, native_changes=0)
    if dims.shape != (3,) or not np.all(np.isfinite(dims)) or np.any(dims <= 0) or not weight:
        record.update(status='HOLD_SOURCE_MEASUREMENTS_REQUIRED')
        results.append(record)
        continue
    record.update(artwork_upper_cm=dims.tolist(), artwork_upper_kg=weight)
    envelopes = absolute @ dims
    cartons = np.ceil(envelopes + clearance - 1e-9)
    ordered = np.sort(cartons, axis=1)[:, ::-1]
    fitting = np.all(ordered <= maximum, axis=1)
    packing_kg = max(3., .1 * weight)
    packed_kg = math.ceil((weight + packing_kg) * 10 - 1e-9) / 10
    record.update(provisional_packing_allowance_kg=packing_kg, planned_upper_packed_kg=packed_kg)
    if not fitting.any():
        diagonal_impossible = float(np.linalg.norm(dims)) > float(np.linalg.norm(maximum - clearance))
        record.update(status='NO_TESTED_FIT', diagonal_necessary_bound_fails=diagonal_impossible,
                      geometric_impossibility_proven_for_this_prism_and_clearance=diagonal_impossible)
        results.append(record)
        continue
    candidates = np.flatnonzero(fitting)
    # Prefer a repeatable single-axis cradle and at least 1 cm below each
    # carrier ceiling over a less practical minimum-volume random rotation.
    practical = np.array([i for i in candidates
                          if i < len(rotations) and (i % 361) % 60 == 0
                          and np.all(maximum - ordered[i] >= 1)], dtype=int)
    ranked = practical if len(practical) else candidates
    index = int(ranked[np.argmin(np.prod(ordered[ranked], axis=1))])
    rotation = matrices[index]
    carton = cartons[index]
    permutation = np.argsort(carton)[::-1]
    rotation = rotation[permutation]
    carton = carton[permutation]
    corners = (signs * dims / 2) @ rotation.T
    minimum_cushion = carton / 2 - np.max(np.abs(corners), axis=0) - wall
    # Independently check every corner against every inner carton wall.
    assert np.all(np.abs(corners) + padding + wall <= carton / 2 + 1e-9)
    assert np.all(minimum_cushion >= padding + tolerance / 2 - 1e-9)
    assert np.all(carton <= maximum)
    record.update(status='GEOMETRIC_PLAN_REQUIRES_PACKING_REVIEW' if packed_kg <= 20 else 'GEOMETRIC_FIT_WEIGHT_REVIEW_REQUIRED',
                  proposed_outer_carton_cm=carton.astype(int).tolist(), rotation_matrix=rotation.tolist(),
                  minimum_cushion_to_inner_wall_cm=minimum_cushion.tolist(),
                  eligible_size_and_assumed_weight=packed_kg <= 20,
                  practical_single_axis_cradle=index in practical,
                  rotation_axis=(index // 361 if index < len(rotations) else None),
                  rotation_degrees=((index % 361) / 4 if index < len(rotations) else None),
                  carrier_limit_reserve_cm=(maximum - carton).tolist(),
                  proposed_native_tier=('Medium up to 10 kg' if packed_kg <= 10 else 'Medium up to 20 kg') if packed_kg <= 20 else None,
                  caution='Build a supported foam cradle; the packed panel must not move. Source box, weigh and measure it before selecting a carrier label. This is not a physical packing/impact validation.')
    results.append(record)

proof = dict(status='GEOMETRIC_PLANS_ONLY_NOT_MEASURED_PACKAGES', checked_utc=datetime.now(timezone.utc).isoformat(),
             source_drafts=66, current_native_tier_maximum_cm=maximum.tolist(), cushion_cm=padding,
             assumed_carton_wall_cm=wall, additional_total_dimensional_tolerance_cm=tolerance,
             orientations_tested=len(matrices), native_or_app_writes=0, records=results)
(OUT / 'ebay-packing-orientation-plans.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'drafts_checked':len(results),'geometric_and_assumed_weight_plans':sum(r.get('eligible_size_and_assumed_weight',False) for r in results),
                  'geometric_fit_weight_review':sum(r['status']=='GEOMETRIC_FIT_WEIGHT_REVIEW_REQUIRED' for r in results),
                  'no_tested_fit':sum(r['status']=='NO_TESTED_FIT' for r in results),'native_or_app_writes':0}))
for r in results:
    if r.get('eligible_size_and_assumed_weight'):
        print(json.dumps({k:r[k] for k in ['sku','title','artwork_upper_cm','proposed_outer_carton_cm','planned_upper_packed_kg','proposed_native_tier']}))
