"""Editable manufacturing costs and optional markup-driven listing prices."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import math
import re
from presentation import listing_value


def money(value):
    # Area/volume calculations can leave a half-penny just below its true value
    # (for example 93.55499999999999). Remove sub-nanopound arithmetic noise
    # before applying the same half-up penny rounding as the workbook.
    value = Decimal(str(value)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
    return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def rate(label, amount, basis, source='', minutes=0):
    return {'label': label, 'rate': amount, 'minutes': minutes, 'basis': basis, 'source': source}


DEFAULTS = {
    'schema': 1, 'currency': 'GBP',
    'reference_width_cm': 20, 'reference_height_cm': 35, 'reference_depth_cm': 6,
    'labour_hourly': 20, 'casting_minutes': 30, 'fixing_minutes': 5,
    'fixing_unit': 5, 'overhead_reference': 5,
    'default_pricing_mode': 'fixed', 'default_markup_percent': 100,
    'materials': {
        'gfrc': rate('GFRC - natural white', 5, 'Owner: £5 casting cost at 35 x 20 x 6 cm. Labour separate.'),
        'jesmonite': rate('Jesmonite AC730', 25.29, '4 kg mixed material per reference casting x £37.94 / 6 kg. Quantity is a modelling assumption; kit price includes VAT.', 'https://www.fslplymouth.co.uk/jesmonite-ac730/jesmonite-ac730-kits/'),
        'moulding_paste': rate('Moulding paste on a rigid support', 99, '2 litres per reference relief x £48/litre + £3 support allowance. £48/litre rounded from the Colart 2023 price guide (£45.30 / 0.946 L), not a current supplier quote. Thin-layer supported construction; not a structural drop-in replacement.', 'https://trade.colart.com/uk/wp-content/uploads/sites/3/2023/01/COL-Price-List-2023-LOW-RESOLUTION-2.pdf'),
        'gypsum': rate('Plaster / gypsum composite', 4, 'Working allowance: 80% of the owner GFRC casting cost; adjust to workshop purchases.')},
    'finishes': {
        'white': rate('Natural White - no added colour', 0, 'Natural white GFRC: no pigment or surface-effect charge.'),
        'pigment': rate('Single colour pigment', 2, 'Working allowance per reference face: £1 pigment + £1 application consumables.', minutes=10),
        'marbled': rate('Marbled / multicolour', 4, 'Working allowance per reference face: £2 colours + £2 blending consumables.', minutes=20),
        'verdigris': rate('Verdigris surface effect', 5, 'Owner: £5 complete verdigris effect per reference face; includes its base treatment.', minutes=20),
        'rust': rate('Rust surface effect', 5, 'Working allowance equal to owner verdigris: coloured base, rust effect and protective finish. Not a supplier quotation.', 'https://www.modernmasters.com/-/media/78C665DF05074FADB8C692A8FB2903AA.ashx', 20),
        'copper': rate('Copper leaf / surface effect', 4, 'Superior copper leaf £7.74 per 25 sheets, 14 x 14 cm = £15.80/m2; 25% overlap/waste on 0.07 m2 = £1.38 + £2.62 size/sealer/consumables allowance.', 'https://www.goldleafsupplies.co.uk/copper-transfer-25-leaf-booklet-140-x-140mm/', 20),
        'metallic': rate('Bronze / pewter / silver effect', 4, 'Working metallic pigment and sealer allowance, comparable to copper; not solid metal.', minutes=20),
        'gold_imitation': rate('Imitation gold leaf', 4, 'Superior imitation leaf £7.14 / 0.49 m2 x 0.07 m2 x 1.25 = £1.28; £2.72 size/sealer allowance.', 'https://www.goldleafsupplies.co.uk/schlag-metal-gold-2-5-transfer-25-leaf-booklet/', 25),
        'gold_genuine': rate('Genuine 23.5 ct gold leaf', 46, '£80.34 per 25 sheets at 8 x 8 cm = £502.13/m2; x 0.07 m2 x 1.25 = £43.94, plus £2.06 size/preparation. Full-face budget; purity is not a claim about the existing sculpture.', 'https://stonehouses.co.uk/collections/23-5ct-transfer/products/23-5ct-restoration-gold-leaf-transfer-25-leaves-20g', 35)},
    'notes': 'GBP cash-cost model, supplier rates VAT-inclusive where stated; owner baseline VAT status unspecified. No VAT added again. Rates checked 2026-10-30. Packaging, delivery, sales fees, installation and pump/plumbing systems excluded. Labour rate and times are editable planning inputs, not measured production times.'
}


def settings(reviews):
    record = next((r for r in reviews if (r['kind'], r['product_id'], r['item_id']) == ('cost_settings', '', '')), {})
    # Older saved rate tables predate pricing. Preserve every saved rate while
    # supplying the new defaults; merely reading the app does not rewrite them.
    return deepcopy({**DEFAULTS, **(record.get('data') or {})}), record.get('version', 0)


def number(value, name, minimum=0, maximum=1000000):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be a finite number between {minimum} and {maximum}.')


def validate_settings(data):
    if not isinstance(data, dict) or set(data) != set(DEFAULTS):
        raise ValueError('Cost settings are incomplete or contain unknown fields.')
    if data['schema'] != 1 or data['currency'] != 'GBP':
        raise ValueError('Unsupported cost model or currency.')
    for key in ('reference_width_cm', 'reference_height_cm', 'reference_depth_cm'):
        number(data[key], key, .01, 10000)
    for key in ('labour_hourly', 'casting_minutes', 'fixing_minutes', 'fixing_unit', 'overhead_reference'):
        number(data[key], key)
    if data['default_pricing_mode'] not in ('fixed', 'markup'):
        raise ValueError('Choose fixed prices or markup pricing.')
    number(data['default_markup_percent'], 'Default markup', 0, 10000)
    for group in ('materials', 'finishes'):
        if not isinstance(data[group], dict) or not 1 <= len(data[group]) <= 100 or not set(DEFAULTS[group]) <= set(data[group]):
            raise ValueError('Keep the built-in rates; add up to 100 materials or finishes.')
        for key, item in data[group].items():
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', key) or not isinstance(item, dict) or set(item) != {'label', 'rate', 'minutes', 'basis', 'source'}:
                raise ValueError('Invalid material or finish entry.')
            for k in ('label', 'basis', 'source'):
                if not isinstance(item[k], str) or len(item[k]) > 4000 or (k == 'label' and not item[k].strip()):
                    raise ValueError('Invalid rate text.')
            if item['source'] and not item['source'].startswith(('https://', 'http://')):
                raise ValueError('Source links must use http or https.')
            number(item['rate'], 'rate'); number(item['minutes'], 'minutes')
    if not isinstance(data['notes'], str) or len(data['notes']) > 10000:
        raise ValueError('Invalid model notes.')
    return deepcopy(data)


def values(product, reviews):
    choices = {r['item_id']: r['data'] for r in reviews if r['kind'] == 'field' and r['product_id'] == product['id']}
    return {f['key']: listing_value(f, choices.get(f['key'], {})) or '' for f in product['fields']}


def dimensions(text):
    # Only the first three dimensions describe the individual. Later framework
    # and arrangement dimensions never replace the panel's own size.
    nums = [sum(float(x) for x in m if x)/len([x for x in m if x]) for m in
            re.findall(r'(\d+(?:\.\d+)?)(?:\s*[–−-]\s*(\d+(?:\.\d+)?))?', text)]
    if 'diameter' in text.lower() and len(nums) >= 2:
        return nums[0], nums[0], nums[1], math.pi / 4
    if 'square' in text.lower() and len(nums) >= 2:
        return nums[0], nums[0], nums[1], 1
    if len(nums) >= 3:
        # Axis order does not affect area/volume. Retain the source order.
        return *nums[:3], 1
    raise ValueError('Three dimensions are needed to calculate a cost.')


def finish_defaults(name, material):
    # Names describe the agreed option. Historic material prose often lists
    # other colours in a composite effect and must not triple-charge them.
    text = name.lower()
    chosen = []
    if 'gold' in text:
        # Owner's production default. Genuine leaf remains an explicit editable
        # alternative; historical material descriptions are not cost selections.
        chosen.append('gold_imitation')
    if 'verdigris' in text: chosen.append('verdigris')
    if 'rust' in text: chosen.append('rust')
    if 'copper' in text and not 'verdigris' in text: chosen.append('copper')
    if any(w in text for w in ('bronze', 'pewter', 'silver', 'brass')): chosen.append('metallic')
    if 'marbl' in text or 'world colours' in text or 'black and white' in text: chosen.append('marbled')
    if not chosen and any(w in text for w in ('terracotta', 'beige', 'cream', 'pink', 'brown', 'blue', 'green', 'yellow')):
        chosen.append('pigment')
    if not chosen: return [{'id': 'white', 'coverage': 1}]
    # Mixed finishes share the face by default. Coverage is independently editable
    # (including overlapping layers), rather than charging every finish in full.
    fraction = 0.5 if 'white and gold' in text else 1 / len(chosen)
    return [{'id': key, 'coverage': fraction} for key in chosen]


def default_inputs(product, reviews):
    f = values(product, reviews)
    width, height, depth, shape = dimensions(f.get('Dimensions / depth', ''))
    name = f.get('Name') or product['name']
    area = width * height * shape
    freestanding = 'freestanding' in f.get('Fixing', '').lower() or 'fountain block' in f.get('Dimensions / depth', '').lower()
    count = 0 if freestanding else 1 if area <= 900 and max(width, height) <= 35 else max(2, 2*math.ceil(area/7200))
    factor = 1
    notes = 'GFRC production scenario; recorded sculpture material is preserved separately. Dimensions use the midpoint of any range. Relative casting volume assumes similar relief construction to the Dune Ripple baseline. Fixing quantities are costing allowances, not a load rating.'
    if freestanding:
        # Hollow bodies cannot be priced as a solid external bounding box.
        weight = re.findall(r'\d+(?:\.\d+)?', f.get('Weight', ''))
        if weight: factor = (float(weight[0]) / 4) / (area * depth / 4200)
        notes += ' Hollow/freestanding body: casting volume factor calibrated to recorded dry mass / 4 kg reference mass; excludes pump, plumbing and installation.'
    extra = 25 if product.get('family') == 'Wall Circle' else 150 if product['id'] == 'BSI-123AABD474C1' else 0
    if extra: notes += ' Other parts allowance: ' + ('RGB lighting kit £25; installation excluded.' if extra == 25 else 'support framework £150; fabrication quote not obtained.')
    return {'width_cm': width, 'height_cm': height, 'depth_cm': depth, 'shape_factor': shape,
            'casting_factor': factor, 'material': 'gfrc', 'finishes': finish_defaults(name, f.get('Material / finish', '')),
            'fixing_count': count, 'labour_hours_override': None, 'other_cost': extra, 'notes': notes}


def validate_inputs(data, config):
    keys = {'width_cm','height_cm','depth_cm','shape_factor','casting_factor','material','finishes','fixing_count','labour_hours_override','other_cost','notes'}
    optional = {'pricing_mode', 'markup_percent'}
    if not isinstance(data, dict) or not keys <= set(data) or set(data) - keys - optional:
        raise ValueError('Cost inputs are incomplete or contain unknown fields.')
    if data.get('pricing_mode', 'default') not in ('default', 'fixed', 'markup'):
        raise ValueError('Choose the shared pricing method, a fixed price or markup pricing.')
    if data.get('markup_percent') is not None:
        number(data['markup_percent'], 'Markup', 0, 10000)
    for key in ('width_cm', 'height_cm', 'depth_cm'): number(data[key], key, .01, 10000)
    for key in ('shape_factor', 'casting_factor'): number(data[key], key, .000001, 100)
    number(data['fixing_count'], 'Fixing quantity', 0, 1000)
    if int(data['fixing_count']) != data['fixing_count']: raise ValueError('Fixing quantity must be a whole number.')
    if data['labour_hours_override'] is not None: number(data['labour_hours_override'], 'Labour hours', 0, 10000)
    number(data['other_cost'], 'Other parts')
    if not isinstance(data['material'], str) or data['material'] not in config['materials']: raise ValueError('Unknown material.')
    if not isinstance(data['finishes'], list) or not 1 <= len(data['finishes']) <= 30: raise ValueError('Choose at least one finish.')
    seen = set()
    for finish in data['finishes']:
        if not isinstance(finish, dict) or set(finish) != {'id', 'coverage'} or not isinstance(finish['id'], str) or finish['id'] not in config['finishes'] or finish['id'] in seen:
            raise ValueError('Unknown or repeated finish.')
        seen.add(finish['id']); number(finish['coverage'], 'Finish coverage', 0, 5)
    if not isinstance(data['notes'], str) or len(data['notes']) > 10000: raise ValueError('Invalid cost notes.')
    return deepcopy(data)


def calculate(inputs, config):
    validate_inputs(inputs, config)
    area = inputs['width_cm'] * inputs['height_cm'] * inputs['shape_factor']
    face = area / (config['reference_width_cm'] * config['reference_height_cm'])
    volume = face * inputs['depth_cm'] / config['reference_depth_cm'] * inputs['casting_factor']
    material = config['materials'][inputs['material']]
    material_cost = money(volume * material['rate'])
    finish_lines = [{'id': f['id'], 'label': config['finishes'][f['id']]['label'], 'coverage': f['coverage'],
                     'cost': money(config['finishes'][f['id']]['rate'] * face * f['coverage'])} for f in inputs['finishes']]
    finish_cost = money(sum(f['cost'] for f in finish_lines))
    fixings = money(inputs['fixing_count'] * config['fixing_unit'])
    overhead = money(config['overhead_reference'] * max(1, math.sqrt(face)))
    hours = inputs['labour_hours_override']
    if hours is None:
        hours = ((config['casting_minutes'] + material['minutes']) * max(.5, math.sqrt(volume)) +
                 sum(config['finishes'][f['id']]['minutes'] * face * f['coverage'] for f in inputs['finishes']) +
                 inputs['fixing_count'] * config['fixing_minutes']) / 60
    labour = money(hours * config['labour_hourly'])
    subtotal = money(material_cost + finish_cost + fixings + overhead + inputs['other_cost'])
    return {'area_cm2': area, 'face_scale': face, 'casting_scale': volume, 'material_label': material['label'],
            'material_cost': material_cost, 'finish_cost': finish_cost, 'finish_lines': finish_lines,
            'fixing_cost': fixings, 'overhead_cost': overhead, 'other_cost': inputs['other_cost'],
            'labour_hours': hours, 'labour_cost': labour, 'manufacturing_cost': subtotal,
            'subtotal_before_labour': subtotal,
            'total_cost': money(subtotal + labour)}


def pricing(inputs, config, total_cost=None, fixed_value='', price_omitted=False):
    mode = inputs.get('pricing_mode', 'default')
    mode = config.get('default_pricing_mode', 'fixed') if mode == 'default' else mode
    percent = inputs.get('markup_percent')
    if percent is None:
        percent = config.get('default_markup_percent', 100)
    amount = None if total_cost is None else money(Decimal(str(total_cost)) * (1 + Decimal(str(percent)) / 100))
    value = ('' if amount is None else f'£{amount:,.2f}') if mode == 'markup' else fixed_value
    if price_omitted:
        value = None
    return {'mode': mode, 'markup_percent': percent, 'marked_up_price': amount,
            'markup_amount': None if amount is None else money(amount - total_cost),
            'listing_value': value, 'fixed_value': fixed_value, 'price_omitted': price_omitted,
            'uses_shared_markup': inputs.get('markup_percent') is None,
            'uses_shared_method': inputs.get('pricing_mode', 'default') == 'default'}


def priced_listing_value(field, choice, cost):
    # Omitting a price is still an explicit review choice. Missing cost inputs
    # must not silently fall back to the retained fixed price in markup mode.
    if field['key'] == 'Price' and choice.get('decision') != 'exclude' and cost.get('pricing', {}).get('mode') == 'markup':
        return cost['pricing']['listing_value']
    return listing_value(field, choice)


def product_cost(product, reviews, config=None):
    config, config_version = settings(reviews) if config is None else config
    record = next((r for r in reviews if (r['kind'], r['product_id'], r['item_id']) == ('cost', product['id'], '')), {})
    saved_inputs = record.get('data') or {}
    fixed_value = values(product, reviews).get('Price', '') if product.get('fields') else ''
    omitted = any(r['kind'] == 'field' and r['product_id'] == product['id'] and r['item_id'] == 'Price' and r['data'].get('decision') == 'exclude' for r in reviews)
    try:
        inputs = {'pricing_mode': 'default', 'markup_percent': None, **(saved_inputs or default_inputs(product, reviews))}
        result = calculate(inputs, config)
        return {'status': 'calculated', 'version': record.get('version', 0), 'settings_version': config_version,
                'inputs': inputs, **result, 'pricing': pricing(inputs, config, result['total_cost'], fixed_value, omitted),
                'alternatives': {key: money(result['total_cost'] - result['material_cost'] - result['labour_cost'] +
                    calculate({**inputs, 'material': key}, config)['material_cost'] + calculate({**inputs, 'material': key}, config)['labour_cost'])
                    for key in config['materials']}}
    except ValueError as error:
        return {'status': 'needs_inputs', 'message': str(error), 'version': record.get('version', 0),
                'settings_version': config_version, 'pricing': pricing(saved_inputs, config, fixed_value=fixed_value, price_omitted=omitted)}
