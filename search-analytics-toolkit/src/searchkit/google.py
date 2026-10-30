"""Google Analytics Admin/Data, Search Console and Site Verification adapters."""

from __future__ import annotations

import urllib.parse

from .auth import PREFIX, GoogleToken
from .core import ToolkitError

ADMIN = "https://analyticsadmin.googleapis.com/"
DATA = "https://analyticsdata.googleapis.com/v1beta/"
GSC = "https://www.googleapis.com/webmasters/v3/"
VERIFY = "https://www.googleapis.com/siteVerification/v1/"
READ = PREFIX + "analytics.readonly|" + PREFIX + "analytics.edit"
EDIT = PREFIX + "analytics.edit"
GSC_READ = PREFIX + "webmasters.readonly|" + PREFIX + "webmasters"
GSC_EDIT = PREFIX + "webmasters"
VERIFY_SCOPE = PREFIX + "siteverification.verify_only"


def q(value):
    return urllib.parse.quote(str(value), safe="")


def lead_audience(host, name="Website enquiries — 30 days", event="generate_lead", days=30):
    return {
        "displayName": name,
        "description": "Public-site confirmed enquiries; exclude controlled tests when reporting.",
        "membershipDurationDays": days,
        "filterClauses": [
            {
                "clauseType": "INCLUDE",
                "simpleFilter": {
                    "scope": "AUDIENCE_FILTER_SCOPE_WITHIN_SAME_EVENT",
                    "filterExpression": {
                        "andGroup": {
                            "filterExpressions": [
                                {
                                    "orGroup": {
                                        "filterExpressions": [{"eventFilter": {"eventName": event}}]
                                    }
                                },
                                {
                                    "orGroup": {
                                        "filterExpressions": [
                                            {
                                                "dimensionOrMetricFilter": {
                                                    "fieldName": "hostName",
                                                    "stringFilter": {
                                                        "matchType": "EXACT",
                                                        "value": host,
                                                        "caseSensitive": False,
                                                    },
                                                }
                                            }
                                        ]
                                    }
                                },
                            ]
                        }
                    },
                },
            }
        ],
    }


class Google:
    def __init__(self, profile, http, vault, receipt):
        self.p, self.http, self.receipt = profile, http, receipt
        self.token = GoogleToken(vault, http)

    def request(self, method, url, body=None, scope=READ):
        return self.http.call(method, url, body=body, headers=self.token.headers(scope))["data"]

    def pages(self, url, field, scope=READ):
        rows, seen = [], set()
        for _ in range(1000):
            data = self.request("GET", url, scope=scope)
            rows.extend(data.get(field, []))
            token = data.get("nextPageToken")
            if not token:
                return rows
            if token in seen:
                raise ToolkitError("API repeated a pagination token; inventory is incomplete.")
            seen.add(token)
            p = urllib.parse.urlsplit(url)
            args = urllib.parse.parse_qs(p.query)
            args["pageToken"] = [token]
            url = urllib.parse.urlunsplit(
                p._replace(query=urllib.parse.urlencode(args, doseq=True))
            )
        raise ToolkitError("Pagination bound exceeded; inventory is incomplete.")

    def inventory(self):
        return {
            "account_summaries": self.pages(
                ADMIN + "v1beta/accountSummaries?pageSize=200", "accountSummaries"
            ),
            "search_console_sites": self.request("GET", GSC + "sites", scope=GSC_READ),
        }

    def write(self, method, url, body, action, scope=EDIT):
        # Intent is durable before transmitting a mutation; unknown outcomes remain visible.
        self.receipt.add(action, "attempting", {"method": method, "url": url, "body": body})
        result = self.request(method, url, body, scope)
        self.receipt.add(action, "accepted", result)
        return result

    def setup_ga4(self):
        cfg, state = self.p.data["ga4"], self.p.state()
        aid = cfg.get("account_id")
        if not aid:
            raise ToolkitError(
                "Set ga4.account_id after inventory; account/TOS creation is an owner step."
            )
        prop_id = cfg.get("property_id") or state.get("ga4_property_id")
        if prop_id:
            prop = "properties/" + str(prop_id)
            current = self.request("GET", ADMIN + "v1beta/" + prop)
        else:
            if not cfg.get("create_property"):
                raise ToolkitError(
                    "Set ga4.property_id or explicitly set ga4.create_property=true."
                )
            existing = self.pages(
                ADMIN
                + "v1beta/properties?filter="
                + q("parent:accounts/" + str(aid))
                + "&pageSize=200",
                "properties",
            )
            if any(x.get("displayName") == cfg["display_name"] for x in existing):
                raise ToolkitError(
                    "A same-named property exists. Pin its property_id after inventory; refusing a duplicate."
                )
            current = self.write(
                "POST",
                ADMIN + "v1beta/properties",
                {
                    "parent": "accounts/" + str(aid),
                    "displayName": cfg["display_name"],
                    "timeZone": cfg["time_zone"],
                    "currencyCode": cfg["currency"],
                },
                "ga4.create_property",
            )
            prop = current["name"]
            self.p.save_state(ga4_property_id=prop.split("/")[-1])
        if current.get("account", current.get("parent")) != "accounts/" + str(aid):
            raise ToolkitError("GA4 property/account identity mismatch. No settings changed.")
        streams = self.pages(ADMIN + "v1beta/" + prop + "/dataStreams?pageSize=200", "dataStreams")
        desired_stream = str(cfg.get("stream_id") or state.get("ga4_stream_id") or "")
        matches = [
            s
            for s in streams
            if urllib.parse.urlsplit(s.get("webStreamData", {}).get("defaultUri", "")).hostname
            == self.p.host
        ]
        if desired_stream:
            matches = [s for s in matches if s["name"].split("/")[-1] == desired_stream]
            if len(matches) != 1:
                raise ToolkitError("Pinned GA4 stream does not match the public website.")
        if len(matches) > 1:
            raise ToolkitError("Several matching streams exist; pin ga4.stream_id before changes.")
        other_websites = [
            s
            for s in streams
            if s.get("webStreamData")
            and urllib.parse.urlsplit(s["webStreamData"].get("defaultUri", "")).hostname
            != self.p.host
        ]
        if (other_websites or (streams and not matches)) and not cfg.get(
            "allow_shared_property", False
        ):
            raise ToolkitError(
                "Property contains streams for another site. Pin the correct property or explicitly allow sharing."
            )
        self.receipt.add(
            "ga4.before_property_and_streams", "snapshot", {"property": current, "streams": streams}
        )
        drift = {
            k: v
            for k, v in {"timeZone": cfg["time_zone"], "currencyCode": cfg["currency"]}.items()
            if current.get(k) != v
        }
        if drift and not cfg.get("update_property_settings"):
            raise ToolkitError(
                "Property timezone/currency differ: "
                + str(drift)
                + ". Preserve history or explicitly allow update_property_settings."
            )
        if drift:
            self.write(
                "PATCH",
                ADMIN + "v1beta/" + prop + "?updateMask=" + ",".join(drift),
                {"name": prop, **drift},
                "ga4.update_property",
            )
            self._verify(ADMIN + "v1beta/" + prop, drift, "ga4.update_property")
        if not matches:
            stream = self.write(
                "POST",
                ADMIN + "v1beta/" + prop + "/dataStreams",
                {
                    "type": "WEB_DATA_STREAM",
                    "displayName": cfg["display_name"] + " website",
                    "webStreamData": {"defaultUri": self.p.url},
                },
                "ga4.create_web_stream",
            )
            self.p.save_state(
                ga4_property_id=prop.split("/")[-1], ga4_stream_id=stream["name"].split("/")[-1]
            )
            readback = self.request("GET", ADMIN + "v1beta/" + stream["name"])
            if readback.get("webStreamData", {}).get("defaultUri", "").rstrip(
                "/"
            ) != self.p.url.rstrip("/"):
                raise ToolkitError("Created web stream readback did not match website.")
        else:
            stream = matches[0]
        self.p.save_state(
            ga4_property_id=prop.split("/")[-1],
            ga4_stream_id=stream["name"].split("/")[-1],
            ga4_measurement_id=stream["webStreamData"]["measurementId"],
        )
        self.receipt.add(
            "ga4.target",
            "verified",
            {
                "property": prop,
                "stream": stream["name"],
                "measurement_id": stream["webStreamData"]["measurementId"],
            },
        )
        retention_url = ADMIN + "v1beta/" + prop + "/dataRetentionSettings"
        desired = "FOURTEEN_MONTHS" if cfg.get("retention_months", 14) == 14 else "TWO_MONTHS"
        retention = self.request("GET", retention_url)
        self.receipt.add("ga4.before_retention", "snapshot", retention)
        if retention.get("eventDataRetention") != desired:
            self.write(
                "PATCH",
                retention_url + "?updateMask=eventDataRetention",
                {"name": prop + "/dataRetentionSettings", "eventDataRetention": desired},
                "ga4.retention",
            )
            self._verify(retention_url, {"eventDataRetention": desired}, "ga4.retention")
        existing = self.pages(ADMIN + "v1beta/" + prop + "/keyEvents?pageSize=200", "keyEvents")
        for event in cfg.get("key_events", []):
            found = [x for x in existing if x["eventName"] == event["eventName"]]
            if len(found) > 1:
                raise ToolkitError("Ambiguous existing key event: " + event["eventName"])
            if not found:
                resource = self.write(
                    "POST",
                    ADMIN + "v1beta/" + prop + "/keyEvents",
                    event,
                    "ga4.key_event." + event["eventName"],
                )
            elif found[0].get("countingMethod") != event["countingMethod"]:
                resource = self.write(
                    "PATCH",
                    ADMIN + "v1beta/" + found[0]["name"] + "?updateMask=countingMethod",
                    {"name": found[0]["name"], "countingMethod": event["countingMethod"]},
                    "ga4.key_event." + event["eventName"],
                )
            else:
                self.receipt.add("ga4.key_event." + event["eventName"], "already_configured")
                continue
            self._verify(
                ADMIN + "v1beta/" + resource["name"], event, "ga4.key_event." + event["eventName"]
            )
        existing = self.pages(
            ADMIN + "v1beta/" + prop + "/customDimensions?pageSize=200", "customDimensions"
        )
        for definition in cfg.get("custom_dimensions", []):
            found = [x for x in existing if x["parameterName"] == definition["parameterName"]]
            if found:
                if any(x["scope"] != definition["scope"] for x in found):
                    raise ToolkitError(
                        "Custom dimension has conflicting scope: " + definition["parameterName"]
                    )
                self.receipt.add(
                    "ga4.dimension." + definition["parameterName"], "already_configured"
                )
                continue
            resource = self.write(
                "POST",
                ADMIN + "v1beta/" + prop + "/customDimensions",
                definition,
                "ga4.dimension." + definition["parameterName"],
            )
            self._verify(
                ADMIN + "v1beta/" + resource["name"],
                definition,
                "ga4.dimension." + definition["parameterName"],
            )
        if cfg.get("audiences"):
            existing = self.pages(
                ADMIN + "v1alpha/" + prop + "/audiences?pageSize=200", "audiences"
            )
            for audience in cfg["audiences"]:
                desired_audience = lead_audience(
                    self.p.host,
                    audience["name"],
                    audience.get("event", "generate_lead"),
                    audience.get("days", 30),
                )
                found = [x for x in existing if x.get("displayName") == audience["name"]]
                if found:
                    if (
                        len(found) != 1
                        or found[0].get("filterClauses") != desired_audience["filterClauses"]
                        or found[0].get("membershipDurationDays")
                        != desired_audience["membershipDurationDays"]
                    ):
                        raise ToolkitError(
                            "Existing audience differs; review its immutable filters before reuse."
                        )
                    self.receipt.add("ga4.audience." + audience["name"], "already_configured")
                    continue
                resource = self.write(
                    "POST",
                    ADMIN + "v1alpha/" + prop + "/audiences",
                    desired_audience,
                    "ga4.audience." + audience["name"],
                )
                self._verify(
                    ADMIN + "v1alpha/" + resource["name"],
                    desired_audience,
                    "ga4.audience." + audience["name"],
                )
        return {"property": prop, "stream": stream, "collection_verified": False}

    def _verify(self, url, expected, action):
        actual = self.request("GET", url)
        if any(actual.get(k) != value for k, value in expected.items()):
            raise ToolkitError(
                action + " readback mismatch; inspect the saved receipt before retrying."
            )
        self.receipt.add(action, "verified")

    def site_url(self):
        return self.p.data["search_console"].get(
            "site_url", "sc-domain:" + self.p.data["website"]["domain"]
        )

    def setup_gsc(self):
        site = self.site_url()
        self.write("PUT", GSC + "sites/" + q(site), None, "gsc.add_site", GSC_EDIT)
        sites = self.request("GET", GSC + "sites", scope=GSC_READ).get("siteEntry", [])
        entry = next((x for x in sites if x["siteUrl"] == site), None)
        if not entry or entry.get("permissionLevel") not in {"siteOwner", "siteFullUser"}:
            raise ToolkitError(
                "Search Console ownership is not verified. Run verification prepare/confirm first."
            )
        self.receipt.add("gsc.site", "verified", entry)
        sitemap_url = GSC + "sites/" + q(site) + "/sitemaps"
        existing = self.request("GET", sitemap_url, scope=GSC_READ).get("sitemap", [])
        for url in self.p.data["website"].get("sitemaps", []):
            if any(x["path"] == url for x in existing):
                self.receipt.add("gsc.sitemap", "already_submitted", url)
                continue
            self.write("PUT", sitemap_url + "/" + q(url), None, "gsc.submit_sitemap", GSC_EDIT)
            data = self.request("GET", sitemap_url + "/" + q(url), scope=GSC_READ)
            if data.get("path") != url:
                raise ToolkitError("Sitemap readback mismatch.")
            self.receipt.add("gsc.sitemap", "submission_verified_processing_separate", data)
        return {"site": entry, "sitemaps": self.request("GET", sitemap_url, scope=GSC_READ)}

    def prepare_verification(self):
        site = self.site_url()
        domain = site.startswith("sc-domain:")
        body = {
            "site": {
                "type": "INET_DOMAIN" if domain else "SITE",
                "identifier": site.removeprefix("sc-domain:"),
            },
            "verificationMethod": "DNS_TXT" if domain else "META",
        }
        token = self.request("POST", VERIFY + "token", body, VERIFY_SCOPE)
        self.p.save_state(google_verification={**body, **token})
        return {**body, **token}

    def confirm_verification(self):
        v = self.p.state().get("google_verification")
        if not v:
            raise ToolkitError("Prepare Google verification first and publish its proof.")
        result = self.write(
            "POST",
            VERIFY + "webResource?verificationMethod=" + q(v["verificationMethod"]),
            {"site": v["site"]},
            "gsc.verify_ownership",
            VERIFY_SCOPE,
        )
        if result.get("site") != v["site"]:
            raise ToolkitError("Google verification response did not match the requested site.")
        self.receipt.add("gsc.verify_ownership", "verified", {"site": result["site"]})
        return result

    def ga4_report(self, start, end, dimensions, metrics, *, extra_filter=None):
        cfg, state = self.p.data["ga4"], self.p.state()
        pid = cfg.get("property_id") or state.get("ga4_property_id")
        if not pid:
            raise ToolkitError("No GA4 property is configured.")
        filters = [
            {
                "filter": {
                    "fieldName": "hostName",
                    "stringFilter": {
                        "matchType": "EXACT",
                        "value": self.p.host,
                        "caseSensitive": False,
                    },
                }
            }
        ]
        if extra_filter:
            filters.append(extra_filter)
        body = {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "dimensionFilter": {"andGroup": {"expressions": filters}},
            "limit": "10000",
            "returnPropertyQuota": True,
        }
        rows, responses, offset = [], [], 0
        while True:
            response = self.request(
                "POST",
                DATA + "properties/" + str(pid) + ":runReport",
                {**body, "offset": str(offset)},
                PREFIX + "analytics.readonly",
            )
            batch = response.get("rows", [])
            responses.append(response)
            rows.extend(batch)
            offset += len(batch)
            if offset >= response.get("rowCount", 0):
                break
            if not batch or len(responses) >= 100:
                raise ToolkitError("GA4 report incomplete; pagination limit reached.")
        return {
            "request": body,
            "property": str(pid),
            "scope": {"hostName": self.p.host},
            "responses": responses,
            "rows": rows,
            "rowCount": len(rows),
            "completeness": "API pagination exhausted; thresholding/sampling flags remain in responses",
        }

    def search_report(self, start, end, dimensions):
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": dimensions,
            "type": "web",
            "dataState": "final",
            "rowLimit": 25000,
        }
        rows, offset, responses = [], 0, []
        while True:
            response = self.request(
                "POST",
                GSC + "sites/" + q(self.site_url()) + "/searchAnalytics/query",
                {**body, "startRow": offset},
                GSC_READ,
            )
            batch = response.get("rows", [])
            responses.append(response)
            rows.extend(batch)
            if len(batch) < 25000:
                break
            offset += len(batch)
            if len(responses) >= 100:
                raise ToolkitError(
                    "Search Console report exceeded the pagination bound; partition dates."
                )
        return {
            "request": body,
            "rows": rows,
            "responses": responses,
            "date_basis": "America/Los_Angeles",
            "completeness": "Returned pages exhausted; anonymized/top-row limits still apply",
        }

    def inspect_url(self, url):
        return self.request(
            "POST",
            "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
            {"inspectionUrl": url, "siteUrl": self.site_url(), "languageCode": "en-GB"},
            GSC_READ,
        )
