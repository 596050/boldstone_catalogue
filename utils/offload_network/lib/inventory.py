"""Runtime inventory path, including non-editable installations."""

import os
from pathlib import Path


def hosts_path():
    override = os.environ.get("OFFLOAD_HOSTS_FILE")
    if override:
        return Path(override).expanduser().resolve()
    root = Path(__file__).resolve().parent.parent
    checkout = root / "hosts.json"
    return checkout if checkout.is_file() else root / "fleet" / "hosts.example.json"
