"""Recheck previously rate-limited public products, stopping on HTTP 429.

Read-only public documents; no authentication, image downloads or mutations.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

from check_wescover_public_presence import fetch

ROOT = Path(__file__).resolve().parents[2]


def main(output, previously_matched=False):
    output.mkdir(parents=True, exist_ok=True)
    previous = json.loads((ROOT / "outputs/multichannel-missing-20261104/wescover-public-readbacks.json").read_text())
    remaining = [row for row in previous if (row.get("status") == "PUBLIC_PRODUCT_MATCHED") == previously_matched]
    prefix = "wescover-earlier-public" if previously_matched else "wescover-remaining-public"
    receipts = []
    for binding in remaining:
        result = fetch(binding["url"])
        product = next((x for x in result.get("structured_data", [])
                        if isinstance(x, dict) and x.get("@type") == "Product"), None)
        result.update(sku=binding["sku"], native_item_id=binding["native_item_id"])
        if product:
            result["identity_matches"] = (
                product.get("sku") == binding["native_item_id"]
                and bool(re.search(r"\(" + re.escape(binding["sku"]) + r"\)", product.get("description", "")))
                and product.get("brand", {}).get("name") == "Boldstone"
            )
            result["status"] = "PUBLIC_PRODUCT_MATCHED" if result["identity_matches"] else "IDENTITY_REVIEW_REQUIRED"
        receipts.append(result)
        (output / (prefix + "-readback.json")).write_text(json.dumps(receipts, indent=2))
        print(json.dumps({"checked": len(receipts), "of": len(remaining), "sku": binding["sku"],
                          "status": result.get("status"), "http": result.get("http_status")}), flush=True)
        if result.get("http_status") == 429:
            break
        time.sleep(1.1)
    summary = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "targeted_previous_matches" if previously_matched else "targeted_previous_exceptions": len(remaining),
        "checked_this_run": len(receipts),
        "new_public_matches": sum(r.get("status") == "PUBLIC_PRODUCT_MATCHED" for r in receipts),
        "stopped_for_rate_limit": bool(receipts and receipts[-1].get("http_status") == 429),
        "native_changes": 0,
        "limitation": "An unreadable public page is not proof of a missing or unpublished product.",
    }
    summary_name = "wescover-earlier-summary.json" if previously_matched else "wescover-remaining-summary.json"
    (output / summary_name).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), "--previously-matched" in sys.argv[2:])
