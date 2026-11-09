"""Verify the published physical registry without starting collectors or trading."""
import hashlib
import ast
import importlib
import gzip
import json
from pathlib import Path
import sys
from organize import HERE, REPO, atomic_json, utc
sys.path.insert(0, str(REPO))
from utils.data_paths import CONFIGURED_DATA_ROOT, audit_data_paths, resolve_source_location, resolve_data_path, ensure_external_storage
from utils.data_paths import _source_location_path


def main():
    audit = audit_data_paths()
    prior = json.loads((HERE / 'PRIOR_REGISTRY_CENSUS_AUDIT.json').read_text())
    issues = {
        'new_missing_registered_directories': sorted({p.removeprefix('data/') for p in audit['missing_local']} - set(prior['missing_local_before'])),
        'new_unexpected_present': sorted({p.removeprefix('data/') for p in audit['unexpected_present']} - set(prior['unexpected_present_before'])),
        'symlinks': audit['symlinks'],
    }
    config = json.loads((REPO / 'data_paths.json').read_text())
    original = json.loads((HERE / 'BEFORE_data_paths.json').read_text())
    with gzip.open(HERE / 'census_repaired/DIRECTORIES.jsonl.gz', 'rt') as f:
        original_directories = {json.loads(line)['path'] for line in f}
    mount = Path(config['external_storage']['mount_point'])
    locations = {}
    issues['new_missing_source_locations'] = []
    for name in config['source_locations']:
        current = resolve_source_location(name)
        old = _source_location_path(original, name)
        before_present = str(old.relative_to(mount)) in original_directories
        locations[name] = {'path': str(current), 'present': current.is_dir(), 'present_before_organization': before_present}
        if before_present and not current.is_dir(): issues['new_missing_source_locations'].append(name)
    frozen = {}
    for file, expected in json.loads((HERE / 'FROZEN_SPEC_SOURCE_BINDINGS.json').read_text()).items():
        actual = hashlib.sha256((REPO / file).read_bytes()).hexdigest()
        if actual != expected: raise RuntimeError('Frozen specification changed during organization: ' + file)
        module = None
        import_error = None
        try:
            module = importlib.import_module(file.removesuffix('.py').replace('/', '.'))
        except ModuleNotFoundError as exc:
            import_error = str(exc)
        bound = {}
        for name in ['DATA_DIR', 'SIGNAL_DATA_DIR']:
            value = getattr(module, name, None) if module else None
            if module is None:
                # Verify only literal root-relative path declarations. Do not
                # fabricate legacy packages or claim an import succeeded.
                for node in ast.parse((REPO / file).read_text()).body:
                    if not isinstance(node, ast.Assign) or not any(isinstance(t, ast.Name) and t.id == name for t in node.targets): continue
                    expr = node.value
                    if (isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div)
                            and isinstance(expr.left, ast.Name) and expr.left.id == 'CONFIGURED_DATA_ROOT'
                            and isinstance(expr.right, ast.Constant) and isinstance(expr.right.value, str)):
                        value = CONFIGURED_DATA_ROOT / expr.right.value
                    else: raise RuntimeError('Path declaration requires explicit evaluation: ' + name)
            if value is not None:
                if not value.is_dir(): raise RuntimeError('Frozen price directory is unavailable')
                bound[name] = str(value)
        frozen[file] = {'sha256': actual, 'resolved_price_directories': bound,
                        'import_error': import_error,
                        'validation': 'IMPORTED' if module else 'LITERAL_DATA_PATH_DECLARATIONS_ONLY'}
    result = {'at_utc': utc(), 'status': 'PASS_STORAGE_LOCATIONS_WITH_RETAINED_STATUS_AND_RUNTIME_LIMITATIONS' if not any(issues.values()) else 'FAIL',
              'registered_datasets': audit['registered_datasets'], 'new_issues': issues,
              'preexisting_status_mismatches': prior['unexpected_present_before'],
              'full_audit': audit, 'source_locations': locations, 'frozen_specifications': frozen,
              'runtime_import_limitations': {p:r['import_error'] for p,r in frozen.items() if r['import_error']},
              'research_output_root': str(resolve_data_path('research', require_exists=True)),
              'external_volume_uuid': ensure_external_storage()['volume_uuid'],
              'local_repositories_preserved': {name: (Path('/Users/tprice/Developer') / name).is_dir() for name in ['marketmaker', 'marketmaker_v2']},
              'trading_or_collection_started': False}
    atomic_json(HERE / 'LIVE_PATH_VERIFICATION.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'full_audit','preexisting_status_mismatches','frozen_specifications'}}, indent=2))
    if any(issues.values()): raise SystemExit(2)


if __name__ == '__main__': main()
