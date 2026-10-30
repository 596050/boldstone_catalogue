"""Optional Yandex Webmaster v4 adapter using an owner-issued OAuth token."""

from urllib.parse import quote

from .core import ToolkitError


class Yandex:
    BASE = "https://api.webmaster.yandex.net/v4/"

    def __init__(self, p, http, vault, receipt):
        self.p, self.http, self.vault, self.receipt = p, http, vault, receipt

    def call(self, method, path, body=None):
        token = self.vault.get("yandex_oauth_token")["value"]
        self.http.secrets.append(token)
        return self.http.call(
            method,
            self.BASE + path,
            body=body,
            headers={"Authorization": "OAuth " + token, "Accept": "application/json"},
        )["data"]

    def inventory(self):
        uid = self.call("GET", "user")["user_id"]
        data = self.call("GET", "user/" + str(uid) + "/hosts")
        return {"user_id": uid, **data}

    def target(self, create=False):
        data = self.inventory()
        hosts = [
            h
            for h in data.get("hosts", [])
            if h.get("ascii_host_url", "").rstrip("/") == self.p.url.rstrip("/")
        ]
        if len(hosts) > 1:
            raise ToolkitError("Yandex returned ambiguous site identities.")
        prefix = "user/" + str(data["user_id"]) + "/hosts/"
        if not hosts:
            if not create:
                raise ToolkitError("Yandex site absent; prepare verification or run setup --apply.")
            self.receipt.add("yandex.add_site", "attempting", {"host_url": self.p.url})
            added = self.call("POST", prefix.rstrip("/"), {"host_url": self.p.url})
            host = self.call("GET", prefix + quote(added["host_id"], safe=""))
        else:
            host = hosts[0]
        if host.get("ascii_host_url", "").rstrip("/") != self.p.url.rstrip("/"):
            raise ToolkitError("Yandex site URL readback mismatch.")
        return prefix + quote(host["host_id"], safe=""), host

    def prepare_verification(self):
        path, host = self.target(create=True)
        data = self.call("GET", path + "/verification")
        if not data.get("verification_uin"):
            raise ToolkitError("Yandex returned no ownership code.")
        self.p.save_state(yandex_verification={"host_url": self.p.url, **data})
        return data

    def confirm_verification(self):
        path, _ = self.target()
        self.receipt.add("yandex.verify_ownership", "attempting", {"host_url": self.p.url})
        self.call("POST", path + "/verification?verification_type=META_TAG")
        result = self.call("GET", path + "/verification")
        status = result.get("verification_state")
        self.receipt.add(
            "yandex.verify_ownership", "verified" if status == "VERIFIED" else "pending", result
        )
        return {
            "verification_state": status,
            "verified": status == "VERIFIED",
            "note": "IN_PROGRESS is not verified; rerun confirm/status after processing.",
        }

    def sitemaps(self, path):
        rows, offset = [], None
        for _ in range(1000):
            args = "?limit=100" + ("&offset=" + quote(offset, safe="") if offset else "")
            data = self.call("GET", path + "/user-added-sitemaps" + args)
            batch = data.get("sitemaps", [])
            rows.extend(batch)
            if len(rows) >= data.get("count", len(rows)):
                return rows
            if not batch or batch[-1]["sitemap_id"] == offset:
                raise ToolkitError("Yandex sitemap pagination incomplete.")
            offset = batch[-1]["sitemap_id"]
        raise ToolkitError("Yandex sitemap pagination bound exceeded.")

    def setup(self):
        path, host = self.target(create=True)
        if not host.get("verified"):
            raise ToolkitError("Yandex ownership pending; prepare/publish/confirm its META proof.")
        existing = self.sitemaps(path)
        for url in self.p.data["website"].get("sitemaps", []):
            if any(s.get("sitemap_url") == url for s in existing):
                continue
            self.receipt.add("yandex.submit_sitemap", "attempting", {"url": url})
            result = self.call("POST", path + "/user-added-sitemaps", {"url": url})
            readback = self.call(
                "GET", path + "/user-added-sitemaps/" + quote(result["sitemap_id"], safe="")
            )
            if readback.get("sitemap_url") != url:
                raise ToolkitError("Yandex sitemap readback mismatch.")
            self.receipt.add("yandex.sitemap", "submission_verified_processing_separate", readback)
        return {"host": host, "sitemaps": self.sitemaps(path)}
