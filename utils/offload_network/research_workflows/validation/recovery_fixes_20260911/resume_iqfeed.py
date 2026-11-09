"""Resume the user-authorized, unchanged queue after verified maintenance completes.

Reads only exported metadata and the local rebind log, never the live queue DB.
Does not start IQConnect, bypass a live lock, remove STOP or change acquisition scope.
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from utils.data_paths import resolve_source_location
from utils.iqfeed.macroeconomics import archive as iq


def main():
    here = Path(__file__).resolve().parent
    repo = here.parents[4]
    logfile = here / "IQFEED_REBIND.log"
    # Waiting is local-only and has a fixed diagnostic deadline. No completion
    # marker means no permission to launch using an unverified code binding.
    deadline = time.monotonic() + 7200
    final = None
    while time.monotonic() < deadline:
        if logfile.exists():
            for line in logfile.read_text().splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "review" in item and "verified_responses" in item:
                    final = item
        if final:
            break
        time.sleep(5)
    if final is None:
        raise TimeoutError("maintenance verification has not completed; no worker started")
    root = resolve_source_location("iqfeed_macroeconomics")
    iq.guard(root, force=True)
    if (root / "metadata/STOP").exists():
        raise RuntimeError("STOP exists; refusing to override a concurrent stop request")
    review_path = Path(final["review"])
    assert review_path.parent == root / "metadata"
    review = json.loads(review_path.read_text())
    config = json.loads((root / "metadata/ARCHIVE.json").read_text())
    assert review["new_code_sha256"] == config["code_sha256"]
    assert config["collector_reviews"][-1] == {
        "file": str(review_path.relative_to(root)), "sha256": iq.file_sha(review_path)
    }
    assert config["cutoff"] == review["previous_archive"]["cutoff"]
    assert review["verified_existing_responses"] == final["verified_responses"]
    started = datetime.now(timezone.utc).isoformat()
    launched = subprocess.run(
        [sys.executable, "-B", "-m", iq.MODULE, "start"], cwd=repo,
        capture_output=True, text=True, check=True, timeout=60,
    )
    response = json.loads(launched.stdout)
    result = {
        "started_at_utc": started, "launch": response, "review": final,
        "cutoff_unchanged": config["cutoff"], "original_scope_unchanged": True,
        "stop_or_live_locks_overridden": False,
    }
    (here / "IQFEED_RESUME.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
