import sys
from pathlib import Path
from typing import Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOST = "localhost"
DEFAULT_GATEWAY_PAPER_PORT = 4002
DEFAULT_GATEWAY_LIVE_PORT = 4001
DEFAULT_TWS_PAPER_PORT = 7497
DEFAULT_TWS_LIVE_PORT = 7496
LIVE_DATA_TYPE = 1


def ensure_repo_root_on_path() -> None:
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def managed_account_buckets(accounts: Iterable[str]) -> tuple[List[str], List[str]]:
    paper = []
    live = []
    for account in accounts:
        if account.startswith("DU"):
            paper.append(account)
        elif account.startswith("U"):
            live.append(account)
    return paper, live


def market_data_type_name(value) -> str:
    names = {
        1: "LIVE",
        2: "FROZEN",
        3: "DELAYED",
        4: "DELAYED-FROZEN",
    }
    return names.get(value, f"unknown({value})")

