"""Prepare an app-only specification overlay; this script never writes live reviews."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json
import re
import sqlite3

ROOT = Path(__file__).resolve().parent
snapshot = json.loads((ROOT / 'initial-app-fields.json').read_text())
products = snapshot['products']
assert len(products) == 188
assert snapshot['source']['register_sha256'] == '9b4b15ca857bea027637b3dd1474bfb98c87746bb842b49003b526da6770e748'
db = sqlite3.connect('file:' + snapshot['source']['gallery_database'] + '?mode=ro', uri=True)
native = {row[0]: json.loads(row[3]) for row in db.execute('SELECT * FROM products')}
db.close()

def clean(text):
    text = text.replace('\u2014', '-').replace('**', '')
    return re.sub(r'\s+', ' ', text).strip(' .')

dimensions, weights, materials = {}, {}, {}
def put(target, indexes, value):
    if isinstance(indexes, int):
        indexes = [indexes]
    for i in indexes:
        target[i] = value

# Each selected size is taken from its recorded working field. Alternatives and
# the distinction between owner measurements and modelling remain in provenance.
dimension_groups = [
([0], 'Panel 200 × 100 × 5 cm; support framework 186 × 86 × 6.5 cm; face thickness 15 mm; framework metal 4 mm'),
([1,3,4,5,6,7,8,9,34,59,61,173,174], '30 × 30 × 6 cm'),
([2,10], '50 × 30 × 6 cm'),
([11,12], '120 × 60 × 6 cm'),
([13,14], '52 × 25 × 5 cm'),
([15], '100 × 100 × 8 cm'),
([16], '55 cm high × 30 cm wide × 5–7 cm deep'),
([17], '55 cm high × 55 cm wide × 5–7 cm deep'),
([18], '80 cm wide × 60 cm high × 5–8 cm deep'),
([19,21], '50 × 25 × 8 cm'),
([20,22], '50 × 25 cm; approximately 5–8 cm deep'),
([23], '100 × 22 × 8 cm'),
([24], '250 cm high × 100 cm wide; approximately 10 cm deep'),
([25,26], '70 cm high × 95 cm wide; approximately 10 cm deep'),
([27], '55 cm high × 55 cm wide; approximately 6 cm deep'),
([28,29,128,129,130,132,133,134,146,147,148,149,150,151,152,165,166,175], '30 × 30 cm; approximately 5–7 cm deep'),
([30,31,32,33], '100 cm high × 22 cm wide × 6 cm deep'),
([35,38], '45 × 40 × 5 cm'),
([36,37], '40 × 45 × 6 cm'),
([39,41], '90 cm high × 15 cm wide × 9 cm deep'),
([40,42,43,44], '90 cm high × 15 cm wide × 8 cm deep'),
([45,48], '35 cm high × 20 cm wide × 6 cm deep'),
([46,47,50,51,52,53,54,55,56], '35 cm high × 21 cm wide × 6 cm deep'),
([49,57], '35 cm high × 20 cm wide × 5–7 cm deep'),
([58,60,127], '30 × 30 × 7 cm'),
([62,104,105], '100 × 30 × 6 cm'),
([63,64,65,66,67,68], '50 × 30 × 7 cm'),
([69,84,85,86,89], '70 cm high × 15 cm wide; approximately 5–7 cm deep'),
([70], '70 cm high × 30 cm wide × 7–10 cm deep'),
([71,72,74], '70 × 50 × 6 cm'),
([73], '75 × 50 cm; approximately 6 cm deep'),
(list(range(75,81)), '40 × 40 cm; approximately 3 cm deep'),
([81,82,83], '100 cm high × 50 cm wide × 6 cm deep'),
([87,88], '70 cm high × 15 cm wide × 7 cm deep'),
(list(range(90,94)), '35 × 35 cm per panel; approximately 6 cm deep; four-panel arrangement 70 × 70 cm'),
([94], '100 × 100 cm fountain block; 50 cm body depth'),
(list(range(95,101)), '80 cm wide × 240 cm high; approximately 8 cm deep'),
([101], '25 cm high × 25 cm wide × 5 cm deep'),
([102,103], '35 × 35 × 6 cm per panel'),
([106], '30 × 30 cm; approximately 5–7 cm deep'),
([107,109,110,112,114,115,116,117], '25 × 25 cm; approximately 6 cm deep'),
([108,111,113], '25 × 25 cm; 4–6 cm side depth'),
([118], '25 × 25 cm; approximately 4–7 cm deep'),
([119,120], '55 × 42 cm; approximately 7 cm deep'),
([121,123,124,125], '100 × 22 cm; approximately 6 cm panel depth'),
([122], '100 cm wide × 22 cm high; approximately 6 cm panel depth'),
([126], '45–60 cm square; 10–18 cm overall height'),
([131,135], 'Approximately 35 × 35 cm overall, including border; approximately 6 cm deep'),
([136,137], '55 × 55 cm; approximately 5–8 cm deep'),
([138], '30 × 30 cm; approximately 5–8 cm deep'),
([139,140], '70 cm high × 50 cm wide; 5–7 cm side depth'),
([141], '70 cm high × 50 cm wide × 7 cm deep'),
([142], '51 cm high × 48 cm wide; 5–7 cm side depth'),
([143], '74 cm high × 35 cm wide × 9 cm deep'),
([144,145], '25 × 25 cm; approximately 5–7 cm deep'),
([153,154,155], '275 × 100 cm; approximately 5–7 cm deep'),
([156], '31.5 × 31.5 × 4 cm'),
([157,158], '100 cm wide × 50 cm high × 6 cm deep'),
([159,160,161], '70 cm high × 50 cm wide × 5–7 cm panel depth'),
([162,163], '70 cm wide × 50 cm high × 5–7 cm panel depth'),
([164], '80 × 60 cm; approximately 6 cm deep'),
([167,169], '55 × 55 cm; approximately 5–7 cm deep'),
([168,170,172], '55 × 55 × 7 cm'),
([171], '55 × 55 cm; 5–8 cm side depth'),
([176], '100 × 60 cm; 2–4 cm deep'),
([177], '150 cm high × 55 cm wide; 2–4 cm deep'),
(list(range(178,185)), '50 cm diameter × 2.5 cm deep'),
([185], 'Approximately 100 cm high × 16 cm wide; approximately 3 cm deep'),
([186,187], '40 × 40 × 6 cm'),
]
for ids, value in dimension_groups:
    for i in ids:
        assert i not in dimensions, i
    put(dimensions, ids, value)
assert set(dimensions) == set(range(188))

# Central values and useful ranges are preserved; packaged/system weights are
# never substituted for sculpture weights.
for i, p in enumerate(products):
    fields = {f['key']: f for f in p['fields']}
    text = fields['Weight']['value'].replace('**','').split('\nOwner:')[0]
    match = re.search(r'(\d+(?:\.\d+)?(?:\s*[–-]\s*\d+(?:\.\d+)?)?)\s*kg', text)
    assert match, (i, text)
    number = re.sub(r'\s+', '', match[1])
    prefix = 'Approximately ' if re.search(r'approx|estimate|guess|calculated|conditional|tentative', text, re.I) else ''
    value = prefix + number + ' kg'
    # Keep an immediately supplied range, but not competing older source values.
    tail = text[match.end():].split('—')[0]
    range_match = re.search(r'(?:working range|estimated(?: range)?|range)\s*(\d+(?:\.\d+)?[–-]\d+(?:\.\d+)?)\s*kg', tail)
    if range_match and range_match[1] != number:
        value += ' (range ' + range_match[1] + ' kg)'
    if 'per panel' in text or 'per White panel' in text or 'each' in text:
        value += ' per panel'
    weights[i] = value
put(weights, [11,12], 'Approximately 20–22 kg per panel')
put(weights, [13,14], 'Approximately 6–8 kg per panel')
put(weights, [19,21], 'Approximately 6–8 kg per panel')
put(weights, 24, 'Approximately 100 kg dry (range 75–140 kg)')
put(weights, [25,26], 'Approximately 35 kg dry panel (range 25–45 kg); excludes water and system components')
put(weights, 82, '15 kg')
put(weights, 94, 'Approximately 100 kg dry (range 60–180 kg), for hollow construction; excludes water and system components')
put(weights, list(range(95,101)), 'Approximately 105 kg per panel (range 101–107 kg)')
put(weights, 116, '4 kg dry')
put(weights, [122,125], 'Approximately 8–10 kg dry panel; excludes fittings and water')
put(weights, 126, 'Approximately 10–20 kg empty, for lightweight cast construction')
put(weights, [160,161,163], 'Approximately 12–15 kg dry panel; excludes basin, pump and water')
put(weights, [167,169], 'Approximately 10–12 kg for cast-composite construction')
put(weights, 176, 'Approximately 5–12 kg for lightweight rigid-board construction')
put(weights, 177, 'Approximately 8–15 kg for lightweight rigid-board construction')
put(weights, 185, 'Approximately 7 kg net (range 4–10 kg)')

material_groups = [
([0,15], 'Jesmonite with a Bath Stone finish'),
([1,2], 'Plaster with a smooth, contoured white relief finish'),
([3,5], 'Cast plaster with a white finish'),
([4,8], 'Cast plaster with a pewter-effect metallic finish'),
([6], 'Plaster with a bronze/brown surface effect'),
([7], 'Cast plaster with pale blue and white marbling'),
([9], 'Cast plaster with white and black marbling'),
([10], 'Plaster with a gold-leaf finish'),
([11,12,13,14,16,17,18,19,21,23,28,29,30,33,43,44,49,57,84,85,86,89,103,108,111,113,119,120,121,122,124,125,139,140,141,148,150,152,159,160,162,163,168,170,171,172,175,186,187], 'Jesmonite AC730 with a white marble stone finish'),
([20,22], 'Jesmonite AC730 with a gold-leaf finish'),
([24,25,26], 'Jesmonite AC730 with a pale stone finish'),
([27], 'Jesmonite AC730 with a white textured stone/aggregate finish'),
([31,32], 'Jesmonite AC730 with a verdigris-effect patina'),
([34,38,71,72,74,143], 'Plaster/gypsum composite with a white marble stone finish'),
([35], 'Plaster/gypsum composite with white and gold-leaf finishes'),
([36,37], 'Gypsum composite with a white stone finish'),
([39,41,87], 'Gypsum composite with a terracotta-effect surface'),
([40,42], 'Cast mineral composite with an applied verdigris patina'),
([45], 'Cast mineral composite with blue-green patina and bronze-effect ridges'),
([46], 'Plaster and sand with a faux rust/iron surface effect'),
([47,55], 'Sand/mineral composite with a faux copper/verdigris finish'),
([48], 'Cast mineral composite with verdigris, copper and rust effects'),
([50], 'Cast mineral composite with bronze and verdigris effects'),
([51], 'Plaster and sand with a hand-laid copper surface effect'),
([52], 'Plaster and sand composite with copper and partial verdigris effects'),
([53], 'Plaster-based cast with applied gold leaf'),
([54], 'Cast mineral composite with a hand-painted faux rust-on-iron finish'),
([56], 'Cast mineral composite with a verdigris/copper-effect finish'),
([58,60], 'Plaster with a copper-bronze and verdigris-effect finish'),
([59,61,128,130,132,133,142], 'Cast mineral composite with a white stone finish'),
([62,73,104,106,146,161], 'Cast mineral composite with a white stone-effect finish'),
([63], 'Plaster/gypsum composite with a gold-leaf surface'),
([64], 'Cast mineral/gypsum composite with black and white marbling'),
([65], 'Cast plaster/mineral composite with a pewter-effect finish'),
([66,67,68], 'Cast mineral/gypsum composite with a white stone-effect finish'),
([69], 'Cast mineral composite with an off-white textured finish and shell motifs'),
([70], 'Cast mineral/gypsum composite with a gold-effect finish'),
([75,77,79], 'Plaster/gypsum composite with a cream finish'),
([76,78,80], 'Plaster/gypsum composite with a white finish'),
([81], 'Cast mineral composite with bronze and verdigris surface effects'),
([82], 'Jesmonite AC730 with a white marble stone finish'),
([83], 'Cast mineral composite with a white/cream stone finish'),
([88], 'Gypsum composite with a verdigris-green surface effect'),
([90,91,92,93], 'Plaster/gypsum composite with a white/cream stone-effect finish'),
([94], 'Jesmonite AC730 with a white/cream stone-effect finish'),
([95,97,99], 'Jesmonite AC730 with a sandstone-effect finish'),
([96,98,100], 'Jesmonite AC730 with a white/cream textured finish'),
([101], 'Cast mineral composite with a white ground and gold-leaf-effect finish'),
([102], 'Cast mineral composite with a gold-coloured surface'),
([105], 'Cast mineral composite with white and gold-leaf-effect surfaces'),
([107,110,112], 'Cast mineral composite with verdigris-green, copper and rust effects'),
([109], 'Cast mineral composite with painted blue, white and dark markings'),
([114], 'Sand/plaster cast with faux silver-leaf and bronze finishes'),
([115], 'Sand/plaster cast with a faux verdigris/copper finish'),
([116], 'Plaster composite with a faux verdigris and rust finish'),
([117], 'Jesmonite AC730 with a white stone-effect finish'),
([118], 'Cast mineral composite with a rust/iron-effect surface'),
([123], 'Cast mineral composite with black, grey and white marbling'),
([126], 'Cast mineral composite with a white/light stone-effect finish'),
([127], 'Plaster with a soft silver metallic finish'),
([129,134], 'Jesmonite AC730 with white and gold-coloured surface treatments'),
([131,135], 'Cast mineral composite with a white/pale stone-effect relief and border'),
([136,137], 'Cast mineral composite with a pale/white stone-effect, coarse textured finish'),
([138], 'Cast mineral composite with a pale/white stone-effect finish and a coarse textured band'),
([144], 'Cast mineral composite with a beige rough-textured finish'),
([145], 'Plaster/gypsum composite with gold leaf on a rough-textured surface'),
([147,149,151], 'Cast mineral composite with a beige/sand textured surface'),
([153], 'Cast mineral composite with a white textured finish'),
([154], 'Cast mineral composite with an off-white textured finish'),
([155], 'Cast mineral composite with a pale textured finish'),
([156], 'Wood board with rust and hand-painted faux verdigris'),
([157], 'Plaster/gypsum composite with a white marble stone finish and sand-textured relief'),
([158], 'Plaster/gypsum composite with a white marble stone finish and smooth rippled relief'),
([164], 'Cast mineral/plaster composite with a textured white finish'),
([165,166], 'Cast mineral composite with a pale stone finish'),
([167,169], 'Cast mineral composite with a bronze-effect finish'),
([173], 'Plaster/gypsum composite with a blue-wash faux verdigris finish'),
([174], 'Cast gypsum composite with hand-applied faux verdigris'),
([176], 'Coated rigid board and mixed media with blue, brown and rust effects'),
([177], 'Coated rigid board and mixed media with rust-brown and blue-grey patina effects'),
([178], 'Plaster/gypsum composite with azure blue and white marbling'),
([179], 'Plaster/gypsum composite with a multicoloured marbled finish'),
([180], 'Plaster/gypsum composite with green and white marbling'),
([181], 'Plaster/gypsum composite with pale blue marbling'),
([182], 'Plaster/gypsum composite with terracotta, rust and cream marbling'),
([183], 'Plaster/gypsum composite with turquoise and dark marbling'),
([184], 'Plaster/gypsum composite with yellow/ochre and grey marbling'),
([185], 'Plaster/gypsum composite with hand-marbled blue, white and cream relief'),
]
for ids, value in material_groups:
    for i in ids:
        assert i not in materials, i
    put(materials, ids, value)
assert set(materials) == set(range(188))
materials[0] = 'Jesmonite AC730 with a Bath Stone finish'

def money(value):
    decimal = Decimal(str(value))
    return '£' + (f'{decimal:,.0f}' if decimal == decimal.to_integral_value() else f'{decimal:,.2f}')

changes, commercial_checks = [], []
confirmed = {(82,'Weight'), (116,'Dimensions / depth'), (116,'Weight'),
             (116,'Material / finish'), (180,'Dimensions / depth'),
             (180,'Weight'), (180,'Material / finish'), (35,'Dimensions / depth')}
for i, p in enumerate(products):
    source = native[p['id']]
    fields = {f['key']: f for f in p['fields']}
    selling = source['selling_details']
    price = money(selling['estimated_price'])
    if selling.get('estimated_price_upper') is not None:
        price += '–' + money(selling['estimated_price_upper'])
    # Check the application projection against the authoritative master, not
    # merely against its shortened selling_details rendering.
    master_price = source['master_fields']['Individual price']['display']
    price_numbers = [Decimal(n.replace(',','')) for n in re.findall(r'£\s*([\d,]+(?:\.\d+)?)', master_price)]
    expected = [Decimal(str(selling['estimated_price']))]
    if selling.get('estimated_price_upper') is not None:
        expected.append(Decimal(str(selling['estimated_price_upper'])))
    assert price_numbers[:len(expected)] == expected, (p['id'], master_price, expected)
    commercial_checks.append({'product_id':p['id'], 'master_price':master_price,
                              'master_availability':source['master_fields']['Availability'], 'selling_details':selling})
    price += ' ' + selling.get('sale_unit', 'per sculpture')
    low, high = selling['lead_time_min_weeks'], selling['lead_time_max_weeks']
    lead = f'{low} week' if low == high == 1 else f'{low} weeks' if low == high else f'{low}–{high} weeks'
    values = {'Dimensions / depth':dimensions[i], 'Weight':weights[i], 'Material / finish':materials[i],
              'Fixing':'Choice of keyhole fixing or French cleat', 'Price':price,
              'Availability':'Made to order', 'Lead time':lead}
    if i in (69,70,90,91,92,93,116):
        values['Fixing'] = 'Keyhole fixing; French cleat available as an alternative'
    if i in range(95,101) or i in range(178,185):
        values['Fixing'] = 'French cleat; keyhole fixing available as an alternative'
    if i in range(178,185):
        values['Fixing'] += '; RGB lighting'
    if i == 126:
        values['Fixing'] = 'Freestanding on a suitable level base; wall-mounted fixing to be agreed'
    if i == 116:
        values['Availability'] = 'Made to order; unlimited order availability'
    reviews = {(r['kind'],r['item_id']):r for r in p['reviews']}
    for key, value in values.items():
        f = fields[key]
        prior = reviews.get(('field',key))
        assert prior is None, ('Existing specification choice must be reconciled',p['id'],key)
        certainty = 'estimate' if re.search(r'estimat|guess|hypothes|propos|conditional|tentative', f['value'], re.I) else 'source_claim'
        if key in ('Availability','Lead time','Fixing') or (i,key) in confirmed or (i==116 and key=='Price'):
            certainty = 'confirmed'
        if key == 'Price' and i != 116:
            certainty = 'estimate'
        if i == 126 and key == 'Fixing':
            certainty = 'estimate'
        if i in (178,179,181,182,183,184) and key == 'Fixing':
            certainty = 'estimate'
        evidence = f"Retained working source for {p['id']}; {snapshot['source']['register_sha256']}; field: {key}."
        if key in ('Availability','Lead time','Price'):
            evidence += ' Commercial policy: ' + selling['policy_ref'] + '.'
        if key == 'Fixing':
            evidence += ' Owner offers keyhole fixing or French cleat; piece-specific source notes retained.'
        if (i,key) in confirmed:
            evidence += ' Direct owner statement retained in the original field and its basis.'
        changes.append({'index':i,'product_id':p['id'],'name':clean(p['name']), 'item_id':key,
                        'version':0,'before':None,'source':f,'value':clean(value),
                        'data':{'decision':'edit','value':clean(value),'certainty':certainty,
                         'notes':'Listing wording simplified at the owner request on 25 October 2026. Original values, source alternatives, conditions and uncertainty remain in the source record; no new physical measurement is asserted.',
                         'evidence':evidence}})
    # Normalise display punctuation only; preserve the current White title edit.
    current_name = reviews.get(('field','Name'))
    name_data = current_name['data'] if current_name else {}
    name = name_data['value'] if name_data.get('decision') == 'edit' else fields['Name']['value']
    if '\u2014' in name and name_data.get('decision') != 'exclude':
        data = dict(name_data) if current_name else {'certainty':'source_claim', 'evidence':'Existing catalogue identity and display name retained.'}
        data.update(decision='edit',value=name.replace('\u2014','-'))
        data['notes'] = (data.get('notes','') + ' Display punctuation only: em dash replaced with hyphen at owner request.').strip()
        changes.append({'index':i,'product_id':p['id'],'name':clean(p['name']),'item_id':'Name',
                        'version':current_name['version'] if current_name else 0,
                        'before':current_name,'source':fields['Name'],'value':data['value'],'data':data})

assert len([c for c in changes if c['item_id']!='Name']) == 1316
assert all(c['value'] and '\u2014' not in c['value'] for c in changes)
assert all(not re.search(r'estimat|guess|propos|hypothes',c['value'],re.I) for c in changes)
plan = {'schema':'boldstone-app-specification-cleanup/v1','source':snapshot['source'],
        'source_snapshot_sha256':hashlib.sha256((ROOT/'initial-app-fields.json').read_bytes()).hexdigest(),
        'scope':'App review overlay only. Source fields and native images unchanged.',
        'products':188,'specification_fields':1316,'name_punctuation_edits':sum(c['item_id']=='Name' for c in changes),
        'changes':changes,'commercial_source_checks':commercial_checks}
(ROOT/'prepared-values.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
for i,p in enumerate(products):
    print(i,p['name'].replace('\u2014','-'))
    print(' | '.join([dimensions[i],weights[i],materials[i]]))
print('PREPARED',len(changes),'changes;',plan['name_punctuation_edits'],'names')
