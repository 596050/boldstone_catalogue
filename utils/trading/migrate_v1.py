"""Record the initial broker-utility copy, refusing to overwrite existing files.

Only executable integration dependencies are copied. Source trees, frozen model
identities, credentials, market data and installed services are never modified.
The manifest records original and relocated bytes separately. Subsequent path
fixes are retained in the delivered files and their final manifest hashes.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import stat


COPY_MAP = {
    **{name + '.py': 'utils/trading/' + name + '.py' for name in (
        'broker_state', 'event_loop', 'logging_config', 'main',
        'main_thread_order_queue', 'market_maker', 'market_maker_config',
        'marketdata', 'order_management', 'portfolio_manager', 'runtime_state',
        'shared_market_data', 'standalone_market_data',
    )},
    'check_ibkr.py': 'utils/ibkr/check.py',
    'run_ibkr.py': 'utils/ibkr/run_ibkr.py',
    'ib_gateway/common.py': 'utils/ibkr/common.py',
    'ib_gateway/gateway_singleton.py': 'utils/ibkr/singleton.py',
    'ib_gateway/preflight.py': 'utils/ibkr/preflight.py',
    'ib_gateway/ibkr_connection_readiness.py': 'utils/ibkr/connection_readiness.py',
    'ib_gateway/download_historical.py': 'utils/ibkr/download_historical.py',
    'ib_gateway/download_historical_ticks.py': 'utils/ibkr/download_historical_ticks.py',
    'scripts/ib_gateway_start.sh': 'utils/ibkr/start.sh',
    'scripts/ib_gateway_preflight.sh': 'utils/ibkr/installation_preflight.sh',
    'scripts/ib_gateway_disclaimer_warmup.py': 'utils/ibkr/disclaimer_warmup.py',
    'ib_gateway/iqfeed_singleton.py': 'utils/iqfeed/singleton.py',
    'ib_gateway/iqfeed_daily_refresh.py': 'utils/iqfeed/daily_refresh.py',
    'ib_gateway/refresh_iqfeed_marketmaker_core.py': 'utils/iqfeed/refresh_marketmaker_core.py',
    'scripts/iqfeed_start.sh': 'utils/iqfeed/start.sh',
    '.runtime/iqfeed/famous_model_iq/iq_feed/iqfeed_downloader.py': 'utils/iqfeed/downloader.py',
    '.runtime/iqfeed/famous_model_iq/iq_feed/lib/ensure_iqfeed_lookup.sh': 'utils/iqfeed/lib/ensure_iqfeed_lookup.sh',
    '.runtime/iqfeed/famous_model_iq/iq_feed/lib/iqfeed_keepalive.py': 'utils/iqfeed/lib/iqfeed_keepalive.py',
    'frozen_models_running/ibkr/_target_runtime/iqfeed_market_data.py': 'utils/iqfeed/live_data.py',
    'frozen_models_running/ibkr/_target_runtime/trading_calendar.py': 'utils/trading/calendar.py',
    'frozen_models_running/ig_index/carry_zrev_96_ig_spreadbet_v1/ig_session.py': 'utils/ig_index/session.py',
    'frozen_models_running/ig_index/carry_zrev_96_ig_spreadbet_v1/instruments.py': 'utils/ig_index/instruments.py',
    'scripts/carry96_broker_sync_report.py': 'utils/trading/broker_sync_report.py',
    **{'ig/' + name + '.py': 'utils/ig_index/' + name + '.py' for name in (
        'client', 'bot', 'models', 'risk', 'strategy',
    )},
    **{'tests/' + name + '.py': 'utils/trading/tests/' + name + '.py' for name in (
        'test_broker_state_and_order_identity', 'test_download_historical',
        'test_gateway_singleton', 'test_ibkr_connection_readiness',
        'test_ig_strategy', 'test_iqfeed_daily_refresh', 'test_iqfeed_singleton',
        'test_shared_market_data',
    )},
}


def module_name(path: str) -> str:
    return path.removesuffix('.py').replace('/', '.')


MODULE_MAP = {
    module_name(src): module_name(dst)
    for src, dst in COPY_MAP.items()
    if src.endswith('.py') and not src.startswith(('.runtime/', 'tests/'))
}
MODULE_MAP['ib_gateway.data_freshness_daemon'] = 'utils.trading.calendar'


def relocate_python(source: str) -> str:
    """Rewrite import nodes without reformatting trading/protocol logic."""
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(ast.parse(source)):
        replacement = None
        if isinstance(node, ast.ImportFrom) and not node.level and node.module in MODULE_MAP:
            node.module = MODULE_MAP[node.module]
            replacement = ast.unparse(node)
        elif isinstance(node, ast.Import):
            changed = False
            for alias in node.names:
                if alias.name in MODULE_MAP:
                    original = alias.name
                    alias.name = MODULE_MAP[original]
                    if '.' not in original and alias.asname is None:
                        alias.asname = original
                    changed = True
            if changed:
                replacement = ast.unparse(node)
        if replacement is not None:
            start = offsets[node.lineno - 1] + len(lines[node.lineno - 1].encode()[:node.col_offset].decode())
            end = offsets[node.end_lineno - 1] + len(lines[node.end_lineno - 1].encode()[:node.end_col_offset].decode())
            edits.append((start, end, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    # Also relocate module references in command strings and dotted imports.
    for original, relocated in sorted(MODULE_MAP.items(), key=lambda pair: -len(pair[0])):
        if '.' in original:
            source = re.sub(r'(?<![\w.])' + re.escape(original) + r'(?![\w])', relocated, source)
    source = source.replace('Path(__file__).resolve().parents[1]', 'Path(__file__).resolve().parents[2]')
    for original, relocated in COPY_MAP.items():
        if original.startswith('scripts/'):
            source = source.replace(original, relocated)
    return source


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def copy_files(source_root: Path, destination_root: Path) -> dict:
    for src, dst in COPY_MAP.items():
        if not (source_root / src).is_file():
            raise FileNotFoundError(source_root / src)
        if (destination_root / dst).exists():
            raise FileExistsError(destination_root / dst)
    records = []
    for src, dst in COPY_MAP.items():
        original = (source_root / src).read_bytes()
        payload = relocate_python(original.decode()) if src.endswith('.py') else original.decode()
        if dst == 'utils/trading/calendar.py':
            daemon = (source_root / 'ib_gateway/data_freshness_daemon.py').read_text()
            tree = ast.parse(daemon)
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'last_completed_session')
            payload += '\n\nfrom datetime import timezone\n\n' + relocate_python(ast.get_source_segment(daemon, function)) + '\n'
        destination = destination_root / dst
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('x') as handle:
            handle.write(payload)
        destination.chmod(stat.S_IMODE((source_root / src).stat().st_mode) | stat.S_IWUSR)
        records.append({'source': src, 'destination': dst, 'source_sha256': digest(original),
                        'destination_sha256': digest(destination.read_bytes())})
    for name in ('iqfeed', 'ibkr', 'ig_index', 'trading'):
        package = destination_root / 'utils' / name / '__init__.py'
        package.write_text('"""Local ' + name.replace('_', ' ') + ' utilities; importing the package starts no service."""\n')
    receipt = {
        'schema': 'marketmaker_v2.broker_utility_migration.v1',
        'source_root': str(source_root), 'destination_root': str(destination_root),
        'scope': 'Provider connection, generic execution, market data, downloads and their direct shared dependencies',
        'source_files_modified': False, 'frozen_files_modified': False,
        'credentials_copied': False, 'market_data_copied': False,
        'services_started': False, 'orders_submitted': False,
        'additional_extraction': {
            'source': 'ib_gateway/data_freshness_daemon.py',
            'source_sha256': digest((source_root / 'ib_gateway/data_freshness_daemon.py').read_bytes()),
            'function': 'last_completed_session', 'destination': 'utils/trading/calendar.py',
        },
        'files': records,
    }
    (destination_root / 'utils/trading/MIGRATION.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    result = copy_files(args.source.resolve(), args.destination.resolve())
    print(json.dumps({'copied_source_files': len(result['files'])}))
