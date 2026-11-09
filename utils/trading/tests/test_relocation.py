from __future__ import annotations

import importlib
import json
from pathlib import Path
import runpy
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]


def test_all_copied_modules_resolve_inside_v2():
    manifest = json.loads((ROOT / 'utils/trading/MIGRATION.json').read_text())
    for record in manifest['files']:
        path = record['destination']
        if not path.endswith('.py') or '/tests/' in path:
            continue
        module = importlib.import_module(path[:-3].replace('/', '.'))
        assert Path(module.__file__).resolve() == ROOT / path
    assert 'ib_gateway' not in sys.modules
    assert str(ROOT.parent / 'marketmaker') not in sys.path
    assert 'research' not in sys.modules


@pytest.mark.parametrize('module', [
    'utils.iqfeed.downloader', 'utils.iqfeed.daily_refresh',
    'utils.iqfeed.refresh_marketmaker_core', 'utils.iqfeed.singleton',
    'utils.ibkr.download_historical', 'utils.ibkr.download_historical_ticks',
    'utils.ibkr.preflight', 'utils.ibkr.connection_readiness',
    'utils.ibkr.singleton', 'utils.ig_index.bot', 'utils.trading.broker_sync_report',
])
def test_cli_help_does_not_connect(module, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', [module, '--help'])
    monkeypatch.delitem(sys.modules, module, raising=False)
    # Each help entrypoint is tested before any order or download operation.
    with pytest.raises(SystemExit) as caught:
        runpy.run_module(module, run_name='__main__')
    assert caught.value.code == 0
    assert 'usage:' in capsys.readouterr().out.lower()


def test_iqfeed_defaults_use_external_data_and_v2_module():
    from utils.data_paths import CONFIGURED_DATA_ROOT
    from utils.iqfeed import downloader, refresh_marketmaker_core as core
    from utils.ibkr.common import REPO_ROOT
    assert REPO_ROOT == ROOT
    assert downloader.DEFAULT_OUTPUT_DIR.is_relative_to(CONFIGURED_DATA_ROOT)
    assert downloader.DEFAULT_INTERVAL_OUTPUT_DIR.is_relative_to(CONFIGURED_DATA_ROOT)
    assert core.DEFAULT_OUTPUT_DIR.is_relative_to(CONFIGURED_DATA_ROOT)
    assert core.DEFAULT_DOWNLOADER == ROOT / 'utils/iqfeed/downloader.py'


def test_ig_order_execution_keeps_dry_run_default():
    from utils.ig_index import bot
    from utils.ig_index.models import TradeDecision, PositionState
    args = bot.build_parser().parse_args(['--epic', 'TEST'])
    assert args.live_orders is False
    class NoOrderClient:
        def create_otc_position(self, **kwargs):
            raise AssertionError('Dry run submitted an order')
        def close_otc_position(self, **kwargs):
            raise AssertionError('Dry run submitted an order')
    decision = TradeDecision(action='OPEN_LONG', reason='test', size=1.0)
    bot.execute_decision(client=NoOrderClient(), args=args, decision=decision, position=PositionState())
