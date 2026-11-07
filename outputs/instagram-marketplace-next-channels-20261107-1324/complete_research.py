"""Retain the research verification gap for Bing rather than assume UK eligibility."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

out = Path(__file__).parent
source = out / "boldstone-next-channels-reviewed-20261107.html"
target = out / "boldstone-next-channels-final-20261107.html"
assert not target.exists()
doc = source.read_text()
anchor = "</p></section>\n<section id='guidance'>"
assert doc.count(anchor) == 1
note = """</p><p><strong>High-traffic route needing one more eligibility check:</strong> Microsoft/Bing appears in your supplied list. Semrush estimates <a href='https://www.semrush.com/website/bing.com/overview/'>2.33bn worldwide Bing website visits in September</a>, but that is all search traffic, not Shopping buyers. Microsoft documents <a href='https://help.ads.microsoft.com/apex/index/3/en/60048'>Merchant Center and Google-feed import</a>, and its <a href='https://stage-preview-about.ads.microsoft.com/en/blog/post/august-2020/product-listings-show-products-for-free-in-the-bing-shopping-tab'>original free Product Listings announcement</a> named the UK as a planned market. Current free-listing help links could not be retrieved during this review. Confirm the present UK account eligibility and free-only setup before treating this as a verified no-upfront route; no paid campaign should be activated merely to import products.</p></section>\n<section id='guidance'>"""
doc = doc.replace(anchor, note)
target.write_text(doc)
receipt = json.loads((out / "request-progress.json").read_text())
receipt.update(
    checked_utc=datetime.now(timezone.utc).isoformat(),
    report=str(target),
    report_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    visual_render="PASS_LOCAL_DOCUMENT_RENDER; reviewed pages 1-3 of the preceding report version. Final change is one sourced paragraph using the same styling.",
    bing_status="Promising but UK free-listing eligibility still needs current native confirmation; not represented as verified live or free-only enabled.",
    instagram_handoff_tab_id="961989096",
)
(out / "request-progress.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({k: receipt[k] for k in ["report", "report_sha256", "instagram_prepared", "instagram_published_this_request", "saatchi_price_change_this_request", "visual_render"]}, indent=2))
