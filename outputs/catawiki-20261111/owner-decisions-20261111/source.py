"""Reuse the verified catalogue snapshot reader in this dated operation folder."""
from pathlib import Path

source = Path(__file__).parent.parent / 'catalogue-update/source.py'
exec(compile(source.read_text(), str(source), 'exec'), {'__file__': __file__})
