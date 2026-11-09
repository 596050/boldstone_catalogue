"""Retained, explicit Mac mini Docker / source-host authenticated HTTPS smoke.

Run prepare on the source; copy worker.json, tokens, CA and wheel to the fresh
Mini directory. Serve on the source and forward Mini 18443 to source 18443;
forward source 18766 to Mini 8767. Run verify on the source. Synthetic data only.
"""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE))
from research_workflows.client import Client, verify_collection
from research_workflows.common import atomic, load
from research_workflows.data_references import prepare_reference
from research_workflows.planner import plan
from research_workflows.simulation import configuration

ROOT = PACKAGE / '.source-state/data-reference-live-20260913-v2'
REMOTE = Path('/Users/tomprice/marketmaker-offload/data-reference-live-20260913-v2')
IMAGE = 'sha256:0eef8d6fc298a7fed3f8c15eba82e0f84fbd5ff4b31dc382da8f923d4da6654d'


def prepare():
    from tests.test_research_batches import native_fixture
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Capsule capture must be outside its source checkout. The compiled sealed
    # objects and raw-data object remain retained under ROOT after staging ends.
    with tempfile.TemporaryDirectory(prefix='offload-data-ref-capsule-') as temporary:
        native, raw, _ = native_fixture(Path(temporary))
        (raw / 'cases.jsonl').write_text(''.join(json.dumps({'input': n, 'target': 'yes' if n % 10 else 'no'})
                                               + '\n' for n in range(100)))
        ref = prepare_reference(raw, ROOT / 'data', source='source-prices', object_key='object.tar.gz')
        native.update(submission_id='mini-data-reference-stages-20260913-v1')
        native['candidates'] = native['candidates'][:1]
        native['candidates'][0].pop('prepare')
        native['defaults']['inputs']['prepared'] = ref
        native['metadata'] = {'synthetic_only': True, 'source_host_https_acquisition': True,
                              'performance_qualification': 'NOT_ESTABLISHED'}
        plan(native, ROOT / 'plan')
    for filename in ('source-token', 'worker-token'):
        with os.fdopen(os.open(ROOT / filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as out:
            out.write(secrets.token_urlsafe(32))
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-keyout', str(ROOT / 'tls-key.pem'), '-out', str(ROOT / 'ca.pem'),
                    '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    config = configuration(IMAGE)
    config['runtimes']['python'].update(timeout_s=180, memory_mb=1024, max_work_mb=256, max_output_mb=64)
    config['capacity'].update(memory_mb=2048, max_work_mb=512)
    config['input_transport'] = 'docker-volume'
    config['data_sources'] = {'source-prices': {
        'type': 'https', 'base_url': 'https://localhost:18443/objects',
        'ca_file': str(REMOTE / 'ca.pem'), 'bearer_token_file': str(REMOTE / 'source-token')}}
    atomic(ROOT / 'worker.json', {'root': 'state', 'token_file': 'worker-token', 'port': 8767,
                                  'concurrency': 1, 'max_pending': 8, 'max_store_mb': 2048,
                                  'min_free_mb': 20480, 'templates': {}, 'workflows': config})
    print(json.dumps({'prepared': str(ROOT), 'data_reference': ref}))


def serve():
    archive = ROOT / 'data/object.tar.gz'
    token = (ROOT / 'source-token').read_text()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            print(format % args, flush=True)  # No headers/credentials are logged.
        def do_GET(self):
            if self.headers.get('Authorization') != 'Bearer ' + token:
                self.send_error(401)
                return
            if self.path != '/objects/object.tar.gz':
                self.send_error(404)
                return
            body = archive.read_bytes()
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 18443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(ROOT / 'ca.pem', ROOT / 'tls-key.pem')
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print('Synthetic authenticated HTTPS source ready on loopback 18443', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def verify(suffix=''):
    if (ROOT / ('result' + suffix)).exists() or (ROOT / ('LIVE_RESULT' + suffix + '.json')).exists():
        raise RuntimeError('Use a fresh retained smoke attempt suffix')
    client = Client('http://127.0.0.1:18766', (ROOT / 'worker-token').read_text(), timeout=300)
    workflow = load(ROOT / 'plan/WORKFLOW.json')
    admission = client.submit_plan(ROOT / 'plan')
    status = client.wait_workflow(workflow['submission_id'], deadline=300, interval=1)
    atomic(ROOT / ('STATUS' + suffix + '.json'), status)
    collection = client.collect(workflow['submission_id'], ROOT / ('result' + suffix), max_bytes=256 << 20)
    verification = verify_collection(ROOT / ('result' + suffix), max_bytes=256 << 20)
    node = status['nodes'][0]
    output = node['outputs']
    report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'host': 'toms-mac-mini.local',
              'transport': 'SSH forwarding plus authenticated HTTPS source on origin host',
              'backend': output['execution']['receipt']['backend'],
              'state': status['state'], 'native_result': output.get('native_result'),
              'data_references': output['data_references'], 'collection': collection,
              'verification': verification, 'admission_workflow': admission['workflow_id'],
              'real_market_data_used': False, 'existing_queue_modified': False}
    atomic(ROOT / ('LIVE_RESULT' + suffix + '.json'), report)
    assert status['state'] == 'completed' and report['backend'] == 'docker', status
    assert output['native_result']['statistical_verdict'] == 'SUPPORTED', status
    assert output['data_references']['prepared']['location_accessed'] is True
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'serve', 'verify'))
    parser.add_argument('--suffix', default='', choices=('', '-release'))
    args = parser.parse_args()
    if args.action == 'verify':
        verify(args.suffix)
    else:
        globals()[args.action]()
