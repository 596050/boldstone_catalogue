"""Read selected Dropbox-original image headers through the local app.

Uses the app's stable ID/content-hash guarded streaming endpoint. Reads at most
1 MiB per original and retains metadata only, not complete image copies.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

from PIL import ImageFile


def check(photo):
    result = {"photo_id": photo["id"], "name": photo["name"],
              "expected_content_hash": photo["original"]["dropbox_content_hash"],
              "checked_at": datetime.now(timezone.utc).isoformat()}
    query = urlencode({"id": result["photo_id"], "v": result["expected_content_hash"]})
    try:
        with urlopen("http://127.0.0.1:8767/api/image?" + query, timeout=35) as response:
            parser, count = ImageFile.Parser(), 0
            while count < 1048576:
                data = response.read(min(16384, 1048576-count))
                if not data:
                    break
                count += len(data)
                parser.feed(data)
                if parser.image:
                    break
            result.update(bytes_read=count, original_bytes=int(response.headers.get("Content-Length", "0")))
            if not parser.image:
                raise ValueError("Image header not determined within bounded read")
            width, height = parser.image.size
            result.update(width=width, height=height, format=parser.image.format, mode=parser.image.mode,
                          landscape_uploader_dimensions=width >= 1500 and height >= 1200,
                          portrait_published_guidance_dimensions=width >= 1200 and height >= 1500,
                          status="ORIGINAL_HEADER_READ")
    except Exception as error:
        result.update(status="ORIGINAL_READ_UNVERIFIED", error=str(error))
    return result


def main(output):
    source = json.loads((output / "app-source.json").read_text())
    root = Path(__file__).resolve().parents[2]
    reconciliation = json.loads((root / "outputs/multichannel-missing-20261104/reconciled-records.json").read_text())
    scope = set(json.loads((output / "scope.json").read_text())["publication_skus"])
    missing = {r["sku"] for r in reconciliation if r["sku"] in scope and r["saatchi"].get("missing")}
    products = {}
    photos = {}
    for product in source["products"]:
        fields = {r["key"]: r["value"] for r in product["fields"] + product["listing_fields"]}
        sku = fields["Seller SKU"]
        if sku not in missing:
            continue
        selected = product["photos"]["listing"]["images"]
        products[sku] = {"catalogue_id": product["id"], "title": product["retail_name"],
                         "photos": [r["id"] for r in selected]}
        for photo in selected:
            if not photo.get("withheld_reasons") and photo.get("original", {}).get("dropbox_content_hash"):
                photos[photo["id"]] = photo
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = {pool.submit(check, photo): aid for aid, photo in photos.items()}
        for future in as_completed(pending):
            results.append(future.result())
            (output / "saatchi-original-headers.json").write_text(json.dumps(results, indent=2))
            if len(results) % 10 == 0 or len(results) == len(photos):
                print(json.dumps({"headers_checked": len(results), "of": len(photos)}), flush=True)
    by_id = {r["photo_id"]: r for r in results}
    for product in products.values():
        checks = [by_id[aid] for aid in product["photos"] if aid in by_id]
        product["originals_meeting_landscape_gate"] = [r["photo_id"] for r in checks if r.get("landscape_uploader_dimensions")]
        product["portrait_candidates_for_native_test"] = [r["photo_id"] for r in checks if r.get("portrait_published_guidance_dimensions") and not r.get("landscape_uploader_dimensions")]
    summary = {"checked_at": datetime.now(timezone.utc).isoformat(), "missing_products": len(products),
               "distinct_selected_originals_checked": len(results),
               "bounded_header_reads_only": True, "full_images_retained": 0,
               "products_with_landscape_size_candidate": sum(bool(r["originals_meeting_landscape_gate"]) for r in products.values()),
               "products_with_portrait_test_candidate": sum(bool(r["portrait_candidates_for_native_test"]) for r in products.values()),
               "unverified_original_reads": sum(r["status"] != "ORIGINAL_HEADER_READ" for r in results),
               "native_publications": 0,
               "limitation": "Pixel dimensions alone do not establish a suitable full-view primary or native upload acceptance.",
               "products": products}
    (output / "saatchi-original-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k != "products"}), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
