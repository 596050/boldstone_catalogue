"""Read public site pages and local publishing records for BMP/Dropbox references."""
from __future__ import annotations

import collections
import hashlib
import html
import json
import os
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse

import convert_bmps as w
import requests
from check_bmp_retirement import CHECKS, reference

PATTERN = re.compile(r".{0,100}(?:\.bmp\b|dropbox(?:usercontent)?\.com).{0,160}", re.IGNORECASE)
LOCK = threading.Lock()
NEXT = 0.0
LOCAL = threading.local()


def matches(text):
    return list(dict.fromkeys(PATTERN.findall(unquote(html.unescape(text.replace('\\/', '/'))))))


def fetch(url):
    global NEXT
    with LOCK:
        wait = max(0, NEXT - time.monotonic())
        NEXT = max(NEXT, time.monotonic()) + 0.35
    time.sleep(wait)
    if not hasattr(LOCAL, "session"):
        LOCAL.session = requests.Session()
        LOCAL.session.headers["User-Agent"] = "Boldstone-Image-Retirement-ReadOnly-Check/1.0"
    try:
        response = LOCAL.session.get(url, timeout=30)
        return {"url": url, "final_url": response.url, "status": response.status_code,
                "bytes": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest(),
                "references": matches(response.text)}
    except requests.RequestException as error:
        return {"url": url, "error_type": type(error).__name__}


def main():
    os.umask(0o077)
    CHECKS.mkdir(exist_ok=True, parents=True, mode=0o700)
    sitemap = requests.get("https://boldstonesculpture.com/sitemap.xml", timeout=30)
    sitemap.raise_for_status()
    sitemap_path = CHECKS / "publication-sitemap.xml"
    sitemap_path.write_bytes(sitemap.content)
    root = ET.fromstring(sitemap.content)
    urls = sorted({r.text for r in root.findall("{*}url/{*}loc")} | {"https://boldstonesculpture.com/"})
    if any(urlparse(url).netloc not in ("boldstonesculpture.com", "www.boldstonesculpture.com") for url in urls):
        raise ValueError("Unexpected sitemap origin")
    images = [r.text for r in root.findall("{*}url/{*}image/{*}loc")]
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch, url) for url in urls]):
            results.append(future.result())
            if len(results) % 50 == 0 or len(results) == len(urls):
                print(f"Public pages checked: {len(results)}/{len(urls)}; "
                      f"pages with references: {sum(bool(r.get('references')) for r in results)}", flush=True)
    # Retry failed reads once; never turn a failed page into absence evidence.
    for index, result in enumerate(results):
        if result.get("status") != 200:
            results[index] = {**fetch(result["url"]), "previous_read": result}
    local_root = Path.cwd() / "SquareSpace product upload"
    listed = subprocess.run(["rg", "--files", "-g", "*.json", "-g", "*.csv", "-g", "*.md",
                             "-g", "*.xml", "-g", "*.html", "-g", "*.py", "-g", "!**/.venv/**",
                             str(local_root)], capture_output=True, text=True, check=True)
    local = []
    for raw in listed.stdout.splitlines():
        path = Path(raw)
        local.append({**reference(path), "references": matches(path.read_text(encoding="utf-8"))})
    report = {"schema": "boldstone-bmp-publication-review-v1", "completed_utc": w.now(),
              "sitemap": reference(sitemap_path), "sitemap_image_count": len(images),
              "sitemap_image_domains": dict(collections.Counter(urlparse(url).netloc for url in images)),
              "sitemap_image_references": [url for url in images if matches(url)],
              "public_pages": sorted(results, key=lambda r: r["url"]), "local_publishing_files": local,
              "boundaries": "Public sitemap pages and local publishing records; excludes private/offline systems.",
              "failed_pages": [r for r in results if r.get("status") != 200],
              "public_reference_pages": [r for r in results if r.get("references")],
              "local_reference_files": [r for r in local if r["references"]]}
    w.private_json(CHECKS / "publication.json", report)
    print(json.dumps({"pages": len(results), "failed_pages": report["failed_pages"],
                      "public_reference_pages": report["public_reference_pages"],
                      "local_files": len(local), "local_reference_files": report["local_reference_files"],
                      "sitemap_image_domains": report["sitemap_image_domains"]}, indent=2))


if __name__ == "__main__":
    main()
