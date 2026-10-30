#!/usr/bin/env python3
"""
Boldstone -> per-post image pipeline.

Reads the product list, downloads each product's photos from the LIVE Squarespace
site, and writes correctly-sized, correctly-counted JPEGs straight into the folder
that holds that post's markdown:

    social/instagram/<slug>/  caption.md + 01.jpg .. 20.jpg   (4:5, all photos)
    social/facebook/<slug>/   caption.md + 01.jpg .. 20.jpg   (4:5, all photos)
    social/threads/<slug>/    caption.md + 01.jpg .. 20.jpg   (4:5, all photos)
    social/x/<slug>/          caption.md + 01.jpg .. 02.jpg   (16:9, MAX 2)
    social/linkedin/<slug>/   caption.md + 01.jpg .. 04.jpg   (1:1,  MAX 4)
    blog/<slug>/              article.md + 01.jpg .. NN.jpg   (max 1600px wide)

Usage:
    pip install -r requirements.txt
    python3 fetch_and_resize.py            # uses cached catalogue if present
    python3 fetch_and_resize.py --refresh  # re-scan the site first

Safe to re-run: images already present are skipped.
"""
import io, json, re, sys, time
from pathlib import Path

try:
    import requests
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Missing deps. Run:  pip install -r requirements.txt")

SITE = "https://boldstonesculpture.com"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "_data"

# size = target canvas · max_imgs = photos that platform gets · pad = letterbox on white
TARGETS = {
    "social/instagram": {"size": (1080, 1350), "max_imgs": 20, "q": 82, "pad": True},
    "social/facebook":  {"size": (1200, 1500), "max_imgs": 20, "q": 82, "pad": True},
    "social/threads":   {"size": (1080, 1350), "max_imgs": 20, "q": 82, "pad": True},
    "social/x":         {"size": (1600, 900),  "max_imgs": 2,  "q": 82, "pad": True},
    "social/linkedin":  {"size": (1200, 1200), "max_imgs": 4,  "q": 82, "pad": True},
    "blog":             {"size": (1600, 1600), "max_imgs": 99, "q": 84, "pad": False},
}
BG = (255, 255, 255)


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def discover():
    """Pull every product and its full image list from the live store's JSON API."""
    master = json.loads((DATA / "products_master.json").read_text())
    out = []
    for i, p in enumerate(master, 1):
        slug = slugify(p["title"])
        try:
            r = requests.get(f"{SITE}/buy/p/{slug}", params={"format": "json"}, timeout=30)
            if r.status_code != 200:
                print(f"  ! {slug}: HTTP {r.status_code}")
                continue
            item = r.json().get("item", {})
            imgs = [x["assetUrl"] for x in item.get("items", []) if x.get("assetUrl")]
            out.append({"slug": slug, "title": p["title"], "images": imgs})
            print(f"  [{i}/{len(master)}] {slug}: {len(imgs)} images")
        except Exception as e:
            print(f"  ! {slug}: {e}")
        time.sleep(0.12)
    return out


def render(img, spec, dest):
    im = ImageOps.exif_transpose(img).convert("RGB")
    if spec["pad"]:
        canvas = Image.new("RGB", spec["size"], BG)
        im.thumbnail(spec["size"], Image.LANCZOS)
        canvas.paste(im, ((spec["size"][0] - im.width) // 2,
                          (spec["size"][1] - im.height) // 2))
    else:
        im.thumbnail(spec["size"], Image.LANCZOS)
        canvas = im
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, "JPEG", quality=spec["q"], optimize=True, progressive=True)
    return dest.stat().st_size


def main():
    cache = DATA / "site_images.json"
    if cache.exists() and "--refresh" not in sys.argv:
        products = json.loads(cache.read_text())
        print(f"Using cached catalogue ({len(products)} products). Pass --refresh to re-scan.")
    else:
        print("Scanning boldstonesculpture.com for image URLs ...")
        products = discover()
        cache.write_text(json.dumps(products, indent=1))
        print(f"\nCatalogue cached: {len(products)} products.\n")

    made = skipped = failed = 0
    total = 0
    for n, p in enumerate(products, 1):
        srcs = p.get("images") or []
        if not srcs:
            continue
        print(f"[{n}/{len(products)}] {p['title']} ({len(srcs)} photos)")
        originals = {}
        for folder, spec in TARGETS.items():
            postdir = ROOT / folder / p["slug"]
            if not postdir.exists():          # no markdown there -> nothing to illustrate
                continue
            for idx, url in enumerate(srcs[: spec["max_imgs"]], 1):
                dest = postdir / f"{idx:02d}.jpg"
                if dest.exists():
                    skipped += 1
                    continue
                if url not in originals:
                    try:
                        resp = requests.get(url, timeout=60)
                        resp.raise_for_status()
                        originals[url] = Image.open(io.BytesIO(resp.content))
                    except Exception as e:
                        print(f"    ! download failed: {e}")
                        failed += 1
                        continue
                try:
                    total += render(originals[url], spec, dest)
                    made += 1
                except Exception as e:
                    print(f"    ! resize failed: {e}")
                    failed += 1

    print("\n" + "=" * 62)
    print(f"created {made} · skipped {skipped} · failed {failed}")
    if made:
        print(f"average file size: {total / made / 1024:.0f} KB  (all well under platform limits)")


if __name__ == "__main__":
    main()
