"""Configuration, private local state, redaction and durable receipts."""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ToolkitError(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def private_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def redact(data, secrets=()):
    sensitive = {
        "access_token",
        "refresh_token",
        "client_secret",
        "id_token",
        "apikey",
        "api_key",
        "authorization",
        "authenticationcode",
        "dnsverificationcode",
    }
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k.lower() in sensitive else redact(v, secrets)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [redact(x, secrets) for x in data]
    if isinstance(data, str):
        for secret in secrets:
            if secret:
                data = data.replace(secret, "[REDACTED]")
        return re.sub(r"(?i)(apikey|access_token|client_secret)=([^&\s]+)", r"\1=[REDACTED]", data)
    return data


def csv_safe(value):
    """Keep raw values in JSON; avoid formula-like text execution in CSV viewers."""
    if isinstance(value, str) and value and value[0] in "=+-@\t\r":
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
            return "'" + value
    return value


def canonical_url(value, *, root=False):
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.port not in (None, 443)
        or p.fragment
        or (root and p.query)
    ):
        raise ToolkitError("Use an HTTPS URL without credentials, fragments or a nonstandard port.")
    if root and p.path not in ("", "/"):
        raise ToolkitError("website.url must be the canonical site root.")
    return (
        "https://"
        + p.hostname.lower().encode("idna").decode()
        + (p.path or "/")
        + ("?" + p.query if p.query else "")
    )


class Profile:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        try:
            self.data = json.loads(self.path.read_text())
        except (OSError, ValueError) as e:
            raise ToolkitError(f"Cannot read profile: {e}") from None
        self.validate()
        self.id = self.data["id"]
        self.url = canonical_url(self.data["website"]["url"], root=True)
        self.host = urlsplit(self.url).hostname
        base = os.environ.get("SEARCHKIT_STATE_DIR")
        self.state_dir = Path(base).expanduser() if base else Path.home() / ".local/state/searchkit"
        self.state_path = self.state_dir / self.id / "state.json"

    def validate(self):
        d = self.data
        if not isinstance(d, dict):
            raise ToolkitError("Profile must be a JSON object.")
        for section in [
            "website",
            "organization",
            "ga4",
            "google",
            "search_console",
            "bing",
            "yandex",
            "network",
            "cloudflare",
            "social_profiles",
        ]:
            if section in d and not isinstance(d[section], dict):
                raise ToolkitError(section + " must be a JSON object.")
        if (
            not isinstance(d.get("organization", {}).get("name"), str)
            or not d["organization"]["name"].strip()
        ):
            raise ToolkitError("Set the real organization.name.")
        if d["organization"].get("type", "Organization") not in {
            "Organization",
            "LocalBusiness",
            "Person",
        }:
            raise ToolkitError("organization.type must be Organization, LocalBusiness or Person.")
        if d.get("schema_version") != 1 or not re.fullmatch(
            r"[a-z0-9][a-z0-9-]{0,62}", d.get("id", "")
        ):
            raise ToolkitError("schema_version must be 1; id must be a lowercase slug.")
        url = canonical_url(d.get("website", {}).get("url", ""), root=True)
        host = urlsplit(url).hostname
        domain = d["website"].get("domain", host).lower()
        d["website"]["domain"] = domain
        d["website"].setdefault("sitemaps", [])
        d["website"].setdefault("priority_urls", [])
        if not re.fullmatch(r"[a-z0-9.-]+", domain) or not (
            host == domain or host.endswith("." + domain)
        ):
            raise ToolkitError("website.domain must be the site's DNS domain.")
        for sitemap in d["website"].get("sitemaps", []):
            if urlsplit(canonical_url(sitemap)).hostname != host:
                raise ToolkitError("Sitemaps must use the configured canonical hostname.")
        for url in d["website"].get("priority_urls", []):
            if urlsplit(canonical_url(url)).hostname != host:
                raise ToolkitError("Priority URLs must use the configured canonical hostname.")
        g = d.get("ga4", {})
        for key in ["account_id", "property_id", "stream_id"]:
            if g.get(key) is not None and not re.fullmatch(r"[0-9]+", str(g[key])):
                raise ToolkitError(f"ga4.{key} must be a numeric ID or null.")
        if g.get("enabled"):
            for field, identity in [
                ("key_events", "eventName"),
                ("custom_dimensions", "parameterName"),
                ("audiences", "name"),
            ]:
                definitions = g.get(field, [])
                if not isinstance(definitions, list) or any(
                    not isinstance(x, dict) for x in definitions
                ):
                    raise ToolkitError("ga4." + field + " must be a list of objects.")
                names = [x.get(identity) for x in definitions]
                if len(set(names)) != len(names):
                    raise ToolkitError("Duplicate ga4." + field + " definitions are prohibited.")
            try:
                ZoneInfo(g["time_zone"])
            except (KeyError, ZoneInfoNotFoundError):
                raise ToolkitError("ga4.time_zone must be an IANA timezone.") from None
            if not re.fullmatch(r"[A-Z]{3}", g.get("currency", "")):
                raise ToolkitError("ga4.currency must be an ISO 4217 currency code.")
            if g.get("retention_months", 14) not in (2, 14):
                raise ToolkitError(
                    "This standard-property adapter supports 2 or 14 month retention."
                )
            for e in g.get("key_events", []):
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", e.get("eventName", "")):
                    raise ToolkitError("Invalid GA4 key event name.")
                if e.get("countingMethod") not in ("ONCE_PER_EVENT", "ONCE_PER_SESSION"):
                    raise ToolkitError("Set an explicit key event countingMethod.")
                if set(e) - {"eventName", "countingMethod"}:
                    raise ToolkitError(
                        "Key event defaults/values require separate review; unsupported fields."
                    )
            for c in g.get("custom_dimensions", []):
                if set(c) - {"parameterName", "displayName", "description", "scope"}:
                    raise ToolkitError("Unsupported custom-dimension fields.")
                if c.get("scope") != "EVENT" or not re.fullmatch(
                    r"[A-Za-z][A-Za-z0-9_]{0,39}", c.get("parameterName", "")
                ):
                    raise ToolkitError(
                        "Custom dimensions require a valid event parameter and EVENT scope."
                    )
                if (
                    not re.fullmatch(r"[A-Za-z0-9_ ]{1,82}", c.get("displayName", ""))
                    or len(c.get("description", "")) > 150
                ):
                    raise ToolkitError(
                        "Invalid custom dimension display name or description length."
                    )
            for a in g.get("audiences", []):
                if not isinstance(a.get("name"), str) or not 1 <= len(a["name"]) <= 100:
                    raise ToolkitError("Audience name must contain 1 to 100 characters.")
                if not isinstance(a.get("days", 30), int) or not 1 <= a.get("days", 30) <= 540:
                    raise ToolkitError("Audience membership must be 1 to 540 days.")
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", a.get("event", "generate_lead")):
                    raise ToolkitError("Invalid audience event name.")
        s = d.get("search_console", {})
        if s.get("enabled"):
            site = s.get("site_url", "sc-domain:" + domain)
            s["site_url"] = site
            if site != "sc-domain:" + domain and site != url:
                raise ToolkitError(
                    "Search Console property must match website.domain or website.url."
                )
        for v in d.get("social_profiles", {}).values():
            canonical_url(v)
        for platform in d.get("social_profiles", {}):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", platform):
                raise ToolkitError("Social platform keys must be simple source labels.")
        if d.get("organization", {}).get("logo_url"):
            canonical_url(d["organization"]["logo_url"])

    def state(self):
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        if state.get("website_url", self.url) != self.url:
            raise ToolkitError(
                "Profile ID belongs to a different website. Choose a new profile ID."
            )
        for field in ["ga4_property_id", "ga4_stream_id"]:
            if state.get(field) and not re.fullmatch(r"[0-9]+", str(state[field])):
                raise ToolkitError("Invalid remembered GA4 target ID; inspect private state.")
        return state

    def save_state(self, **updates):
        state = self.state()
        state.update(updates, website_url=self.url)
        private_json(self.state_path, state)

    @contextlib.contextmanager
    def lock(self):
        # Process lock: prevents concurrent setup from creating duplicate resources.
        import fcntl

        self.state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        p = self.state_path.with_suffix(".lock")
        with p.open("a") as f:
            os.chmod(p, 0o600)
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ToolkitError("Another setup/report command owns this profile lock.") from None
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


class Receipt:
    def __init__(self, profile, command, root):
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.folder = Path(root) / profile.id / (stamp + "-" + command)
        self.folder.mkdir(parents=True, mode=0o700)
        self.path = self.folder / "receipt.json"
        self.data = {
            "started_at": now(),
            "profile": profile.id,
            "website": profile.url,
            "command": command,
            "configuration_sha256": hashlib.sha256(profile.path.read_bytes()).hexdigest(),
            "status": "running",
            "steps": [],
        }
        self.flush()

    def flush(self):
        private_json(self.path, self.data)

    def add(self, action, status, details=None):
        self.data["steps"].append(
            {"at": now(), "action": action, "status": status, "details": redact(details)}
        )
        self.flush()

    def finish(self, status):
        self.data.update(status=status, finished_at=now())
        self.flush()

    def export(self, name, data):
        private_json(self.folder / (name + ".json"), redact(data))


def template(site_url, name, slug):
    url = canonical_url(site_url, root=True)
    host = urlsplit(url).hostname
    return {
        "schema_version": 1,
        "id": slug,
        "website": {
            "url": url,
            "domain": host,
            "sitemaps": [url + "sitemap.xml"],
            "priority_urls": [url],
        },
        "organization": {"name": name, "type": "Organization"},
        "social_profiles": {},
        "google": {"expected_email": None},
        "network": {"dns_fallback": None},
        "ga4": {
            "enabled": True,
            "account_id": None,
            "property_id": None,
            "stream_id": None,
            "create_property": False,
            "display_name": name,
            "time_zone": "Europe/London",
            "currency": "GBP",
            "retention_months": 14,
            "update_property_settings": False,
            "native_installation": False,
            "key_events": [{"eventName": "generate_lead", "countingMethod": "ONCE_PER_EVENT"}],
            "custom_dimensions": [],
            "audiences": [],
        },
        "search_console": {"enabled": True, "site_url": "sc-domain:" + host},
        "bing": {"enabled": True},
        "yandex": {"enabled": False},
        "indexnow": {"enabled": True},
        "cloudflare": {"zone_id": None},
    }
