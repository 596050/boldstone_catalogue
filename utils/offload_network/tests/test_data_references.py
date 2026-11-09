"""Pinned references: real local HTTPS/filesystem I/O, isolated test stores only."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import threading

import pytest

from offload_service.http_api import Server
from research_workflows import batch
from research_workflows.client import Client, verify_collection
from research_workflows.common import load, sha
from research_workflows.data_references import DataSources, DataUnavailable, prepare_reference, source_profiles
from research_workflows.objects import ObjectStore
from research_workflows.planner import plan
from research_workflows.simulation import configuration
from research_workflows.spec import SCHEMA, validate
from research_workflows.worker import WorkflowWorker


@pytest.fixture
def data(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / 'values.json').write_text('{"values":[2,3,5]}\n')
    (raw / 'binary.dat').write_bytes(bytes(range(256)))
    reference = prepare_reference(raw, tmp_path / 'prepared', source='prices', object_key='v1/data.tar.gz')
    location = tmp_path / 'storage'
    (location / 'v1').mkdir(parents=True)
    archive = location / reference['key']
    shutil.copyfile(tmp_path / 'prepared/object.tar.gz', archive)
    store = ObjectStore(tmp_path / 'store', max_object_mb=4, max_store_mb=32, min_free_mb=1)
    return reference, archive, store, {'prices': {'type': 'filesystem', 'root': str(location)}}


def request(reference, code):
    return {'schema': SCHEMA, 'submission_id': 'reference-test', 'jobs': [{
        'id': 'consume', 'kind': 'producer', 'runtime': 'python',
        'capsule': {'source': str(code)}, 'entrypoint': 'main.py',
        'inputs': {'data': reference},
        'args': ['{input.data}/values.json', '{output.result}'],
        'outputs': {'result': {'type': 'json', 'path': 'artifacts/result.json'}},
    }]}


def test_local_reference_snapshot_cache_and_tamper(data):
    ref, archive, store, profiles = data
    resolver = DataSources(store, profiles)
    receipt = resolver.resolve(ref)
    assert not receipt['cache_hit'] and receipt['location_accessed']
    root, _ = store.get(ref['object_sha256'])
    assert load(root / 'data/values.json')['values'] == [2, 3, 5]
    assert (root / 'data/binary.dat').read_bytes() == bytes(range(256))
    archive.unlink()  # Deliberately remove this test fixture's remote copy.
    assert resolver.resolve(ref)['cache_hit']
    (root / 'data/values.json').write_text('changed')
    with pytest.raises(ValueError):
        resolver.resolve(ref)


def test_resume_verified_prefix(data):
    ref, archive, store, profiles = data
    store.begin(ref['object_sha256'], ref['archive_bytes'])
    store.append(ref['object_sha256'], 0, archive.read_bytes()[:17])
    assert not DataSources(store, profiles).resolve(ref)['cache_hit']
    assert store.get(ref['object_sha256'])[1]['files']


def test_complete_retained_prefix_does_not_claim_a_new_source_read(data):
    ref, archive, store, profiles = data
    store.begin(ref['object_sha256'], ref['archive_bytes'])
    store.append(ref['object_sha256'], 0, archive.read_bytes())
    archive.unlink()
    receipt = DataSources(store, profiles).resolve(ref)
    assert not receipt['cache_hit'] and not receipt['location_accessed']


def test_concurrent_references_share_one_fetch(data, monkeypatch):
    ref, _, store, profiles = data
    resolver = DataSources(store, profiles)
    original, calls = resolver._open, []
    def counted(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(resolver, '_open', counted)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(resolver.resolve, [ref, ref]))
    assert len(calls) == 1
    assert sorted(row['cache_hit'] for row in results) == [False, True]


@pytest.mark.parametrize('change', [
    lambda r: r.update(key='../escape'), lambda r: r.update(key='/absolute'),
    lambda r: r.update(key='https://other.invalid/data'), lambda r: r.update(key='%2e%2e/data'),
    lambda r: r.update(key='data\nheader'), lambda r: r.update(archive_bytes=True),
    lambda r: r.update(archive_bytes=0), lambda r: r.update(object_sha256='wrong'),
    lambda r: r.update(token='must-not-be-a-job-field'),
])
def test_invalid_references_are_rejected_during_planning(tmp_path, data, change):
    ref, _, _, _ = data
    bad = deepcopy(ref)
    change(bad)
    raw = request(bad, 'unused')
    raw['jobs'][0]['capsule'] = 'a' * 64
    with pytest.raises(ValueError):
        plan(raw, tmp_path / 'invalid-plan')
    assert not (tmp_path / 'invalid-plan').exists()


@pytest.mark.parametrize('profile', [
    {'type': 'https', 'base_url': 'http://insecure.invalid'},
    {'type': 'https', 'base_url': 'https://user:secret@host.invalid'},
    {'type': 'https', 'base_url': 'https://host.invalid/?token=secret'},
    {'type': 'filesystem', 'root': 'relative'},
    {'type': 's3', 'bucket': 'bucket', 'prefix': '../escape'},
    {'type': 's3', 'bucket': 'bucket', 'prefix': False},
    {'type': 's3', 'bucket': 'bucket', 'access_key': 'secret'},
    {'type': 'unsupported'},
])
def test_operator_profiles_are_strict(profile):
    with pytest.raises(ValueError):
        source_profiles({'prices': profile})


def test_missing_source_is_retryable_without_committing(data):
    ref, archive, store, profiles = data
    archive.unlink()
    with pytest.raises(DataUnavailable, match='unavailable'):
        DataSources(store, profiles).resolve(ref)
    assert not (store.directory(ref['object_sha256']) / 'COMMITTED.json').exists()


def test_changed_archive_fails_closed_and_retains_failed_prefix(data):
    ref, archive, store, profiles = data
    archive.write_bytes(b'!' * ref['archive_bytes'])
    with pytest.raises(ValueError, match='corrupt'):
        DataSources(store, profiles).resolve(ref)
    assert not store.directory(ref['object_sha256']).exists()
    assert (store.root / 'uploads' / (ref['object_sha256'] + '.part')).exists()


def test_symlink_cannot_escape_approved_root(data, tmp_path):
    ref, archive, store, profiles = data
    outside = tmp_path / 'outside.tar.gz'
    archive.rename(outside)
    archive.symlink_to(outside)
    with pytest.raises(ValueError, match='symlink'):
        DataSources(store, profiles).resolve(ref)


def test_cache_does_not_enable_unconfigured_source(data):
    ref, _, store, profiles = data
    DataSources(store, profiles).resolve(ref)
    with pytest.raises(ValueError, match='unconfigured'):
        DataSources(store, {}).resolve(ref)


def test_referenced_object_size_and_expansion_are_bounded(data):
    ref, _, store, profiles = data
    wrong = dict(ref, archive_bytes=store.max_bytes + 1)
    with pytest.raises(ValueError, match='object limit'):
        DataSources(store, profiles).resolve(wrong)
    with pytest.raises(ValueError, match='pinned size'):
        DataSources(store, profiles).resolve(dict(ref, archive_bytes=ref['archive_bytes'] + 1))


@pytest.fixture(scope='module')
def certificate(tmp_path_factory):
    folder = tmp_path_factory.mktemp('data-reference-tls')
    cert, private = folder / 'cert.pem', folder / 'key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(private), '-out', str(cert), '-days', '1',
                    '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cert, private


@pytest.fixture
def https_source(tmp_path, data, certificate):
    ref, archive, store, _ = data
    cert, private = certificate
    state = {'mode': 'range', 'calls': [], 'token': 'synthetic-private-token'}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            state['calls'].append(dict(self.headers))
            if self.headers.get('Authorization') != 'Bearer ' + state['token']:
                self.send_error(401)
                return
            if state['mode'] == 'redirect':
                self.send_response(302)
                self.send_header('Location', 'https://unapproved.invalid/secret')
                self.end_headers()
                return
            body = archive.read_bytes()
            if 'Range' in self.headers and state['mode'] != 'ignore-range':
                offset = int(self.headers['Range'][6:-1])
                self.send_response(206)
                self.send_header('Content-Range', f'bytes {offset}-{len(body)-1}/{len(body)}')
                body = body[offset:]
            else:
                self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, private)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token_file = tmp_path / 'data-token'
    token_file.write_text(state['token'])
    token_file.chmod(0o600)
    profiles = {'prices': {'type': 'https', 'base_url': f'https://localhost:{server.server_port}/objects',
                           'ca_file': str(cert), 'bearer_token_file': str(token_file)}}
    try:
        yield ref, archive, store, profiles, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('mode', ['range', 'ignore-range'])
def test_authenticated_https_fetch_resume_and_cache(https_source, mode):
    ref, archive, store, profiles, state = https_source
    state['mode'] = mode
    store.begin(ref['object_sha256'], ref['archive_bytes'])
    store.append(ref['object_sha256'], 0, archive.read_bytes()[:17])
    resolver = DataSources(store, profiles)
    receipt = resolver.resolve(ref)
    assert receipt['provider'] == 'https' and not receipt['cache_hit']
    assert len(state['calls']) == 1 and state['calls'][0]['Range'] == 'bytes=17-'
    assert resolver.resolve(ref)['cache_hit'] and len(state['calls']) == 1
    assert state['token'] not in json.dumps(receipt)
    assert 'localhost' not in json.dumps(receipt)


def test_https_redirect_is_rejected_without_forwarding_credentials(https_source):
    ref, _, store, profiles, state = https_source
    state['mode'] = 'redirect'
    with pytest.raises(ValueError, match='redirect'):
        DataSources(store, profiles).resolve(ref)
    assert len(state['calls']) == 1


def test_https_auth_failure_is_terminal_and_does_not_leak_token(https_source):
    ref, _, store, profiles, state = https_source
    Path(profiles['prices']['bearer_token_file']).write_text('wrong-secret')
    with pytest.raises(ValueError, match='authentication') as error:
        DataSources(store, profiles).resolve(ref)
    assert 'wrong-secret' not in str(error.value)


def test_https_tls_verification_is_not_disabled(https_source):
    ref, _, store, profiles, _ = https_source
    profiles['prices'].pop('ca_file')
    with pytest.raises(ValueError, match='TLS verification'):
        DataSources(store, profiles).resolve(ref)


def test_batch_aliases_allow_references_and_independent_overrides(data):
    ref, _, _, _ = data
    other = dict(ref, key='v2/data.tar.gz', object_sha256='b' * 64)
    raw = {'schema': batch.SCHEMA, 'submission_id': 'ref-batch',
           'data_sources': {'raw': ref, 'other': other},
           'defaults': {'runtime': 'python', 'capsule': 'a' * 64,
                        'inputs': {'data': {'mode': 'source_ref', 'source': 'raw'}},
                        'args': ['--data', '{input.data}/cases.jsonl']},
           'candidates': [{'id': 'one', 'model': 'a.py'},
                          {'id': 'two', 'model': 'b.py',
                           'inputs': {'data': {'mode': 'source_ref', 'source': 'other'}}}]}
    expanded = validate(batch.expand(raw))
    assert expanded['jobs'][0]['inputs']['data'] == ref
    assert expanded['jobs'][1]['inputs']['data'] == other
    assert raw['defaults']['inputs']['data']['mode'] == 'source_ref'


def test_reference_job_api_execution_collection_and_receipt(tmp_path, data):
    ref, _, _, profiles = data
    code = tmp_path / 'code'
    code.mkdir()
    (code / 'main.py').write_text('import pathlib, sys\npathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes())\n')
    planned = tmp_path / 'plan'
    result = plan(request(ref, code), planned)
    assert result['data_acquired'] is False
    assert len(list((planned / 'objects').glob('*.tar.gz'))) == 1  # Capsule only.
    config = configuration()
    config['data_sources'] = profiles
    with WorkflowWorker(tmp_path / 'worker', [], backend='trusted-local', workflow_config=config,
                        concurrency=1, min_free_mb=0) as worker:
        server = Server(('127.0.0.1', 0), worker, 't' * 43)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client(f'http://127.0.0.1:{server.server_port}', 't' * 43)
            client.submit_plan(planned)
            for _ in range(10):
                worker.workflows.tick()
                worker.process_next()
                status = client.workflow_status('reference-test')
                if status['terminal']:
                    break
            assert status['state'] == 'completed'
            envelope = status['nodes'][0]['outputs']
            assert envelope['data_references']['data']['reference'] == ref
            assert envelope['input_objects']['data'] == ref['object_sha256']
            client.collect('reference-test', tmp_path / 'result')
            assert verify_collection(tmp_path / 'result')['final']
            capabilities = client.request('/v2/capabilities')
            assert capabilities['data_reference_sources'] == {'prices': {'type': 'filesystem'}}
            assert str(profiles['prices']['root']) not in json.dumps(capabilities)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@pytest.mark.parametrize('offset', [0, 17])
def test_s3_sdk_versioned_fetch_and_resume(data, monkeypatch, offset):
    boto3 = pytest.importorskip('boto3')
    from botocore.response import StreamingBody
    from botocore.stub import Stubber
    ref, archive, store, _ = data
    ref = dict(ref, version_id='pinned-version')
    client = boto3.client('s3', region_name='us-east-1',
                          aws_access_key_id='synthetic', aws_secret_access_key='synthetic')
    expected = {'Bucket': 'test-prices', 'Key': 'archives/' + ref['key'], 'VersionId': 'pinned-version'}
    response = {'Body': StreamingBody(io.BytesIO(archive.read_bytes()[offset:]), ref['archive_bytes'] - offset),
                'ContentLength': ref['archive_bytes'] - offset, 'VersionId': 'pinned-version'}
    if offset:
        expected['Range'] = f'bytes={offset}-'
        response['ContentRange'] = f"bytes {offset}-{ref['archive_bytes'] - 1}/{ref['archive_bytes']}"
        store.begin(ref['object_sha256'], ref['archive_bytes'])
        store.append(ref['object_sha256'], 0, archive.read_bytes()[:offset])
    class Session:
        def __init__(self, **kwargs):
            pass
        def client(self, *args, **kwargs):
            return client
    monkeypatch.setattr(boto3, 'Session', Session)
    with Stubber(client) as stub:
        stub.add_response('get_object', response, expected)
        receipt = DataSources(store, {'prices': {'type': 's3', 'bucket': 'test-prices',
                                                  'prefix': 'archives/'}}).resolve(ref)
        assert receipt['provider'] == 's3'
        stub.assert_no_pending_responses()


@pytest.mark.parametrize('status,expected_error', [(403, ValueError), (503, DataUnavailable)])
def test_s3_sdk_failure_classification(data, monkeypatch, status, expected_error):
    boto3 = pytest.importorskip('boto3')
    from botocore.stub import Stubber
    ref, _, store, _ = data
    client = boto3.client('s3', region_name='us-east-1',
                          aws_access_key_id='synthetic', aws_secret_access_key='synthetic')
    class Session:
        def __init__(self, **kwargs):
            pass
        def client(self, *args, **kwargs):
            return client
    monkeypatch.setattr(boto3, 'Session', Session)
    with Stubber(client) as stub:
        stub.add_client_error('get_object', service_error_code='Failure',
                              service_message='must-not-leak-provider-details', http_status_code=status)
        with pytest.raises(expected_error) as error:
            DataSources(store, {'prices': {'type': 's3', 'bucket': 'test-prices'}}).resolve(ref)
        assert 'must-not-leak' not in str(error.value)


@pytest.mark.parametrize('backend', ['trusted-local', 'docker'])
def test_native_testing_stages_consume_referenced_data(tmp_path, backend):
    if backend == 'docker' and not os.environ.get('OFFLOAD_RESEARCH_TEST_IMAGE'):
        pytest.skip('requires opt-in prebuilt research image')
    from tests.test_research_batches import native_fixture
    native, raw, _ = native_fixture(tmp_path)
    (raw / 'cases.jsonl').write_text(''.join(json.dumps({'input': n, 'target': 'yes' if n % 10 else 'no'})
                                           + '\n' for n in range(100)))
    ref = prepare_reference(raw, tmp_path / 'referenced', source='prices', object_key='object.tar.gz')
    native['candidates'] = native['candidates'][:1]
    native['candidates'][0].pop('prepare')
    native['defaults']['inputs']['prepared'] = ref
    config = configuration(os.environ.get('OFFLOAD_RESEARCH_TEST_IMAGE', 'python:3.12-slim'))
    config['runtimes']['python'].update(timeout_s=180, memory_mb=1024, max_work_mb=256, max_output_mb=64)
    config['capacity'].update(memory_mb=2048, max_work_mb=512)
    config['data_sources'] = {'prices': {'type': 'filesystem', 'root': str(tmp_path / 'referenced')}}
    planned = tmp_path / 'native-plan'
    plan(native, planned)
    with WorkflowWorker(tmp_path / 'native-worker', [], backend=backend, workflow_config=config,
                        min_free_mb=0) as worker:
        for archive in (planned / 'objects').glob('*.tar.gz'):
            ident = sha(archive)
            worker.workflows.objects.begin(ident, archive.stat().st_size)
            worker.workflows.objects.append(ident, 0, archive.read_bytes())
            worker.workflows.objects.commit(ident)
        worker.workflows.submit(load(planned / 'WORKFLOW.json'))
        for _ in range(10):
            worker.workflows.tick()
            worker.process_next()
            status = worker.workflows.status(native['submission_id'])
            if status['terminal']:
                break
        assert status['state'] == 'completed', status
        output = status['nodes'][0]['outputs']
        assert output['native_result']['statistical_verdict'] == 'SUPPORTED'
        assert output['data_references']['prepared']['reference'] == ref
        assert output['input_objects']['prepared'] == ref['object_sha256']
