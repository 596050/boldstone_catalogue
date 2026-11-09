import hashlib
import json
from pathlib import Path

import pytest
from utils import data_paths
from utils.external_storage.relocated_references import Locations, read_document


@pytest.fixture
def storage(tmp_path, monkeypatch):
    mount = tmp_path / 'volume'; mount.mkdir()
    config = {
        'external_storage': {'mount_point': str(mount)},
        'data_root': str(mount / 'raw_price_data'),
        'path_relocations': {
            'marketmaker/data/research': 'other_data/research',
            'marketmaker/data/research/demo/raw': 'raw_price_data/demo',
            'macroeconomics': 'raw_price_data/iqfeed_macro_market',
            'macroeconomics/economic_releases': 'other_data/macroeconomics/economic_releases',
        },
        'physical_locations': {
            'data/research': 'other_data/research',
            'data/research/demo/raw': 'raw_price_data/demo',
        },
    }
    monkeypatch.setattr(data_paths, 'load_data_paths', lambda **kwargs: config)
    return mount, config


def test_old_manifest_and_split_relative_payload_keep_original_hashes(storage):
    mount, config = storage
    source = mount / 'raw_price_data/demo/source.csv'
    source.parent.mkdir(parents=True); source.write_bytes(b'time,price\n2026-09-01,42\n')
    manifest = mount / 'other_data/research/demo/MANIFEST.json'
    manifest.parent.mkdir(parents=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original = json.dumps({'path': 'raw/source.csv', 'sha256': digest}).encode()
    manifest.write_bytes(original)
    old = mount / 'marketmaker/data/research/demo/MANIFEST.json'
    actual_manifest = data_paths.resolve_storage_reference(old, require_exists=True)
    assert actual_manifest == manifest
    value = json.loads(actual_manifest.read_bytes())
    for reference_manifest in (old, actual_manifest):
        actual_source = data_paths.resolve_manifest_reference(value['path'], reference_manifest)
        assert actual_source == source
        assert hashlib.sha256(actual_source.read_bytes()).hexdigest() == value['sha256']
    assert manifest.read_bytes() == original


def test_recreated_old_source_is_rejected(storage):
    mount, _ = storage
    old = mount / 'marketmaker/data/research/demo/raw/source.csv'
    old.parent.mkdir(parents=True); old.write_text('shadow')
    with pytest.raises(data_paths.DataPathError, match='recreated'):
        data_paths.resolve_storage_reference(old)


def test_missing_reference_is_not_substituted(storage):
    mount, _ = storage
    with pytest.raises(data_paths.MissingDataPathError):
        data_paths.resolve_storage_reference(mount / 'macroeconomics/economic_releases/missing.csv', require_exists=True)
    with pytest.raises(data_paths.DataPathConfigError):
        data_paths.resolve_manifest_reference('../../../../../escape.csv', mount / 'other_data/research/demo/MANIFEST.json')


def test_local_repository_paths_stay_local(storage):
    _, config = storage
    path = '/Users/tprice/Developer/marketmaker_v2/research/demo.py'
    assert data_paths.resolve_storage_reference(path) == Path(path)
    assert Locations(config).text(path) == (path, [])


def test_derived_view_keeps_checksum_and_observation_clock(storage):
    mount, config = storage
    old = str(mount / 'macroeconomics/economic_releases/series.csv')
    path = mount / 'MANIFEST.json'
    value = {'source': {'path': old, 'sha256': 'f' * 64}, 'observed_at': '2020-01-01T00:00:00Z'}
    path.write_text(json.dumps(value)); original = path.read_bytes()
    identity, current, refs = read_document(path, Locations(config))
    assert identity['sha256'] == hashlib.sha256(original).hexdigest()
    assert current['source']['path'] == str(mount / 'other_data/macroeconomics/economic_releases/series.csv')
    assert current['source']['sha256'] == value['source']['sha256']
    assert current['observed_at'] == value['observed_at']
    assert refs[0]['pointer'] == '/source/path'
    assert path.read_bytes() == original
