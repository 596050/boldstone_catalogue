"""UK parcel quotes from Royal Mail's published retail Tracked 48 tariff.

No booking, payment, account credentials or customer data are sent upstream.
An unreadable or changed page must never overwrite a verified tariff.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import math
import os
import re
import tempfile
import threading
import urllib.error
import urllib.request

SOURCE_URL = 'https://www.royalmail.com/sending/uk/tracked-48'
GUIDE_URL = 'https://www.royalmail.com/sites/royalmail.com/files/2026-09/online-price-guide-october-2026-v1-ta.pdf'
DAY = 24 * 60 * 60
# Verified against the service page and the online guide, effective 5 October.
SEED = {
    'schema': 1, 'service': 'Royal Mail Tracked 48', 'currency': 'GBP',
    'source_url': SOURCE_URL, 'guide_url': GUIDE_URL,
    'verified_at': '2026-10-30T18:55:29+00:00', 'effective_date': '2026-10-05',
    'verification': 'Published service page and online price guide checked manually',
    'collection_pence': 50, 'compensation_gbp': 75,
    'tiers': [
        {'id': 'small_2', 'label': 'Small parcel up to 2 kg', 'max_kg': 2, 'max_cm': [45, 35, 16], 'pence': 375},
        {'id': 'medium_2', 'label': 'Medium parcel up to 2 kg', 'max_kg': 2, 'max_cm': [61, 46, 46], 'pence': 570},
        {'id': 'medium_10', 'label': 'Medium parcel up to 10 kg', 'max_kg': 10, 'max_cm': [61, 46, 46], 'pence': 755},
        {'id': 'medium_20', 'label': 'Medium parcel up to 20 kg', 'max_kg': 20, 'max_cm': [61, 46, 46], 'pence': 1225},
    ],
}


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('A timezone is required')
    return result


def validate_package(data):
    keys = {'length_cm', 'width_cm', 'depth_cm', 'weight_kg', 'packaging_gbp', 'collection', 'destination'}
    if not isinstance(data, dict) or set(data) != keys:
        raise ValueError('Enter the packed dimensions, weight, destination and delivery options.')
    result = data.copy()
    for key in ('length_cm', 'width_cm', 'depth_cm', 'weight_kg', 'packaging_gbp'):
        value = data[key]
        maximum = 1000 if key == 'weight_kg' else 10000
        if type(value) not in (int, float) or not math.isfinite(value) or value > maximum or (value < 0 if key == 'packaging_gbp' else value <= 0):
            raise ValueError('Use a valid positive packed size and weight, and a non-negative packaging charge.')
        if key == 'packaging_gbp':
            result[key] = float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    if type(data['collection']) is not bool or data['destination'] not in ('uk', 'international'):
        raise ValueError('Choose a delivery destination and collection option.')
    return result


def validate_tariff(value):
    if not isinstance(value, dict) or value.get('schema') != 1 or value.get('source_url') != SOURCE_URL or value.get('currency') != 'GBP' or value.get('service') != SEED['service']:
        raise ValueError('Unrecognised tariff')
    stamp(value['verified_at'])
    if [t.get('id') for t in value.get('tiers', [])] != [t['id'] for t in SEED['tiers']]:
        raise ValueError('Incomplete tariff')
    for row, expected in zip(value['tiers'], SEED['tiers']):
        if row.get('max_kg') != expected['max_kg'] or row.get('label') != expected['label']:
            raise ValueError('Parcel bands changed; manual tariff review is required.')
        dims = row.get('max_cm')
        if not isinstance(dims, list) or len(dims) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 or x > 200 for x in dims) or sorted(dims, reverse=True) != dims:
            raise ValueError('Invalid parcel dimensions')
        if type(row.get('pence')) is not int or not 1 <= row['pence'] <= 100000:
            raise ValueError('Invalid postage amount')
    if any(t['max_cm'] != value['tiers'][1]['max_cm'] for t in value['tiers'][2:]):
        raise ValueError('Conflicting medium parcel dimensions')
    if [t['pence'] for t in value['tiers']] != sorted(t['pence'] for t in value['tiers']):
        raise ValueError('Unexpected price ordering')
    if type(value.get('collection_pence')) is not int or not 0 <= value['collection_pence'] <= 10000:
        raise ValueError('Invalid collection fee')
    if type(value.get('compensation_gbp')) not in (int, float) or not 0 <= value['compensation_gbp'] <= 10000:
        raise ValueError('Invalid compensation value')
    return deepcopy(value)


def quote(data, tariff):
    data = validate_package(data)
    dims = sorted((data['length_cm'], data['width_cm'], data['depth_cm']), reverse=True)
    base = {'inputs': data, 'service': tariff['service'], 'currency': 'GBP',
            'tariff_verified_at': tariff['verified_at'], 'source_url': SOURCE_URL}
    if data['destination'] != 'uk':
        return {**base, 'status': 'separate_quote', 'message': 'International delivery needs a separate quote.'}
    for tier in tariff['tiers']:
        if data['weight_kg'] <= tier['max_kg'] and all(a <= b for a, b in zip(dims, tier['max_cm'])):
            collection = tariff['collection_pence'] if data['collection'] else 0
            packaging = int(Decimal(str(data['packaging_gbp'])) * 100)
            return {**base, 'status': 'calculated', 'tier': deepcopy(tier),
                    'postage_pence': tier['pence'], 'collection_pence': collection,
                    'packaging_pence': packaging, 'total_pence': tier['pence'] + collection + packaging}
    return {**base, 'status': 'separate_quote', 'message': 'This packed parcel exceeds the Royal Mail size or weight limits. Arrange a separate courier quote.'}


class Page(HTMLParser):
    """Read visible text and expand standard table spans without a browser."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.tables = [], []
        self.table = self.row = self.cell = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'table':
            if self.table is not None:
                raise ValueError('Nested price table needs review')
            self.table = []
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in ('th', 'td') and self.row is not None:
            attrs = dict(attrs)
            self.cell = {'text': [], 'cols': int(attrs.get('colspan', 1)), 'rows': int(attrs.get('rowspan', 1))}
            if not 1 <= self.cell['cols'] <= 20 or not 1 <= self.cell['rows'] <= 20:
                raise ValueError('Invalid table spans')

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)
            if self.cell is not None:
                self.cell['text'].append(data)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        elif self.hidden:
            return
        elif tag in ('th', 'td') and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            expanded, spans = [], {}
            for cells in self.table:
                row, column = [], 0
                def inherited():
                    nonlocal column
                    while column in spans:
                        text, remaining = spans[column]
                        row.append(text)
                        if remaining == 1:
                            del spans[column]
                        else:
                            spans[column] = (text, remaining - 1)
                        column += 1
                for cell in cells:
                    inherited()
                    text = re.sub(r'\s+', ' ', ' '.join(cell['text'])).strip()
                    for _ in range(cell['cols']):
                        row.append(text)
                        if cell['rows'] > 1:
                            spans[column] = (text, cell['rows'] - 1)
                        column += 1
                inherited()
                expanded.append(row)
            self.tables.append(expanded)
            self.table = None


def parse_page(html, checked_at):
    page = Page()
    page.feed(html)
    text = re.sub(r'\s+', ' ', ' '.join(page.text))
    candidates = []
    for table in page.tables:
        if not any('Tracked 48' in ' '.join(row) for row in table):
            continue
        for i, header in enumerate(table):
            if [c.lower().strip() for c in header] != ['size', 'weight up to and including', 'price', 'online price', 'price', 'online price']:
                continue
            prices = {}
            for row in table[i + 1:]:
                if len(row) != 6 or row[0].lower() not in ('small parcel', 'medium parcel'):
                    continue
                weight = re.fullmatch(r'(2|10|20)\s*kg', row[1], re.I)
                money = re.fullmatch(r'£\s*(\d+\.\d{2})', row[3])
                if not weight or not money:
                    raise ValueError('The online parcel price table changed')
                key = ('small' if row[0].lower().startswith('small') else 'medium') + '_' + weight[1]
                if key in prices:
                    raise ValueError('Ambiguous price table')
                prices[key] = int(Decimal(money[1]) * 100)
            if set(prices) == {t['id'] for t in SEED['tiers']}:
                candidates.append(prices)
    if len(candidates) != 1:
        raise ValueError('Could not verify all four online Tracked 48 parcel prices')
    result = deepcopy(SEED)
    for size, max_kg in (('Small', 2), ('Medium', 20)):
        pattern = rf'{size}\s+parcel\s+Max\s+{max_kg}\s*kg\s*\|?\s*Max\s+L\s*([\d.]+)\s*cm\s*x\s*W\s*([\d.]+)\s*cm\s*x\s*D\s*([\d.]+)\s*cm'
        found = re.findall(pattern, text, re.I)
        if len(found) != 1:
            raise ValueError('Could not verify parcel size limits')
        for row in result['tiers']:
            if row['id'].startswith(size.lower()):
                row['max_cm'] = [float(v) for v in found[0]]
    fee = set(re.findall(r'just\s+(\d+)p\s+per\s+item', text, re.I))
    compensation = re.findall(r'Compensation cover up to\s*£(\d+)', text, re.I)
    if len(fee) != 1 or len(compensation) != 1 or 'Prices include VAT' not in text:
        raise ValueError('Could not verify collection, compensation or VAT details')
    for row in result['tiers']:
        row['pence'] = candidates[0][row['id']]
    result.update(collection_pence=int(fee.pop()), compensation_gbp=int(compensation[0]),
                  verified_at=checked_at, effective_date=None, verification='Automatic public service page check',
                  page_sha256=hashlib.sha256(html.encode()).hexdigest())
    return validate_tariff(result)


class OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlparse
        parsed = urlparse(newurl)
        if parsed.scheme != 'https' or parsed.netloc != 'www.royalmail.com':
            raise ValueError('Royal Mail redirected to an unexpected site')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page():
    request = urllib.request.Request(SOURCE_URL, headers={'User-Agent': 'BoldstoneCatalogue/1.0 (published tariff checker)', 'Accept': 'text/html'})
    with urllib.request.build_opener(OfficialRedirects()).open(request, timeout=15) as response:
        if response.headers.get_content_type() != 'text/html':
            raise ValueError('Royal Mail did not return an HTML service page')
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('Royal Mail page exceeded the size limit')
        return data.decode('utf-8')


class Tariffs:
    def __init__(self, root, fetch=fetch_page, now=utcnow):
        self.path = Path(root) / 'royal-mail-tariff.json'
        self.fetch, self.now = fetch, now
        self.lock, self.refresh_lock = threading.RLock(), threading.Lock()
        self.tariff, self.attempt, self.refreshing = deepcopy(SEED), None, False
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                self.tariff = validate_tariff(saved['tariff'])
                attempt = saved.get('attempt')
                if attempt:
                    stamp(attempt['at'])
                    if attempt.get('status') not in ('ok', 'failed'):
                        raise ValueError('Invalid saved refresh')
                    self.attempt = attempt
            except (ValueError, KeyError, TypeError, OSError):
                self.tariff = deepcopy(SEED)
                self.attempt = {'at': self.now().isoformat(), 'status': 'failed', 'message': 'Saved tariff could not be read. Using the bundled verified rates; check Royal Mail before quoting.'}

    def snapshot(self):
        with self.lock:
            age = max(0, (self.now() - stamp(self.tariff['verified_at'])).total_seconds())
            return {'tariff': deepcopy(self.tariff), 'last_attempt': deepcopy(self.attempt),
                    'refreshing': self.refreshing, 'stale': age > DAY,
                    'needs_confirmation': age > DAY or bool(self.attempt and self.attempt['status'] == 'failed'),
                    'refresh_interval_hours': 24}

    def _persist(self, tariff, attempt):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.royal-mail-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump({'tariff': tariff, 'attempt': attempt}, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def refresh(self, force=False):
        if type(force) is not bool:
            raise ValueError('Invalid refresh option')
        if not self.refresh_lock.acquire(blocking=False):
            return self.snapshot()
        try:
            now = self.now()
            with self.lock:
                if self.attempt and (now - stamp(self.attempt['at'])).total_seconds() < (60 if force else DAY):
                    return self.snapshot()
                self.refreshing = True
                current = deepcopy(self.tariff)
            try:
                candidate = parse_page(self.fetch(), now.isoformat())
                attempt = {'at': now.isoformat(), 'status': 'ok', 'message': 'All four parcel prices, size limits and collection fee verified from Royal Mail.'}
            except urllib.error.HTTPError as error:
                candidate = current
                attempt = {'at': now.isoformat(), 'status': 'failed', 'message': f'Royal Mail blocked or declined the automatic check (HTTP {error.code}). Using the last verified rates; confirm them on Royal Mail before quoting.'}
            except Exception:
                candidate = current
                attempt = {'at': now.isoformat(), 'status': 'failed', 'message': 'Could not verify the complete Royal Mail tariff. Using the last verified rates; confirm them on Royal Mail before quoting.'}
            try:
                self._persist(candidate, attempt)
            except OSError:
                candidate = current
                attempt = {'at': now.isoformat(), 'status': 'failed', 'message': 'Could not save the tariff check on this Mac. Previous rates are retained.'}
            with self.lock:
                self.tariff, self.attempt, self.refreshing = candidate, attempt, False
            return self.snapshot()
        finally:
            with self.lock:
                self.refreshing = False
            self.refresh_lock.release()
