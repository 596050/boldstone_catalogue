"""One bounded, create-only public-source capture; no broker authentication."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CENTRAL = Path('/Volumes/Toshiba 2TB/other_data/research/artifacts/native_evidence_retrieval_20261005_v1')
SOURCES = {
    'nyfed_api.yml': 'https://markets.newyorkfed.org/static/docs/markets-api.yml',
    'sofr.json': 'https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2018-04-02&endDate=2026-10-02',
    'ig_weekly_funding.html': 'https://www.ig.com/uk/help-and-support/articles/681700-overnight-funding-interest-rates-for-indices-shares-and-etfs',
    'ig_funding_method.html': 'https://www.ig.com/uk/help-and-support/articles/681712-what-is-overnight-funding-how-is-it-charged-and-how-is-it-calculated',
    'ig_legacy_costs.pdf': 'https://www.ig.com/usermanagement/customeragreements?agreementType=costs_and_charges&igCompany=iggb&locale=en_GB',
    'ig_ibor_transition_ie.html': 'https://www.ig.com/ie/the-ibor-transition-everything-you-need-to-know',
    'nyse_volume_201411.pdf': 'https://www.nyse.com/publicdocs/nyse/data/Monthly_Consolidated_Volume_by_Symbol_201411.pdf',
    'tickdata_us_equities.html': 'https://www.tickdata.com/product/us-equities/',
    'tickdata_delivery.html': 'https://www.tickdata.com/data-delivery/deep-history-data',
    'iqfeed_api.html': 'https://iqhelp.dtn.com/api/',
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(data)


def fetch(item):
    name, url = item
    rec = dict(name=name, url=url, requested_at=stamp(), historical_receipt=False)
    req = urllib.request.Request(url, headers={'User-Agent': 'Marketmaker source research/1.0', 'Accept-Encoding': 'identity'})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read(12 * 1024 * 1024 + 1)
            if len(body) > 12 * 1024 * 1024:
                raise ValueError('bounded_response_limit')
            rec.update(http_status=r.status, final_url=r.url,
                       headers={k:r.headers.get(k) for k in ('Date','Last-Modified','ETag','Content-Type')},
                       bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        path = CENTRAL / 'public' / name
        write(path, body)
        rec.update(status='CAPTURED', path=str(path))
        if name.endswith('.pdf') and not body.startswith(b'%PDF-'):
            rec['status'] = 'UNEXPECTED_CONTENT'
        if name == 'sofr.json':
            data = json.loads(body)
            rows = data['refRates']
            dates = [x['effectiveDate'] for x in rows]
            rec['coverage'] = dict(rows=len(rows), unique_dates=len(set(dates)),
                                   first=min(dates), last=max(dates), types=sorted({x['type'] for x in rows}))
            rec['applicability'] = 'CURRENT_VINTAGE_BENCHMARK_ONLY_NOT_IG_CHARGES_OR_HISTORICAL_DELIVERY'
    except Exception as exc:
        rec.update(status='FAILED', error_type=type(exc).__name__)
        if isinstance(exc, urllib.error.HTTPError):
            rec['http_status'] = exc.code
    rec['completed_at'] = stamp()
    return rec


def main():
    if CENTRAL.exists():
        raise SystemExit('Create-only capture already exists')
    CENTRAL.mkdir(parents=True, mode=0o700)
    with ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(pool.map(fetch, SOURCES.items()))
    record = dict(observed_at=stamp(), source_role='SUPPORTING_ACQUISITION_NOT_CANDIDATE',
                  no_broker_authentication=True, no_purchase=True, no_external_messages=True,
                  clock_note='Capture time is current retrieval time, never historical customer receipt time.',
                  receipts=receipts)
    data = (json.dumps(record, indent=2, sort_keys=True) + '\n').encode()
    write(HERE / 'PUBLIC_CAPTURE.json', data)
    write(CENTRAL / 'PUBLIC_CAPTURE.json', data)
    for rec in receipts:
        print(json.dumps({k:rec[k] for k in ('name','status','http_status','bytes','coverage') if k in rec}))


if __name__ == '__main__':
    main()
