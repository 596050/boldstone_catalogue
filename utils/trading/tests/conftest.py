"""Offline fixtures for the copied utility suite; never read the mounted archive."""
from pathlib import Path
import asyncio
import socket
import sys
import tempfile
import types

import pytest

# Exercise the installed client library; individual tests still use fake broker
# objects. Loading this before collection prevents a retained test's minimal
# fallback stub from hiding missing exports in the real dependency.
asyncio.set_event_loop(asyncio.new_event_loop())
import ib_insync  # noqa: E402,F401


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_temporary_data = tempfile.TemporaryDirectory(prefix='marketmaker_v2_broker_tests_')
_previous_data_paths = sys.modules.get('utils.data_paths')
_data_paths = types.ModuleType('utils.data_paths')
_data_paths.CONFIGURED_DATA_ROOT = Path(_temporary_data.name)
sys.modules['utils.data_paths'] = _data_paths


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Broker migration tests must not open network connections')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)


def pytest_unconfigure(config):
    if _previous_data_paths is None:
        sys.modules.pop('utils.data_paths', None)
    else:
        sys.modules['utils.data_paths'] = _previous_data_paths
    _temporary_data.cleanup()
