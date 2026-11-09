"""Read individual centimetre dimensions without treating counts as dimensions."""
import math
import re


NUMBER = r'[-+]?(?:\d+(?:\.\d+)?|\.\d+)'
RANGE = NUMBER + r'(?:\s*[–−-]\s*' + NUMBER + r')?'
UNIT = r'(?:millimetres?|millimeters?|centimetres?|centimeters?|mm|cm|metres?|meters?|m|inches|inch|in\.?|feet|foot|ft\.?|["″\'′])'
QUANTITY = re.compile(
    r'(?<![\w.])(?P<low>' + NUMBER + r')(?:\s*[–−-]\s*(?P<high>' + NUMBER + r'))?'
    r'\s*(?P<unit>' + UNIT + r'(?![a-z]))?', re.I)
AXIS = r'(?:wide|width|high|height|deep|depth|long|length)'
CHAIN = re.compile(RANGE + r'\s*(?:' + UNIT + r')?\s*(?:' + AXIS + r')?\s*[x×]\s*' + RANGE, re.I)
SHAPE = re.compile(RANGE + r'\s*(?:' + UNIT + r')?\s*(diameter|square)\b', re.I)
PREFIX_SHAPE = re.compile(r'\b(diameter|square)\b\s*[:=]?\s*' + RANGE, re.I)
AXES = {'wide': 'width', 'width': 'width', 'high': 'height', 'height': 'height',
        'deep': 'depth', 'depth': 'depth', 'long': 'length', 'length': 'length'}


def labelled_axis(text, quantity):
    """Return an attached dimension label and the start of its phrase."""
    suffix = re.match(r'\s*(?:side |panel |body )?(' + AXIS + r')\b', text[quantity.end():], re.I)
    if suffix:
        # "2 high relief panels" is a sale count, not a height. An explicit
        # unit or a delimiter after the axis distinguishes a dimension label.
        after = text[quantity.end() + suffix.end():]
        if quantity.group('unit') or re.match(r'\s*(?:[x×,;()/]|$)', after):
            return AXES[suffix.group(1).lower()], quantity.start()
    prefix = re.search(r'\b(' + AXIS + r')\s*[:=]?\s*$', text[:quantity.start()], re.I)
    if prefix:
        return AXES[prefix.group(1).lower()], prefix.start()
    return None, quantity.start()


def shape_phrases(text):
    for pattern in (SHAPE, PREFIX_SHAPE):
        for match in pattern.finditer(text):
            if pattern is SHAPE:
                quantity = QUANTITY.match(text, match.start())
                following = text[match.end():]
                # "2 square panels" counts objects; it does not say they are
                # two centimetres wide. Unitless shape dimensions must end or
                # continue with a separator rather than a following noun.
                if (not quantity.group('unit') and re.match(r'\s+[a-z]', following, re.I)
                        and not re.match(r'\s*(?:x|by)\b', following, re.I)):
                    continue
            yield match


def dimensions(text, *, upper=False):
    text = str(text)
    # ASCII x is a dimension separator even without spaces. Normalize just
    # numeric quantities, leaving x characters inside names/prose untouched.
    text = re.sub(r'(\d\s*(?:' + UNIT + r')?)\s*x\s*(?=[-+.\d])',
                  lambda match: match.group(1) + ' × ', text, flags=re.I)
    # Later framework/arrangement measurements belong to another object. Keep
    # them out of both the cost calculation and shipping package estimate.
    for match in re.finditer(r'\b(?:framework|arrangement)\b', text, re.I):
        if QUANTITY.search(text[:match.start()]):
            text = text[:match.start()]
            break
    candidates = [match.start() for match in shape_phrases(text)]
    if match := CHAIN.search(text):
        candidates.append(match.start())
    for quantity in QUANTITY.finditer(text):
        axis, start = labelled_axis(text, quantity)
        if axis:
            candidates.append(start)
    if candidates:
        text = text[min(candidates):]
    matches = list(QUANTITY.finditer(text))
    shape = next((match for match in shape_phrases(text) if match.start() == 0), None)
    needed = 2 if shape else 3
    if len(matches) < needed:
        raise ValueError('Three dimensions are needed; use centimetres for the individual sculpture.')

    def value(match):
        unit = match.group('unit')
        if unit and unit.lower() not in ('cm', 'centimetre', 'centimetres', 'centimeter', 'centimeters'):
            raise ValueError('Use centimetres for the individual sculpture dimensions.')
        ends = [float(match.group('low')), float(match.group('high') or match.group('low'))]
        if any(not math.isfinite(end) or end <= 0 for end in ends):
            raise ValueError('Dimensions must be positive finite numbers.')
        return max(ends) if upper else sum(ends) / 2

    selected = matches[:needed]
    nums = [value(match) for match in selected]
    if shape:
        return nums[0], nums[0], nums[1], math.pi / 4 if shape.group(1).lower() == 'diameter' else 1
    # Width/height/depth can be written in any order. Recognize labels attached
    # to these first three quantities, rather than picking a later framework.
    labelled = {}
    for match, number in zip(selected, nums):
        axis, _ = labelled_axis(text, match)
        if axis:
            labelled[axis] = number
    face = [labelled[axis] for axis in ('width', 'height', 'length') if axis in labelled]
    if 'depth' in labelled and len(face) == 2:
        nums = [*face, labelled['depth']]
    return *nums, 1
