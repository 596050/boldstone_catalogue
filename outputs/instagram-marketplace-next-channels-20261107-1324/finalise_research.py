"""Create a revised report without overwriting the earlier working artifact."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

out = Path(__file__).parent
old = out / "boldstone-next-channels-20261107.html"
new = out / "boldstone-next-channels-reviewed-20261107.html"
assert not new.exists()
doc = old.read_text()
edits = {
    "Existing local notes show Amazon onboarding already in progress.":
        "Existing account presence and onboarding status were not checked in this review.",
    "Resume the existing account. Pilot a small, safely packed item only after actual delivery cost and shipping credit reconcile.":
        "Check for an existing account before registering. Pilot a small, safely packed item only after actual delivery cost and shipping credit reconcile.",
    "Another Chrome task is switching windows, so no publication is counted until the exact account, image, caption and product tag can be saved and read back safely.":
        "Chrome changed windows during the first photo selection. The upload was stopped before publication. These five posts remain local preparations, with no saved native product tags or new post IDs. A quiet editing interval is needed before posting.",
    "The price must be freshly checked in the exact existing artwork before any new save; do not create a duplicate listing.":
        "The price must be freshly checked in the exact existing artwork before any new save; do not create a duplicate listing. The older filled form is no longer open. <a href='https://www.saatchiart.com/en-gb/studio/art/14393353/overview'>Open existing artwork 14393353</a>; its intended artwork-only price is US$265, preserving crate packing and the separate collector delivery quote. An explicit reCAPTCHA rejection requires owner verification; it is not a reason to keep repeating Save.",
}
for before, after in edits.items():
    assert before in doc, before
    doc = doc.replace(before, after)
new.write_text(doc)

research = json.loads((out / "channel-research.json").read_text())
research["checked_utc"] = datetime.now(timezone.utc).isoformat()
research["browser_gate"] = "Focus changed during photo selection; no publication was attempted. Direct tab control is unavailable. Pending request for a quiet Chrome interval remains unanswered."
research["amazon_account_status"] = "Not checked; search for existing account before any registration."
for channel in research["channels"]:
    if channel["name"].startswith("Amazon UK"):
        channel["fit"] = channel["fit"].replace(
            "Existing local notes show Amazon onboarding already in progress.",
            "Existing account presence and onboarding status were not checked in this review."
        )
        channel["action"] = channel["action"].replace("Resume the existing account.", "Check for an existing account before registering.")
(out / "channel-research-reviewed.json").write_text(json.dumps(research, indent=2) + "\n")

class Readback(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.images = []
        self.styles = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "img":
            self.images.append(attrs.get("src", ""))
        if tag == "style":
            self.styles += 1

p = Readback()
p.feed(new.read_text())
assert {"overview", "competitors", "guidance", "posts", "sources"} <= p.ids
assert p.styles == 1 and p.images and all(s.startswith("data:image/") for s in p.images)
assert all(s[1:] in p.ids for s in p.links if s.startswith("#"))
assert len([s for s in p.links if s.startswith("https://")]) >= 20
posts = json.loads((out / "instagram-five-posts.json").read_text())
assert len(posts) == len({p["sku"] for p in posts}) == 5
assert all(p["status"] == "PREPARED_NOT_PUBLISHED" for p in posts)
assert all(hashlib.sha256(Path(p["media_path"]).read_bytes()).hexdigest() == p["sha256"] for p in posts)
receipt = {
    "checked_utc": research["checked_utc"],
    "research_status": "PASS_CONTENT_AND_SOURCE_READBACK",
    "report": str(new),
    "report_sha256": hashlib.sha256(new.read_bytes()).hexdigest(),
    "visual_render": "Pending; browser control unavailable while native Chrome focus is shared.",
    "instagram_prepared": 5,
    "instagram_published_this_request": 0,
    "publish_actions_issued": 0,
    "new_native_post_ids": [],
    "saatchi_price_change_this_request": False,
    "saatchi_price_last_verified_usd": 138,
    "saatchi_price_last_verified_utc": "2026-11-07T08:14:00Z",
    "saatchi_target_usd": 265,
    "fresh_native_marketplace_checks": "Blocked by shared native window focus and unavailable direct tab control",
    "app_products_changed_since_previous_workbook_snapshot": 0,
    "catalogue_workbook_changed_this_request": False,
    "new_accounts_created": 0,
    "paid_plans_activated": 0,
    "source_entries": 443,
    "source_lists": 3,
    "research_scope": "Selected higher-traffic candidates; not an exhaustive current audit of all 443 entries",
}
(out / "request-progress.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
