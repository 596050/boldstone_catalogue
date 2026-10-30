"""Bing JSON REST, IndexNow, and optional Cloudflare ownership-proof deployment."""

from __future__ import annotations

import re
import secrets
import urllib.parse

from .core import ToolkitError, canonical_url


class Bing:
    BASE = "https://ssl.bing.com/webmaster/api.svc/json/"

    def __init__(self, p, http, vault, receipt):
        self.p, self.http, self.vault, self.receipt = p, http, vault, receipt

    def call(self, method, name, params=None):
        key = self.vault.get("bing_api_key")["value"]
        self.http.secrets.append(key)
        args = {"apikey": key}
        if method == "GET":
            args.update(params or {})
        result = self.http.call(
            method,
            self.BASE + name + "?" + urllib.parse.urlencode(args),
            body=params if method == "POST" else None,
        )["data"]
        if not isinstance(result, dict) or "d" not in result:
            raise ToolkitError("Unexpected Bing REST envelope.")
        if isinstance(result["d"], dict) and ("ErrorCode" in result["d"] or "ErrorCode" in result):
            raise ToolkitError("Bing returned an API fault; inspect credential/account access.")
        return result["d"]

    def sites(self):
        result = self.call("GET", "GetUserSites")
        if not isinstance(result, list):
            raise ToolkitError("Bing did not return a complete site list.")
        return result

    def own_site(self, sites):
        return next(
            (s for s in sites if s.get("Url", "").rstrip("/") == self.p.url.rstrip("/")), None
        )

    def ensure_site(self):
        site = self.own_site(self.sites())
        if site is None:
            self.receipt.add("bing.add_site", "attempting", {"siteUrl": self.p.url})
            self.call("POST", "AddSite", {"siteUrl": self.p.url})
            site = self.own_site(self.sites())
            if site is None:
                raise ToolkitError("Added Bing site was absent on readback.")
        self.receipt.add(
            "bing.site", "verified" if site.get("IsVerified") else "ownership_pending", site
        )
        return site

    def prepare_verification(self):
        site = self.ensure_site()
        if not site.get("AuthenticationCode"):
            raise ToolkitError("Bing did not return a verification code.")
        self.p.save_state(bing_verification=site)
        return site

    def confirm_verification(self):
        self.receipt.add("bing.verify_ownership", "attempting", {"siteUrl": self.p.url})
        result = self.call("POST", "VerifySite", {"siteUrl": self.p.url})
        site = self.own_site(self.sites())
        if result is not True or not site or not site.get("IsVerified"):
            raise ToolkitError(
                "Bing ownership is still unverified; check the published proof and retry later."
            )
        self.receipt.add("bing.verify_ownership", "verified", {"siteUrl": self.p.url})
        return {"siteUrl": self.p.url, "verified": True}

    def setup(self):
        site = self.ensure_site()
        if not site.get("IsVerified"):
            raise ToolkitError(
                "Bing site is added but ownership is pending. Prepare/publish/confirm verification."
            )
        feeds = self.call("GET", "GetFeeds", {"siteUrl": self.p.url})
        for url in self.p.data["website"].get("sitemaps", []):
            if any(f.get("Url") == url for f in feeds):
                self.receipt.add("bing.sitemap", "already_submitted", url)
                continue
            self.receipt.add("bing.submit_sitemap", "attempting", {"feedUrl": url})
            self.call("POST", "SubmitFeed", {"siteUrl": self.p.url, "feedUrl": url})
            check = self.call("GET", "GetFeeds", {"siteUrl": self.p.url})
            if not any(f.get("Url") == url for f in check):
                raise ToolkitError("Bing sitemap submission absent on readback.")
            self.receipt.add("bing.sitemap", "submission_verified_processing_separate", check)
        return {"feeds": self.call("GET", "GetFeeds", {"siteUrl": self.p.url})}

    def report(self):
        # These APIs choose their own available windows; never label them with a requested GA4 period.
        return {
            name: self.call("GET", name, {"siteUrl": self.p.url})
            for name in ["GetRankAndTrafficStats", "GetQueryStats", "GetCrawlStats", "GetFeeds"]
        }


class IndexNow:
    ENDPOINT = "https://api.indexnow.org/indexnow"

    def __init__(self, p, http, receipt):
        self.p, self.http, self.receipt = p, http, receipt

    def prepare(self):
        state = self.p.state()
        key = state.get("indexnow_key") or secrets.token_hex(32)
        if not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key):
            raise ToolkitError("Invalid IndexNow key.")
        self.p.save_state(indexnow_key=key)
        return {"key": key, "keyLocation": self.p.url + key + ".txt"}

    def submit(self, urls):
        key = self.p.state().get("indexnow_key")
        if not key:
            raise ToolkitError("Prepare and publish the IndexNow key file first.")
        location = self.p.url + key + ".txt"
        urls = list(dict.fromkeys(canonical_url(u) for u in urls))
        if not urls or len(urls) > 10000:
            raise ToolkitError("Supply between 1 and 10,000 changed URLs.")
        if any(urllib.parse.urlsplit(u).hostname != self.p.host for u in urls):
            raise ToolkitError("IndexNow URL outside the configured canonical hostname.")
        proof = self.http.call("GET", location, text=True)
        if proof["text"].strip() != key:
            raise ToolkitError(
                "Public IndexNow key-file contents do not match; no notification sent."
            )
        body = {"host": self.p.host, "key": key, "keyLocation": location, "urlList": urls}
        self.receipt.add("indexnow.submit", "attempting", {"host": self.p.host, "urlList": urls})
        # Some implementations return an empty body; text preserves the real status.
        result = self.http.call("POST", self.ENDPOINT, body=body, text=True)
        if result["http_status"] not in [200, 202]:
            raise ToolkitError("IndexNow did not acknowledge the notification.")
        self.receipt.add(
            "indexnow.submit",
            "received_key_validation_pending"
            if result["http_status"] == 202
            else "received_not_indexing_proof",
            result,
        )
        return {"submitted_urls": len(urls), **result, "indexed": "not established"}


class Cloudflare:
    BASE = "https://api.cloudflare.com/client/v4/"

    def __init__(self, p, http, vault, receipt):
        self.p, self.http, self.vault, self.receipt = p, http, vault, receipt

    def call(self, method, path, body=None):
        token = self.vault.get("cloudflare_api_token")["value"]
        self.http.secrets.append(token)
        data = self.http.call(
            method, self.BASE + path, body=body, headers={"Authorization": "Bearer " + token}
        )["data"]
        if not data.get("success"):
            raise ToolkitError("Cloudflare rejected the request.")
        return data

    def deploy_google_txt(self):
        zone = self.p.data.get("cloudflare", {}).get("zone_id")
        if not zone or not re.fullmatch(r"[a-fA-F0-9]{32}", zone):
            raise ToolkitError("Supply the exact Cloudflare zone_id.")
        domain = self.p.data["website"]["domain"]
        info = self.call("GET", "zones/" + zone)["result"]
        if info.get("name") != domain:
            raise ToolkitError("Cloudflare zone/domain mismatch; no DNS change made.")
        v = self.p.state().get("google_verification", {})
        if (
            v.get("verificationMethod") != "DNS_TXT"
            or v.get("site", {}).get("identifier") != domain
        ):
            raise ToolkitError("Prepare matching Google DNS_TXT verification first.")
        content = v["token"]
        path = "zones/" + zone + "/dns_records"
        existing = self.call("GET", path + "?type=TXT&name=" + urllib.parse.quote(domain, safe=""))[
            "result"
        ]
        if any(x.get("content", "").strip('"') == content for x in existing):
            self.receipt.add("cloudflare.google_verification_txt", "already_present")
            return {"status": "already_present"}
        payload = {"type": "TXT", "name": domain, "content": content, "ttl": 1}
        self.receipt.add(
            "cloudflare.google_verification_txt", "attempting", {"zone": zone, "record": payload}
        )
        result = self.call("POST", path, payload)["result"]
        check = self.call("GET", path + "/" + result["id"])["result"]
        if check.get("content", "").strip('"') != content or check.get("name") != domain:
            raise ToolkitError("Created TXT record readback mismatch.")
        self.receipt.add(
            "cloudflare.google_verification_txt", "verified", {"record_id": check["id"]}
        )
        return {
            "status": "verified",
            "record_id": check["id"],
            "propagation": "not yet established",
        }
