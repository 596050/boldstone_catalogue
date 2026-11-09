"""Quick smoke test: authenticate, create a draft, list drafts, fetch the draft.

Run with:
    python -m utils.google_services.test_draft
    python utils/google_services/test_draft.py
"""

import logging
import sys
from pathlib import Path

# Allow running as a standalone script from the repo root
if __name__ == "__main__":
    _repo_root = str(Path(__file__).resolve().parent.parent.parent)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)

from utils.google_services.auth import GoogleAuth
from utils.google_services.gmail import GmailService


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    )

    print("1. Authenticating ...")
    auth = GoogleAuth()
    print("   Authentication successful.")

    gmail = GmailService(auth=auth)

    print("2. Creating test draft ...")
    draft = gmail.create_draft(
        to="test@example.com",
        subject="Google Services test draft",
        html_body="<p>This draft was created by <b>test_draft.py</b>.</p>",
    )
    draft_id = draft["id"]
    print(f"   Draft created: id={draft_id}")

    print("3. Listing drafts ...")
    drafts = gmail.list_drafts(max_results=10)
    found = any(d["id"] == draft_id for d in drafts)
    print(f"   Found {len(drafts)} draft(s). Test draft present: {found}")

    print("4. Fetching draft details ...")
    detail = gmail.get_draft(draft_id)
    snippet = detail.get("message", {}).get("snippet", "")
    print(f"   Snippet: {snippet!r}")

    print("\n--- ALL CHECKS PASSED ---")


if __name__ == "__main__":
    main()
