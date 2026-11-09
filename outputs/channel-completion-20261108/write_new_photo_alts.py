"""Alt text written after visual inspection of the 18 original photographs."""
from pathlib import Path
import json
OUT=Path(__file__).parent
path=OUT/'website-photo-append-plan.json'
plan=json.loads(path.read_text())
alts=[
 'Two separately sold white Lunar Phase panels displayed side by side on brick, with curved recesses and a small spiral catching pink-toned light.',
 'Close view of the raised concentric rings and granular brown finish on the Cup Ring and Spiral Paver I panel.',
 'Close view of the raised curling spiral and granular brown finish on the Cup Ring and Spiral Paver II panel.',
 'White Bone Spiral II panel displayed against dark timber, with a raised spiral, broad curved recess and dappled sunlight.',
 'The separately sold white Bone Spiral I and II panels displayed together against dark timber, showing their adjoining curved and spiral forms.',
 'A tall white Magnolia Growth relief with pointed overlapping leaf forms, mounted on a red brick wall.',
 'A textured Sculpted Curves relief with a mottled surface, photographed among bamboo leaves.',
 'Two separately sold white Moon Fish Wave panels displayed together on a patterned wall, with central wave-like ridges and curved shell forms.',
 'Two separately sold white Ammonite Grande panels placed side by side to form a raised spiral, against a wooden backdrop.',
 'Close view of irregular gold-effect finish patches on the white raised leaf forms of Magnolia Growth.',
 'A white Islington Shellmoon Fountain relief resting on a workshop trolley outdoors, showing its spiral and broad curved channel.',
 'White Wave and Moonshadow II relief under warm lighting on a tiled wall, with overlapping curves casting deep shadows.',
 'A white Spiral Moon Relief panel standing against dark timber above gravel, with a raised spiral and sweeping circular recess.',
 'A white Lunar Water Catcher relief mounted on brick, with intersecting concave oval forms and a raised lower curve.',
 'An angled view of a Patina Panel lying on a rough surface, showing turquoise-green and rusty brown finish patterns.',
 'A silver-finish Lunar Phase IV relief mounted on stone, with a deep curved recess and reflected light across the surface.',
 'A white Lunar Phase II panel resting on a timber surface, showing its raised central spiral within a deep circular recess.',
 'Close view along Dune Ripple II ridges, showing the copper-coloured finish and turquoise verdigris accents.'
]
assert len(alts)==len(plan['photos'])==18
for photo,alt in zip(plan['photos'],alts):photo['alt_text']=alt
by_id={p['id']:p for p in plan['photos']}
for product in plan['products']:product['new_photo']=by_id[product['new_photo']['id']]
path.write_text(json.dumps(plan,indent=2)+'\n')
print('Added visually checked alt text for 18 originals.')
