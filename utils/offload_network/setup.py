"""Back-compat shim for older pip / setuptools that don't yet support
PEP 660 editable installs from pyproject.toml alone.

All real metadata lives in pyproject.toml; this file just defers there.
Remove once everyone is on pip >= 22.0 and setuptools >= 64.0.
"""
from setuptools import setup

setup()
