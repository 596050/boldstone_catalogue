"""Evidence-preserving product copy shared by channel export tools.

These helpers prepare content; they never assert stock or publish an offer.
"""
import html
import re

MATERIAL = 'Made from a gypsum-based material.'
SURFACE = 'A decorative surface effect is applied to create the finish shown.'
SURFACE_VARIATION = ('Each piece is handmade. The surface-effect pattern will vary '
                     'and will differ from the photographs.')
CUSTOMISATION = ('All designs can be customised. Completely new commissions can also '
                 'be created in collaboration with designer Sally Price.')
DISPATCH_EXCEPTIONS = (
    'Default: dispatch within 10 working days. Use 3 working days only where the '
    'platform requires it: applicable eBay Simple Delivery offers, Chairish parcel '
    'orders and Saatchi Art courier collection. '
    'TikTok: standard shipping may require 2 working days; keep inactive until '
    'the owner confirms that deadline or extended handling is enabled. '
    'Carrier transit time is additional.'
)


def values(product):
    return {f['key']: f.get('value') or '' for f in product['fields'] + product['listing_fields']}


def product_type(product):
    name = (product.get('name', '') + ' ' + product.get('retail_name', '')).lower()
    if 'water feature' in name or 'fountain' in name:
        return 'Sculptural water-feature panel'
    if 'paver' in name:
        return 'Decorative paver panel'
    if 'basin' in name or 'catcher' in name:
        return 'Sculptural relief'
    return 'Wall sculpture'


def finish_retail_name(product):
    """Keep an applied colour/effect visibly distinct from the base material."""
    f = values(product)
    name = f.get('Retail name') or product.get('retail_name') or product['name']
    if has_surface_effect(product) and not re.search(r'\bfinish\b', name, re.I):
        name = name.rstrip() + ' Finish'
    return name


def marketplace_title(product, limit=None):
    name = finish_retail_name(product)
    kind = product_type(product)
    title = 'Boldstone ' + name + ' ' + kind
    title = re.sub(r'\s+', ' ', title).strip()
    if limit and len(title) > limit:
        # Retain the brand and product type. Full model/finish remains in the
        # description and item specifics if the channel has a short title cap.
        room = limit - len('Boldstone ') - len(' ' + kind)
        if has_surface_effect(product):
            # A channel's title cap must not remove the material clarification.
            design, separator, finish = name.rpartition(' - ')
            suffix = separator + finish if separator else ' Finish'
            if len(suffix) >= room:
                raise ValueError('Title cap cannot retain the finish description')
            stem = design if separator else re.sub(r'\s+Finish$', '', name, flags=re.I)
            short = stem[:room - len(suffix)].rsplit(' ', 1)[0].rstrip(' -') + suffix
        else:
            short = name[:room].rsplit(' ', 1)[0].rstrip(' -')
        title = 'Boldstone ' + short + ' ' + kind
    return title


def appearance(product):
    finish = values(product).get('Material / finish', '')
    finish = re.sub(r'^Gypsum-based material\s+with\s+', '', finish, flags=re.I)
    # Describe an appearance, never imply stone or metal is the substrate.
    finish = re.sub(r'^a(?:n)?\s+', '', finish)
    return finish[:1].upper() + finish[1:]


def has_surface_effect(product):
    """Use recorded finishes, or an existing explicit effect statement.

    A sculpted pattern alone is not evidence of an applied surface effect.
    """
    finishes = product.get('costing', {}).get('inputs', {}).get('finishes')
    if finishes is not None:
        return any(finish['id'] != 'white' for finish in finishes)
    return bool(re.search(r'(?m)^Surface effect:', values(product).get('Description', '')))


def surface_variation_copy(text, surface_effect):
    """Idempotently maintain the owner-approved handmade finish disclosure."""
    text = text.replace(SURFACE_VARIATION, '').rstrip()
    text = re.sub(r'(?m)^Surface effect:[^\n]*',
                  lambda match: match.group(0).rstrip(), text)
    if not surface_effect:
        return text
    if re.search(r'(?m)^Surface effect:', text):
        return re.sub(r'(?m)^Surface effect:[^\n]*',
                      lambda match: match.group(0).rstrip() + ' ' + SURFACE_VARIATION,
                      text, count=1)
    point = 'Surface effect: ' + SURFACE + ' ' + SURFACE_VARIATION
    if re.search(r'(?m)^Material:[^\n]*', text):
        return re.sub(r'(?m)^Material:[^\n]*',
                      lambda match: match.group(0) + '\n' + point, text, count=1)
    return text + '\n' + point


def customisation_copy(text):
    text = re.sub(r'(?m)^Custom design:[^\n]*\n?', '', text).strip()
    point = 'Custom design: ' + CUSTOMISATION
    if re.search(r'(?m)^Dispatch time:', text):
        return re.sub(r'(?m)^Dispatch time:', point + '\nDispatch time:', text, count=1)
    return text + '\n' + point


def complete_description(product, sku, dispatch_days=10, channel='catalogue'):
    f = values(product)
    text = str(f.get('Description', '')).strip()
    if not text:
        raise ValueError('Missing design description for ' + product['id'])
    # Idempotent replacement of our structured lines, while preserving design
    # prose and the source dimensions/weight rather than silently estimating.
    labels = ('Brand', 'Product type', 'Model', 'Colour / appearance', 'Quantity supplied',
              'Dispatch time', 'Production lead time', 'Lead time')
    text = re.sub(r'(?m)^(?:' + '|'.join(re.escape(x) for x in labels) + r'):.*\n?', '', text)
    text = re.sub(r'(?m)^Material:.*$', 'Material: ' + MATERIAL, text)
    if 'Material: ' not in text:
        text += '\nMaterial: ' + MATERIAL
    header = [
        'Brand: Boldstone', 'Product type: ' + product_type(product),
        'Model: ' + finish_retail_name(product) + ' (' + sku + ')',
        'Colour / appearance: ' + appearance(product),
        'Quantity supplied: 1 individually described sculpture or panel. Other pieces and room props shown are not included.',
    ]
    text = text.replace('Material: ', '\n'.join(header) + '\nMaterial: ', 1)
    dispatch = f'Dispatch time: Within {dispatch_days} working days. Delivery transit time is additional.'
    if re.search(r'(?m)^Delivery:', text):
        text = re.sub(r'(?m)^Delivery:', dispatch + '\nDelivery:', text, count=1)
    else:
        text += '\n' + dispatch
    if product_type(product) == 'Sculptural water-feature panel' and 'pump' not in text.lower():
        text += '\nSupplied as one sculptural panel. Pump, basin, pipework and installation are not included.'
    if channel == 'tiktok':
        text = re.sub(r'(?m)^Delivery:.*$', 'Delivery: Available delivery options and charges are shown at checkout.', text)
    elif channel == 'ebay':
        text = re.sub(r'(?m)^Delivery:.*$',
                      'Delivery: The available delivery service and charge are shown in this eBay listing. '
                      'Carrier transit time is additional to dispatch time.', text)
    text = surface_variation_copy(text, has_surface_effect(product))
    text = customisation_copy(text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def description_html(text):
    out = []
    for block in text.split('\n\n'):
        lines = block.splitlines()
        if all(':' in line and len(line.split(':', 1)[0]) < 30 for line in lines):
            out.append('<ul>' + ''.join('<li><strong>' + html.escape(line.split(':', 1)[0]) +
                ':</strong>' + html.escape(line.split(':', 1)[1]) + '</li>' for line in lines) + '</ul>')
        else:
            out.append('<p>' + '<br>'.join(html.escape(line) for line in lines) + '</p>')
    return ''.join(out)


def chairish_description(record, dispatch_days=3):
    """Chairish requires prose rather than specification lists or public SKUs.

    This changes presentation only. Origin, production dates and signatures are
    deliberately not inferred; those must be supplied in the native fields.
    """
    if dispatch_days not in (3, 10):
        raise ValueError('Unsupported owner-approved dispatch allowance')
    source = record['description_text']
    introduction, separator, _ = source.partition('\nBrand:')
    if not separator:
        raise ValueError('Missing structured catalogue description')
    fields = dict(re.findall(r'(?m)^([^\n:]{1,35}):\s*([^\n]+)$', source))
    for key in ('Material', 'Dimensions', 'Weight', 'Use', 'Fixings'):
        if not fields.get(key):
            raise ValueError('Missing Chairish source fact: ' + key)
    if record.get('surface_effect') and not fields.get('Surface effect'):
        raise ValueError('Missing applied surface-effect statement')
    facts = [
        'This Boldstone ' + record.get('product_type', 'wall sculpture').lower() +
        ' is sold individually. Other sculptures and room props shown are not included.',
        fields['Material'],
    ]
    if fields.get('Surface effect'):
        facts.append(fields['Surface effect'])
        if record.get('surface_effect') and SURFACE_VARIATION not in fields['Surface effect']:
            facts.append(SURFACE_VARIATION)
    if fields.get('Companion pieces'):
        facts.append(fields['Companion pieces'])
    facts.append(fields.get('Custom design') or CUSTOMISATION)
    facts.extend([
        'The dimensions are ' + fields['Dimensions'].rstrip('.') + '.',
        'The stated weight is ' + fields['Weight'][:1].lower() + fields['Weight'][1:].rstrip('.') + '.',
        fields['Use'], fields['Fixings'],
    ])
    if 'Pump, basin, pipework and installation are not included.' in source:
        facts.append('Pump, basin, pipework and installation are not included.')
    facts.append(f'Dispatch is within {dispatch_days} working days. Delivery transit time is additional.')
    description = introduction.strip() + '\n\n' + ' '.join(facts)
    if record['sku'] in description or re.search(r'https?://', description):
        raise ValueError('Chairish prose contains a public SKU or external URL')
    return description


def saatchi_description(record, limit=1000):
    """Fit the native artwork field without truncating material or size facts.

    Saatchi's courier workflow uses the owner's three-day exception. A short
    description does not establish creation year, edition status or sale stock.
    """
    prose = chairish_description(record, dispatch_days=3)
    introduction, facts = prose.rsplit('\n\n', 1)
    colour = str(record.get('colour') or '').strip()
    if not colour:
        raise ValueError('Missing Saatchi colour / appearance')
    facts = 'Colour / appearance: ' + colour.rstrip('.') + '.\n' + facts
    paragraphs = introduction.split('\n\n')
    while paragraphs:
        result = '\n\n'.join(paragraphs) + '\n\n' + facts
        if 50 <= len(result) <= limit:
            return result
        # Shorten design prose by complete paragraphs only, retaining at least
        # the first design paragraph and every specification and exclusion.
        paragraphs.pop()
    # The native 1,000-character field cannot always hold the verbose catalogue
    # specifications plus owner disclosures. Compact their wording, preserving
    # dimensions, qualifications, finish variation, companions and commissions.
    fields = dict(re.findall(r'(?m)^([^\n:]{1,35}):\s*([^\n]+)$', record['description_text']))
    compact = ['Made from a gypsum-based material.', 'Colour: ' + colour.rstrip('.') + '.']
    if record.get('surface_effect'):
        compact.extend(['A decorative surface effect is applied.', SURFACE_VARIATION])
    if fields.get('Companion pieces'):
        companions = fields['Companion pieces'].partition(' with ')[2].partition('. Companion sculptures')[0]
        if not companions:
            raise ValueError('Unrecognised companion statement')
        compact.append('Companion pieces: ' + companions + ' (sold separately).')
    compact.extend(['Dimensions: ' + fields['Dimensions'].rstrip('.') + '.',
                    'Weight: ' + fields['Weight'].rstrip('.') + '.',
                    'Suitable for outdoor use and indoor display.',
                    'Usually keyhole fixings; French cleats and other options are available.',
                    'One sculpture supplied; other pieces and room props are not included.'])
    if 'Pump, basin, pipework and installation are not included.' in record['description_text']:
        compact.append('Pump, basin, pipework and installation are not included.')
    compact.extend(['All designs can be customised; completely new commissions can be created with designer Sally Price.',
                    'Dispatch within 3 working days; delivery transit time is additional.'])
    brief = ' '.join(compact)
    introduction = record['description_text'].partition('\nBrand:')[0].strip()
    sentences = re.split(r'(?<=[.!?])\s+', introduction)
    while sentences:
        result = ' '.join(sentences) + '\n\n' + brief
        if 50 <= len(result) <= limit:
            return result
        sentences.pop()
    raise ValueError('Required Saatchi copy exceeds the native character limit')


def validate(product, record):
    errors = []
    f = values(product)
    text = record['description_text']
    for key in ('Dimensions / depth', 'Weight', 'Material / finish'):
        if not f.get(key): errors.append('Missing ' + key)
    for label in ('Brand:', 'Product type:', 'Model:', 'Colour / appearance:', 'Quantity supplied:', 'Material:', 'Dispatch time:'):
        if label not in text: errors.append('Missing description field ' + label)
    if MATERIAL not in text: errors.append('Missing gypsum material statement')
    if record.get('surface_effect') and SURFACE not in text: errors.append('Missing surface-effect statement')
    if record.get('surface_effect') and SURFACE_VARIATION not in text: errors.append('Missing handmade surface-effect variation statement')
    if CUSTOMISATION not in text: errors.append('Missing Sally Price customisation statement')
    if not record.get('sku'): errors.append('Missing seller SKU')
    return errors
